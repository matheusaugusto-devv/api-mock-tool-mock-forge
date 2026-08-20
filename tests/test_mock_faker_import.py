import io
import json
import pytest
from fastapi.testclient import TestClient

from src.app import create_app
from src.core.errors import InvalidPayloadError
from src.core.faker_generator import generate_mock_record, generate_mock_records, generate_value_for_type
from src.core.importer_exporter import (
    export_project_json,
    export_project_openapi,
    import_openapi_spec,
    import_project_json,
    import_resource_json_data,
    parse_openapi_spec,
)
from src.db.database import Database


@pytest.fixture
def client():
    app = create_app(db_path=":memory:")
    return TestClient(app)


# --- 1. Faker Generator Unit Tests ---

def test_faker_generator_mapping():
    assert isinstance(generate_value_for_type("name"), str)
    assert "@" in generate_value_for_type("email")
    assert isinstance(generate_value_for_type("number"), int)
    assert isinstance(generate_value_for_type("boolean"), bool)
    assert isinstance(generate_value_for_type("price"), float)
    assert isinstance(generate_value_for_type("url"), str)
    assert isinstance(generate_value_for_type("company"), str)
    # Direct faker attribute match
    assert isinstance(generate_value_for_type("first_name"), str)
    # Fallback with col_name hint
    assert isinstance(generate_value_for_type("text", col_name="email"), str)


def test_faker_generator_fallback():
    # Invalid or unknown type fallback to text
    val = generate_value_for_type("completely_unknown_type_xyz_123")
    assert isinstance(val, str)
    assert len(val) > 0


def test_faker_generate_mock_record_and_records():
    columns = [
        {"name": "full_name", "type": "name"},
        {"name": "contact_email", "type": "email"},
        {"name": "age", "type": "number"},
        {"name": "is_active", "type": "boolean"},
        {"name": "custom_field", "type": "unknown_type"},
    ]
    record = generate_mock_record(columns)
    assert "full_name" in record
    assert "contact_email" in record
    assert isinstance(record["age"], int)
    assert isinstance(record["is_active"], bool)
    assert isinstance(record["custom_field"], str)

    records = generate_mock_records(columns, count=5)
    assert len(records) == 5
    assert all("full_name" in r for r in records)


# --- 2. OpenAPI 3.0 Parser & Importer Unit Tests ---

def test_parse_openapi_spec_json_and_yaml():
    spec_json = """
    {
      "openapi": "3.0.0",
      "info": {"title": "Test API", "version": "1.0"},
      "components": {
        "schemas": {
          "User": {
            "type": "object",
            "properties": {
              "name": {"type": "string"},
              "email": {"type": "string", "format": "email"},
              "age": {"type": "integer"},
              "active": {"type": "boolean"}
            }
          }
        }
      },
      "paths": {
        "/orders": {
          "get": {}
        }
      }
    }
    """
    res = parse_openapi_spec(spec_json)
    assert len(res) == 2
    names = {r["name"] for r in res}
    assert "users" in names
    assert "orders" in names

    user_res = next(r for r in res if r["name"] == "users")
    cols = {c["name"]: c["type"] for c in user_res["columns"]}
    assert cols["name"] == "text"
    assert cols["email"] == "email"
    assert cols["age"] == "number"
    assert cols["active"] == "boolean"


def test_parse_openapi_spec_yaml():
    yaml_spec = """
    openapi: 3.0.0
    info:
      title: Sample
      version: 1.0.0
    components:
      schemas:
        Article:
          properties:
            title:
              type: string
    """
    res = parse_openapi_spec(yaml_spec)
    assert len(res) == 1
    assert res[0]["name"] == "articles"


def test_parse_openapi_invalid():
    with pytest.raises(InvalidPayloadError):
        parse_openapi_spec("{invalid json")
    with pytest.raises(InvalidPayloadError):
        parse_openapi_spec(12345)


def test_openapi_import_into_sqlite():
    db = Database(":memory:")
    spec = {
        "openapi": "3.0.0",
        "components": {
            "schemas": {
                "Product": {
                    "properties": {
                        "title": {"type": "string"},
                        "price": {"type": "number"}
                    }
                }
            }
        }
    }
    project = import_openapi_spec(db, "store-api", spec)
    assert project["slug"] == "store-api"
    resources = db.list_resources(project["id"])
    assert len(resources) == 1
    assert resources[0]["name"] == "products"
    cols = {c["name"]: c["type"] for c in resources[0]["columns"]}
    assert cols["title"] == "text"
    assert cols["price"] == "float"


# --- 3. JSON Import/Export Unit Tests ---

def test_json_export_and_import():
    db = Database(":memory:")
    p = db.create_project("my-shop")
    r = db.create_resource(p["id"], "items", [{"name": "title", "type": "text"}])
    db.insert_row(p["id"], r["id"], {"title": "Item A"})
    db.insert_row(p["id"], r["id"], {"title": "Item B"})

    exported = export_project_json(db, "my-shop")
    assert exported["slug"] == "my-shop"
    assert len(exported["resources"]) == 1
    assert exported["resources"][0]["name"] == "items"
    assert len(exported["resources"][0]["data"]) == 2

    # Import into a new db
    db2 = Database(":memory:")
    import_project_json(db2, exported, target_slug="my-shop-imported")
    p2 = db2.get_project("my-shop-imported")
    assert p2 is not None
    res2 = db2.list_resources(p2["id"])
    assert len(res2) == 1
    rows2 = db2.list_rows(p2["id"], res2[0]["id"])
    assert len(rows2) == 2
    assert rows2[0]["title"] == "Item A"


def test_json_export_invalid():
    db = Database(":memory:")
    with pytest.raises(InvalidPayloadError):
        export_project_json(db, "nonexistent")
    with pytest.raises(InvalidPayloadError):
        export_project_openapi(db, "nonexistent")
    with pytest.raises(InvalidPayloadError):
        import_project_json(db, "not a dict")
    with pytest.raises(InvalidPayloadError):
        import_project_json(db, {"slug": "valid-slug", "resources": "not-a-list"})


def test_openapi_export():
    db = Database(":memory:")
    p = db.create_project("customer-api")
    db.create_resource(p["id"], "customers", [
        {"name": "name", "type": "text"},
        {"name": "age", "type": "number"},
        {"name": "active", "type": "boolean"},
        {"name": "balance", "type": "float"},
    ])

    oas = export_project_openapi(db, "customer-api")
    assert oas["openapi"] == "3.0.0"
    assert "/api/customer-api/customers" in oas["paths"]
    assert "Customer" in oas["components"]["schemas"]


# --- 4. API Endpoints & HTMX Data Explorer Tests ---

def test_api_generate_mocks(client):
    client.post("/api/projects", json={"slug": "mock-proj"})
    client.post("/api/projects/mock-proj/resources", json={
        "name": "authors",
        "columns": [{"name": "name", "type": "name"}, {"name": "email", "type": "email"}]
    })

    resp = client.post("/api/projects/mock-proj/resources/authors/generate-mocks?count=15")
    assert resp.status_code == 201
    data = resp.json()
    assert data["inserted"] == 15
    assert len(data["rows"]) == 15
    assert "@" in data["rows"][0]["email"]

    # Invalid count error
    bad_resp = client.post("/api/projects/mock-proj/resources/authors/generate-mocks?count=0")
    assert bad_resp.status_code == 400


def test_api_export_json_and_openapi(client):
    client.post("/api/projects", json={"slug": "export-proj"})
    client.post("/api/projects/export-proj/resources", json={
        "name": "posts",
        "columns": [{"name": "title", "type": "text"}]
    })

    r1 = client.get("/api/projects/export-proj/export/json")
    assert r1.status_code == 200
    assert r1.json()["slug"] == "export-proj"

    r2 = client.get("/api/projects/export-proj/export/openapi")
    assert r2.status_code == 200
    assert r2.json()["openapi"] == "3.0.0"


def test_api_import_json_and_openapi(client):
    payload_json = {
        "slug": "imported-proj",
        "resources": [
            {
                "name": "tags",
                "columns": [{"name": "tag_name", "type": "text"}],
                "data": [{"tag_name": "tech"}, {"tag_name": "news"}]
            }
        ]
    }
    r1 = client.post("/api/projects/imported-proj/import/json", json=payload_json)
    assert r1.status_code == 200

    r2 = client.get("/api/imported-proj/tags")
    assert r2.status_code == 200
    assert len(r2.json()) == 2

    # OpenAPI import
    oas_spec = {
        "openapi": "3.0.0",
        "components": {
            "schemas": {
                "Comment": {
                    "properties": {
                        "text": {"type": "string"}
                    }
                }
            }
        }
    }
    r3 = client.post("/api/projects/imported-proj/import/openapi", json=oas_spec)
    assert r3.status_code == 200

    r4 = client.get("/api/imported-proj/comments")
    assert r4.status_code == 200


def test_web_data_explorer_and_inline_actions(client):
    client.post("/projects", data={"slug": "ui-proj"})
    client.post("/projects/ui-proj/resources", data={
        "name": "members",
        "column_name": ["username", "email"],
        "column_type": ["text", "email"],
    })

    # Generate mocks via UI
    resp = client.post("/projects/ui-proj/resources/members/generate-mocks", data={"count": 5})
    assert resp.status_code == 200
    assert "members" in resp.text
    assert "Data Explorer" in resp.text

    # Search in Data Explorer
    resp_search = client.get("/projects/ui-proj/data?resource=members&q=nonexistent123xyz")
    assert resp_search.status_code == 200
    assert "No records found" in resp_search.text

    # Get data tab with HTMX target
    resp_tab = client.get(
        "/projects/ui-proj?tab=data",
        headers={"hx-request": "true", "hx-target": "workspace-tab-content"},
    )
    assert resp_tab.status_code == 200
    assert "Data Explorer" in resp_tab.text

    # Inline edit
    resp_edit = client.post(
        "/projects/ui-proj/resources/members/rows/1/edit",
        data={"username": "alice_updated", "email": "alice@example.com"}
    )
    assert resp_edit.status_code == 200
    assert "alice_updated" in resp_edit.text

    # Inline delete
    resp_del = client.delete("/projects/ui-proj/resources/members/rows/1")
    assert resp_del.status_code == 200

    # Export endpoints in Web UI
    resp_exp_json = client.get("/projects/ui-proj/export/json")
    assert resp_exp_json.status_code == 200
    assert resp_exp_json.json()["slug"] == "ui-proj"

    resp_exp_oas = client.get("/projects/ui-proj/export/openapi")
    assert resp_exp_oas.status_code == 200
    assert resp_exp_oas.json()["openapi"] == "3.0.0"

    # Import file via Web UI (JSON)
    import_data = json.dumps({
        "slug": "ui-proj",
        "resources": [{"name": "roles", "columns": [{"name": "role_name", "type": "text"}]}]
    }).encode("utf-8")
    
    resp_upload = client.post(
        "/projects/ui-proj/import",
        files={"file": ("import.json", io.BytesIO(import_data), "application/json")},
        data={"format": "auto"}
    )
    assert resp_upload.status_code == 200
    assert "roles" in resp_upload.text

    # Import file via Web UI (OpenAPI)
    openapi_upload_data = json.dumps({
        "openapi": "3.0.0",
        "components": {
            "schemas": {
                "Profile": {
                    "properties": {
                        "bio": {"type": "string"}
                    }
                }
            }
        }
    }).encode("utf-8")
    resp_upload_oas = client.post(
        "/projects/ui-proj/import",
        files={"file": ("openapi.json", io.BytesIO(openapi_upload_data), "application/json")},
        data={"format": "openapi"}
    )
    assert resp_upload_oas.status_code == 200
    assert "profiles" in resp_upload_oas.text

    # Import invalid file error
    resp_bad_upload = client.post(
        "/projects/ui-proj/import",
        files={"file": ("bad.json", io.BytesIO(b"{invalid"), "application/json")},
        data={"format": "auto"}
    )
    assert resp_bad_upload.status_code == 422
    assert "Import error" in resp_bad_upload.text


def test_import_resource_json_data_direct(client):
    app = client.app
    db = app.state.db
    project = db.create_project("json-data-proj")
    res = db.create_resource(project["id"], "customers", [{"name": "name", "type": "text"}, {"name": "city", "type": "text"}])

    # 1. Import list of dicts
    data_list = [
        {"name": "Alice", "city": "São Paulo"},
        {"name": "Bob", "city": "Rio"},
    ]
    inserted = import_resource_json_data(db, project["id"], res["id"], data_list)
    assert len(inserted) == 2
    assert inserted[0]["name"] == "Alice"
    assert inserted[1]["city"] == "Rio"

    # 2. Import single dict
    single_data = {"name": "Charlie", "city": "Curitiba"}
    inserted_single = import_resource_json_data(db, project["id"], res["id"], single_data)
    assert len(inserted_single) == 1
    assert inserted_single[0]["name"] == "Charlie"

    # 3. Import with {"data": [...]}
    wrapped_data = {"data": [{"name": "David", "city": "Belo Horizonte"}]}
    inserted_wrapped = import_resource_json_data(db, project["id"], res["id"], wrapped_data)
    assert len(inserted_wrapped) == 1
    assert inserted_wrapped[0]["name"] == "David"

    # 4. Invalid types
    with pytest.raises(InvalidPayloadError):
        import_resource_json_data(db, project["id"], res["id"], "invalid string")

    with pytest.raises(InvalidPayloadError):
        import_resource_json_data(db, project["id"], res["id"], ["not a dict"])


def test_import_resource_data_web_view(client):
    client.post("/projects", data={"name": "JSON View Proj", "slug": "json-view-proj"})
    client.post("/projects/json-view-proj/resources", data={"name": "products", "column_name": ["title", "price"], "column_type": ["text", "price"]})

    valid_json = json.dumps([
        {"title": "Laptop", "price": 1200.0},
        {"title": "Mouse", "price": 25.5}
    ]).encode("utf-8")

    # Success upload
    resp = client.post(
        "/projects/json-view-proj/resources/products/import-data",
        files={"file": ("products.json", io.BytesIO(valid_json), "application/json")},
    )
    assert resp.status_code == 200
    assert "Laptop" in resp.text
    assert "Mouse" in resp.text

    # Invalid JSON syntax
    resp_invalid_json = client.post(
        "/projects/json-view-proj/resources/products/import-data",
        files={"file": ("products.json", io.BytesIO(b"{bad json syntax"), "application/json")},
    )
    assert resp_invalid_json.status_code == 422
    assert "Invalid JSON file syntax" in resp_invalid_json.text

    # Invalid JSON format (list with non-dict)
    resp_bad_format = client.post(
        "/projects/json-view-proj/resources/products/import-data",
        files={"file": ("products.json", io.BytesIO(b"\"just string\""), "application/json")},
    )
    assert resp_bad_format.status_code == 422
    assert "Import failed" in resp_bad_format.text

