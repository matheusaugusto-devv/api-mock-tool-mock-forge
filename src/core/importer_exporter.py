import json
from typing import Any
import yaml

from .errors import InvalidPayloadError
from .validation import sanitize_resource, validate_columns, validate_slug
from ..db.database import Database


def export_project_json(db: Database, project_slug: str) -> dict:
    project = db.get_project(project_slug)
    if not project:
        raise InvalidPayloadError(f"Project '{project_slug}' not found")

    resources = db.list_resources(project["id"])
    export_resources = []
    for res in resources:
        rows = db.list_rows(project["id"], res["id"])
        # Strip internal id from row data if desired, or keep it
        cleaned_rows = [{k: v for k, v in row.items() if k != "id"} for row in rows]
        export_resources.append({
            "name": res["name"],
            "columns": res["columns"],
            "data": cleaned_rows,
        })

    return {
        "slug": project["slug"],
        "resources": export_resources,
    }


def import_resource_json_data(db: Database, project_id: int, resource_id: int, data: Any) -> list[dict]:
    if isinstance(data, dict):
        # Support either a single object or {"data": [...]} wrapper
        if "data" in data and isinstance(data["data"], list):
            items = data["data"]
        else:
            items = [data]
    elif isinstance(data, list):
        items = data
    else:
        raise InvalidPayloadError("JSON data must be a list of objects or a single JSON object")

    inserted = []
    for item in items:
        if not isinstance(item, dict):
            raise InvalidPayloadError("Each item in JSON data must be an object")
        row_data = {k: v for k, v in item.items() if k != "id"}
        saved = db.insert_row(project_id, resource_id, row_data)
        inserted.append(saved)

    return inserted


def import_project_json(db: Database, data: dict, target_slug: str | None = None) -> dict:
    if not isinstance(data, dict):
        raise InvalidPayloadError("JSON payload must be an object")

    raw_slug = target_slug or data.get("slug")
    slug = validate_slug(raw_slug)

    project = db.get_project(slug)
    if not project:
        project = db.create_project(slug)

    resources_data = data.get("resources", [])
    if not isinstance(resources_data, list):
        raise InvalidPayloadError("'resources' must be a list")

    for res_dict in resources_data:
        if not isinstance(res_dict, dict) or not res_dict.get("name"):
            continue
        res_name = sanitize_resource(res_dict["name"])
        cols = validate_columns(res_dict.get("columns", [{"name": "name", "type": "text"}]))
        
        # Check if resource already exists
        existing = db.get_resource(project["id"], res_name)
        if not existing:
            created_res = db.create_resource(project["id"], res_name, cols)
            res_id = created_res["id"]
        else:
            res_id = existing["id"]

        rows = res_dict.get("data", [])
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    db.insert_row(project["id"], res_id, row)

    return project


def export_project_openapi(db: Database, project_slug: str) -> dict:
    project = db.get_project(project_slug)
    if not project:
        raise InvalidPayloadError(f"Project '{project_slug}' not found")

    resources = db.list_resources(project["id"])
    paths = {}
    schemas = {}

    for res in resources:
        name = res["name"]
        schema_name = "".join([part.capitalize() for part in name.split("-")]).rstrip("s") or name
        properties = {}
        for col in res["columns"]:
            c_type = col.get("type", "text").lower()
            if c_type in ("number", "integer", "int"):
                o_type = "integer"
            elif c_type in ("float", "price"):
                o_type = "number"
            elif c_type in ("boolean", "bool"):
                o_type = "boolean"
            else:
                o_type = "string"
            properties[col["name"]] = {"type": o_type}

        schemas[schema_name] = {
            "type": "object",
            "properties": properties,
        }

        paths[f"/api/{project_slug}/{name}"] = {
            "get": {
                "summary": f"List {name}",
                "responses": {
                    "200": {
                        "description": f"List of {name}",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {"$ref": f"#/components/schemas/{schema_name}"},
                                }
                            }
                        },
                    }
                },
            },
            "post": {
                "summary": f"Create {name}",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {"$ref": f"#/components/schemas/{schema_name}"}
                        }
                    }
                },
                "responses": {"201": {"description": "Created"}},
            },
        }

    return {
        "openapi": "3.0.0",
        "info": {
            "title": f"Mock API - {project_slug}",
            "version": "1.0.0",
        },
        "paths": paths,
        "components": {
            "schemas": schemas,
        },
    }


def parse_openapi_spec(spec_data: str | dict) -> list[dict]:
    """Parse OpenAPI 3.0 YAML or JSON into resources schema structure."""
    if isinstance(spec_data, str):
        try:
            parsed = json.loads(spec_data)
        except Exception:
            try:
                parsed = yaml.safe_load(spec_data)
            except Exception as e:
                raise InvalidPayloadError(f"Invalid OpenAPI spec format: {e}")
    else:
        parsed = spec_data

    if not isinstance(parsed, dict):
        raise InvalidPayloadError("OpenAPI spec must be an object")

    resources = []
    
    # Check components.schemas first
    components_schemas = parsed.get("components", {}).get("schemas", {})
    if isinstance(components_schemas, dict) and components_schemas:
        for schema_name, schema_body in components_schemas.items():
            if not isinstance(schema_body, dict):
                continue
            properties = schema_body.get("properties", {})
            columns = []
            for prop_name, prop_def in properties.items():
                p_type = prop_def.get("type", "string") if isinstance(prop_def, dict) else "string"
                if p_type == "integer":
                    col_type = "number"
                elif p_type == "number":
                    col_type = "float"
                elif p_type == "boolean":
                    col_type = "boolean"
                else:
                    col_type = prop_def.get("format", "text") if isinstance(prop_def, dict) else "text"
                    if col_type not in ("email", "date", "datetime", "uuid", "url"):
                        col_type = "text"
                columns.append({"name": prop_name, "type": col_type})
            
            if not columns:
                columns = [{"name": "name", "type": "text"}]

            res_name = sanitize_resource(schema_name)
            resources.append({
                "name": res_name,
                "columns": validate_columns(columns),
            })

    # Also check paths if schemas was empty or to complement
    paths = parsed.get("paths", {})
    if isinstance(paths, dict):
        for path_key in paths.keys():
            # e.g. /users or /api/users
            parts = [p for p in path_key.strip("/").split("/") if p and not p.startswith("{")]
            if parts:
                res_candidate = parts[-1]
                try:
                    res_name = sanitize_resource(res_candidate)
                    if not any(r["name"] == res_name for r in resources):
                        resources.append({
                            "name": res_name,
                            "columns": [{"name": "name", "type": "text"}],
                        })
                except Exception:
                    pass

    return resources


def import_openapi_spec(db: Database, project_slug: str, spec_data: str | dict) -> dict:
    slug = validate_slug(project_slug)
    project = db.get_project(slug)
    if not project:
        project = db.create_project(slug)

    resources = parse_openapi_spec(spec_data)
    for res in resources:
        existing = db.get_resource(project["id"], res["name"])
        if not existing:
            db.create_resource(project["id"], res["name"], res["columns"])

    return project
