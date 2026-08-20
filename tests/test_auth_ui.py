from fastapi.testclient import TestClient
import pytest

from src.app import create_app


@pytest.fixture
def client():
    app = create_app(":memory:")
    return TestClient(app)


def _create_test_project(client, slug="ui-auth-proj"):
    client.post("/api/projects", json={"slug": slug})
    return slug


def test_auth_tab_rendered_in_workspace(client):
    slug = _create_test_project(client)
    
    # Full page
    res = client.get(f"/projects/{slug}?tab=auth")
    assert res.status_code == 200
    assert "API Authentication Settings" in res.text
    assert "API Keys & Scopes" in res.text
    assert "None (Public)" in res.text

    # HTMX Fragment
    res_htmx = client.get(
        f"/projects/{slug}?tab=auth",
        headers={"hx-request": "true", "hx-target": "workspace-tab-content"},
    )
    assert res_htmx.status_code == 200
    assert "API Authentication Settings" in res_htmx.text
    assert "<html" not in res_htmx.text


def test_update_auth_settings_ui(client):
    slug = _create_test_project(client, "settings-proj")

    # Update to api_key
    res = client.post(
        f"/projects/{slug}/auth/settings",
        data={"auth_type": "api_key"},
    )
    assert res.status_code == 200
    assert 'value="api_key" checked' in res.text
    assert "Authentication settings updated successfully!" in res.text

    # Update to basic without username/password -> error 422
    res_err = client.post(
        f"/projects/{slug}/auth/settings",
        data={"auth_type": "basic", "basic_username": "", "basic_password": ""},
    )
    assert res_err.status_code == 422
    assert "Username and Password are required" in res_err.text

    # Update to basic with valid credentials
    res_basic = client.post(
        f"/projects/{slug}/auth/settings",
        data={"auth_type": "basic", "basic_username": "myuser", "basic_password": "mypassword"},
    )
    assert res_basic.status_code == 200
    assert "value=\"myuser\"" in res_basic.text

    # 404 for unknown project
    res_404 = client.post("/projects/non-existent-proj/auth/settings", data={"auth_type": "none"})
    assert res_404.status_code == 404


def test_api_keys_management_ui(client):
    slug = _create_test_project(client, "keys-proj")

    # Error when name missing
    res_err = client.post(
        f"/projects/{slug}/auth/keys",
        data={"name": "", "scopes": ["read"]},
    )
    assert res_err.status_code == 422
    assert "API Key name is required" in res_err.text

    # Error when scopes missing
    res_err_scopes = client.post(
        f"/projects/{slug}/auth/keys",
        data={"name": "Test Key"},
    )
    assert res_err_scopes.status_code == 422
    assert "At least one scope must be selected" in res_err_scopes.text

    # Successfully create API Key
    res_create = client.post(
        f"/projects/{slug}/auth/keys",
        data={"name": "Frontend Client", "scopes": ["read", "write", "auth"]},
    )
    assert res_create.status_code == 200
    assert "Frontend Client" in res_create.text
    assert "auth" in res_create.text
    assert "Revoke" in res_create.text

    # Fetch created key ID from DB
    db = client.app.state.db
    project = db.get_project(slug)
    keys = db.list_api_keys(project["id"])
    assert len(keys) == 1
    key_id = keys[0]["id"]

    # Revoke key
    res_delete = client.delete(f"/projects/{slug}/auth/keys/{key_id}")
    assert res_delete.status_code == 200
    assert "API Key revoked successfully!" in res_delete.text
    assert "No API Keys generated" in res_delete.text

    # Revoking non-existent key returns 404
    res_delete_404 = client.delete(f"/projects/{slug}/auth/keys/9999")
    assert res_delete_404.status_code == 404
