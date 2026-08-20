import base64
import time
from fastapi.testclient import TestClient
import pytest

from src.app import create_app
from src.core.auth import generate_bearer_token, has_scope, verify_bearer_token


@pytest.fixture
def client():
    app = create_app(":memory:")
    return TestClient(app)


def _setup_project(client, slug="test-proj"):
    res = client.post("/api/projects", json={"slug": slug})
    assert res.status_code == 201
    res = client.post(
        f"/api/projects/{slug}/resources",
        json={
            "name": "users",
            "columns": [
                {"name": "name", "type": "text"},
                {"name": "email", "type": "text"},
            ],
        },
    )
    assert res.status_code == 201
    return slug


def test_auth_mode_none_allows_all_requests(client):
    slug = _setup_project(client, "public-proj")
    
    # POST /auth returns 401 when API key is missing
    auth_resp = client.post(f"/api/{slug}/auth", json={})
    assert auth_resp.status_code == 401

    # CRUD works with no credentials
    post_res = client.post(f"/api/{slug}/users", json={"name": "Alice", "email": "alice@example.com"})
    assert post_res.status_code == 201
    user_id = post_res.json()["id"]

    get_res = client.get(f"/api/{slug}/users")
    assert get_res.status_code == 200
    assert len(get_res.json()) == 1

    get_one = client.get(f"/api/{slug}/users/{user_id}")
    assert get_one.status_code == 200
    assert get_one.json()["name"] == "Alice"

    put_res = client.put(f"/api/{slug}/users/{user_id}", json={"name": "Alice M", "email": "alice@example.com"})
    assert put_res.status_code == 200

    del_res = client.delete(f"/api/{slug}/users/{user_id}")
    assert del_res.status_code == 204


def test_api_key_auth_mode(client):
    slug = _setup_project(client, "apikey-proj")
    db = client.app.state.db
    project = db.get_project(slug)

    # Enable api_key mode
    db.update_project_auth(project["id"], auth_type="api_key")

    # Unauthenticated request rejected
    res = client.get(f"/api/{slug}/users")
    assert res.status_code == 401
    assert "ApiKey" in res.headers.get("www-authenticate", "")

    # Invalid key rejected
    res = client.get(f"/api/{slug}/users", headers={"X-API-Key": "invalid_key"})
    assert res.status_code == 401

    # Create key with read-only scope
    read_key = db.create_api_key(project["id"], name="Read Key", scopes=["read"])["key"]

    # Read works
    res = client.get(f"/api/{slug}/users", headers={"X-API-Key": read_key})
    assert res.status_code == 200

    # Write fails with 403 (insufficient scope)
    res = client.post(f"/api/{slug}/users", json={"name": "Bob", "email": "bob@example.com"}, headers={"X-API-Key": read_key})
    assert res.status_code == 403

    # Create key with write scope
    write_key = db.create_api_key(project["id"], name="Write Key", scopes=["write"])["key"]

    # Write works via Authorization: ApiKey <key>
    res = client.post(f"/api/{slug}/users", json={"name": "Bob", "email": "bob@example.com"}, headers={"Authorization": f"ApiKey {write_key}"})
    assert res.status_code == 201
    row_id = res.json()["id"]

    # Admin key has full access
    admin_key = db.create_api_key(project["id"], name="Admin Key", scopes=["admin"])["key"]
    res = client.put(f"/api/{slug}/users/{row_id}", json={"name": "Bob Updated", "email": "bob@example.com"}, headers={"X-API-Key": admin_key})
    assert res.status_code == 200

    res = client.delete(f"/api/{slug}/users/{row_id}", headers={"X-API-Key": admin_key})
    assert res.status_code == 204


def test_basic_auth_mode(client):
    slug = _setup_project(client, "basic-proj")
    db = client.app.state.db
    project = db.get_project(slug)

    # Enable basic auth
    db.update_project_auth(project["id"], auth_type="basic", basic_username="admin", basic_password="secretpassword")

    # Missing credentials
    res = client.get(f"/api/{slug}/users")
    assert res.status_code == 401
    assert "Basic" in res.headers.get("www-authenticate", "")

    # Invalid credentials
    bad_creds = base64.b64encode(b"admin:wrong").decode("utf-8")
    res = client.get(f"/api/{slug}/users", headers={"Authorization": f"Basic {bad_creds}"})
    assert res.status_code == 401

    # Malformed base64 / invalid header
    res = client.get(f"/api/{slug}/users", headers={"Authorization": "Basic not_valid_base64!!!"})
    assert res.status_code == 401

    # Valid credentials
    valid_creds = base64.b64encode(b"admin:secretpassword").decode("utf-8")
    res = client.post(
        f"/api/{slug}/users",
        json={"name": "Charlie", "email": "charlie@example.com"},
        headers={"Authorization": f"Basic {valid_creds}"},
    )
    assert res.status_code == 201

    res = client.get(f"/api/{slug}/users", headers={"Authorization": f"Basic {valid_creds}"})
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_bearer_token_flow_and_expiration(client):
    slug = _setup_project(client, "bearer-proj")
    db = client.app.state.db
    project = db.get_project(slug)

    # Enable bearer auth
    db.update_project_auth(project["id"], auth_type="bearer")

    # Direct request to /auth without API key fails with 401
    res = client.post(f"/api/{slug}/auth", json={})
    assert res.status_code == 401

    # Invalid API key returns 401
    res = client.post(f"/api/{slug}/auth", json={"apiKey": "invalid_key"})
    assert res.status_code == 401

    # API key without 'auth' scope returns 403
    no_auth_key = db.create_api_key(project["id"], name="Read Only", scopes=["read"])["key"]
    res = client.post(f"/api/{slug}/auth", json={"apiKey": no_auth_key})
    assert res.status_code == 403

    # API key with 'auth' and 'read' scope
    auth_key = db.create_api_key(project["id"], name="Auth Key", scopes=["auth", "read"])["key"]
    res = client.post(f"/api/{slug}/auth", json={"apiKey": auth_key})
    assert res.status_code == 200
    token_data = res.json()
    assert token_data["token_type"] == "bearer"
    assert token_data["expires_in"] == 300
    token = token_data["access_token"]

    # Calling api with bearer token (read)
    res = client.get(f"/api/{slug}/users", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200

    # Write fails because token only inherited read and auth
    res = client.post(f"/api/{slug}/users", json={"name": "David", "email": "david@example.com"}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403

    # Generate token with admin/write scope
    admin_auth_key = db.create_api_key(project["id"], name="Full Key", scopes=["auth", "write", "read"])["key"]
    res = client.post(f"/api/{slug}/auth", headers={"X-API-Key": admin_auth_key})
    assert res.status_code == 200
    full_token = res.json()["access_token"]

    # Write succeeds
    res = client.post(f"/api/{slug}/users", json={"name": "David", "email": "david@example.com"}, headers={"Authorization": f"Bearer {full_token}"})
    assert res.status_code == 201

    # Expired token validation test
    expired_token, _ = generate_bearer_token(
        project_slug=slug,
        api_key_id=1,
        secret_key=db.get_project_auth(project["id"])["secret_key"],
        scopes=["read"],
        ttl=-10,  # Already expired
    )
    res = client.get(f"/api/{slug}/users", headers={"Authorization": f"Bearer {expired_token}"})
    assert res.status_code == 401


def test_auth_utilities():
    secret = "testsecret"
    token, ttl = generate_bearer_token("test", 1, secret, ["read", "write"], ttl=100)
    assert ttl == 100

    payload = verify_bearer_token(token, secret)
    assert payload is not None
    assert payload["slug"] == "test"
    assert payload["scopes"] == ["read", "write"]

    # Wrong secret
    assert verify_bearer_token(token, "wrongsecret") is None

    # Tampered token
    assert verify_bearer_token(token + "x", secret) is None
    assert verify_bearer_token("invalid.token", secret) is None

    # Scope helper
    assert has_scope("read", ["read"])
    assert not has_scope("write", ["read"])
    assert has_scope("write", ["admin"])
    assert has_scope("anything", ["*"])


def test_database_auth_and_api_keys():
    from src.db.database import Database
    db = Database(":memory:")
    proj = db.create_project("db-auth-test")

    auth = db.get_project_auth(proj["id"])
    assert auth["auth_type"] == "none"

    updated = db.update_project_auth(proj["id"], "bearer")
    assert updated["auth_type"] == "bearer"

    key1 = db.create_api_key(proj["id"], name="Key 1", scopes=["read", "auth"])
    assert key1["name"] == "Key 1"
    assert "read" in key1["scopes"]

    fetched_key = db.get_api_key(key1["key"])
    assert fetched_key["id"] == key1["id"]

    keys = db.list_api_keys(proj["id"])
    assert len(keys) == 1

    deleted = db.delete_api_key(proj["id"], key1["id"])
    assert deleted is True
    assert db.get_api_key(key1["key"]) is None
