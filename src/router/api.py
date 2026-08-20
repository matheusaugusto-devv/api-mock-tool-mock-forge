import base64
from typing import Any
import json

from fastapi import APIRouter, Body, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import JSONResponse, Response

from ..core.auth import generate_bearer_token, has_scope, verify_bearer_token
from ..core.errors import InvalidPayloadError, ResourceNotFoundError
from ..core.faker_generator import generate_mock_records
from ..core.importer_exporter import (
    export_project_json,
    export_project_openapi,
    import_openapi_spec,
    import_project_json,
    parse_openapi_spec,
)
from ..core.validation import sanitize_resource, validate_columns, validate_slug
from ..db.database import Database

api = APIRouter(prefix="/api")


def _db(request: Request) -> Database:
    return request.app.state.db


def _authenticate_request(request: Request, project: dict, required_scope: str | None = None) -> None:
    db = _db(request)
    auth_settings = db.get_project_auth(project["id"])
    auth_type = auth_settings.get("auth_type", "none")

    if auth_type == "none" or not auth_type:
        return

    auth_header = request.headers.get("Authorization", "")
    api_key_header = request.headers.get("X-API-Key", "")

    if auth_type == "api_key":
        key = api_key_header
        if not key and auth_header.startswith("ApiKey "):
            key = auth_header[7:].strip()
        elif not key and auth_header.startswith("Bearer ") and not key:
            key = auth_header[7:].strip()
        
        if not key:
            raise HTTPException(status_code=401, detail="API key required", headers={"WWW-Authenticate": "ApiKey"})
        
        key_record = db.get_api_key(key)
        if not key_record or key_record["project_id"] != project["id"]:
            raise HTTPException(status_code=401, detail="Invalid API key", headers={"WWW-Authenticate": "ApiKey"})
        
        if required_scope and not has_scope(required_scope, key_record.get("scopes", [])):
            raise HTTPException(status_code=403, detail=f"Insufficient permissions: required scope '{required_scope}'")
        return

    if auth_type == "basic":
        if not auth_header.startswith("Basic "):
            raise HTTPException(status_code=401, detail="Basic authentication required", headers={"WWW-Authenticate": 'Basic realm="Project API"'})
        
        try:
            encoded_creds = auth_header[6:].strip()
            decoded = base64.b64decode(encoded_creds).decode("utf-8")
            username, password = decoded.split(":", 1)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid Basic auth credentials", headers={"WWW-Authenticate": 'Basic realm="Project API"'})
        
        if username != auth_settings.get("basic_username", "") or password != auth_settings.get("basic_password", ""):
            raise HTTPException(status_code=401, detail="Invalid Basic auth credentials", headers={"WWW-Authenticate": 'Basic realm="Project API"'})
        return

    if auth_type == "bearer":
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Bearer token required", headers={"WWW-Authenticate": "Bearer"})
        
        token = auth_header[7:].strip()
        payload = verify_bearer_token(token, auth_settings.get("secret_key", ""))
        if not payload or payload.get("slug") != project["slug"]:
            raise HTTPException(status_code=401, detail="Invalid or expired Bearer token", headers={"WWW-Authenticate": "Bearer"})
        
        if required_scope and not has_scope(required_scope, payload.get("scopes", [])):
            raise HTTPException(status_code=403, detail=f"Insufficient permissions: required scope '{required_scope}'")
        return


def _get_project_and_authenticate(request: Request, project_slug: str, required_scope: str | None = None) -> dict:
    db = _db(request)
    project = db.get_project(project_slug)
    if not project:
        raise ResourceNotFoundError(f"Project '{project_slug}' not found")
    _authenticate_request(request, project, required_scope)
    return project


def _get_resource(db: Database, project_slug: str, resource: str, request: Request | None = None, required_scope: str | None = None) -> dict:
    project = db.get_project(project_slug)
    if not project:
        raise ResourceNotFoundError(f"Project '{project_slug}' not found")
    if request:
        _authenticate_request(request, project, required_scope)
    res = db.get_resource(project["id"], resource)
    if not res:
        raise ResourceNotFoundError(f"Resource '{resource}' not found in project '{project_slug}'")
    return res



def _check_payload(resource: dict, data: dict) -> None:
    allowed = {column["name"] for column in resource["columns"]}
    unknown = set(data) - allowed
    if unknown:
        raise InvalidPayloadError(f"Unknown column(s): {', '.join(sorted(unknown))}")


def _eq(value: Any, expected: str) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return str(value).lower() == str(expected).lower()
    try:
        return value == type(value)(expected)
    except (TypeError, ValueError):
        return str(value) == expected


def _apply_filters(rows: list[dict], params) -> list[dict]:
    filters = {key: value for key, value in params.items() if not key.startswith("_")}
    if not filters:
        return rows
    return [row for row in rows if all(_eq(row.get(key), value) for key, value in filters.items())]


def _sort_key(value: Any) -> tuple:
    if value is None:
        return (2, "")
    if isinstance(value, bool):
        return (1, str(value).lower())
    if isinstance(value, (int, float)):
        return (0, value)
    return (1, str(value).lower())


def _apply_sort(rows: list[dict], params) -> list[dict]:
    sort = params.get("_sort")
    if not sort:
        return rows
    order = params.get("_order", "asc")
    if order not in ("asc", "desc"):
        raise InvalidPayloadError("'_order' must be 'asc' or 'desc'")
    return sorted(rows, key=lambda row: _sort_key(row.get(sort)), reverse=(order == "desc"))


def _to_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        raise InvalidPayloadError(f"Invalid integer value: {value!r}")


def _apply_pagination(request: Request, response: Response, rows: list[dict]) -> list[dict]:
    params = request.query_params
    if "_page" not in params and "_limit" not in params:
        return rows
    page = _to_int(params.get("_page"), 1)
    limit = _to_int(params.get("_limit"), len(rows))
    if page < 1 or limit < 1:
        raise InvalidPayloadError("'_page' and '_limit' must be positive integers")
    start = (page - 1) * limit
    response.headers["X-Total-Count"] = str(len(rows))
    return rows[start : start + limit]


@api.post("/projects", status_code=201)
def create_project(request: Request, body: dict = Body(...)):
    return _db(request).create_project(validate_slug(body.get("slug")))


@api.get("/projects")
def list_projects(request: Request):
    return _db(request).list_projects()


@api.post("/projects/{slug}/resources", status_code=201)
def create_resource(request: Request, slug: str, body: dict = Body(...)):
    db = _db(request)
    project = db.get_project(slug)
    if not project:
        raise ResourceNotFoundError(f"Project '{slug}' not found")
    name = sanitize_resource(body.get("name"))
    columns = validate_columns(body.get("columns"))
    return db.create_resource(project["id"], name, columns)


@api.get("/projects/{slug}/resources")
def list_resources(request: Request, slug: str):
    db = _db(request)
    project = db.get_project(slug)
    if not project:
        raise ResourceNotFoundError(f"Project '{slug}' not found")
    return db.list_resources(project["id"])


@api.get("/projects/{slug}/resources/{resource_id}")
def get_resource(request: Request, slug: str, resource_id: int):
    db = _db(request)
    project = db.get_project(slug)
    if not project:
        raise ResourceNotFoundError(f"Project '{slug}' not found")
    res = db.get_resource_by_id(project["id"], resource_id)
    if not res:
        raise ResourceNotFoundError(f"Resource {resource_id} not found in project '{slug}'")
    return res


@api.put("/projects/{slug}/resources/{resource_id}")
def update_resource_api(request: Request, slug: str, resource_id: int, body: dict = Body(...)):
    db = _db(request)
    project = db.get_project(slug)
    if not project:
        raise ResourceNotFoundError(f"Project '{slug}' not found")
    name = sanitize_resource(body.get("name"))
    columns = validate_columns(body.get("columns"))
    res = db.update_resource(project["id"], resource_id, name, columns)
    if not res:
        raise ResourceNotFoundError(f"Resource {resource_id} not found in project '{slug}'")
    return res


@api.delete("/projects/{slug}/resources/{resource_id}", status_code=204)
def delete_resource_api(request: Request, slug: str, resource_id: int):
    db = _db(request)
    project = db.get_project(slug)
    if not project:
        raise ResourceNotFoundError(f"Project '{slug}' not found")
    if not db.delete_resource(project["id"], resource_id):
        raise ResourceNotFoundError(f"Resource {resource_id} not found in project '{slug}'")
    return Response(status_code=204)


@api.post("/{project_slug}/auth")
def authenticate_project_token(request: Request, project_slug: str, body: dict = Body(default={})):
    db = _db(request)
    project = db.get_project(project_slug)
    if not project:
        raise ResourceNotFoundError(f"Project '{project_slug}' not found")
    
    auth_settings = db.get_project_auth(project["id"])

    api_key_str = (body.get("apiKey") or body.get("api_key")) if isinstance(body, dict) else None
    if not api_key_str:
        api_key_str = request.headers.get("X-API-Key")
    if not api_key_str:
        auth_hdr = request.headers.get("Authorization", "")
        if auth_hdr.startswith("ApiKey "):
            api_key_str = auth_hdr[7:].strip()

    if not api_key_str:
        raise HTTPException(
            status_code=401,
            detail="API key is required to generate bearer tokens",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    key_record = db.get_api_key(api_key_str)
    if not key_record or key_record["project_id"] != project["id"]:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    if not has_scope("auth", key_record.get("scopes", [])):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions: API key does not have 'auth' scope",
        )

    token, ttl = generate_bearer_token(
        project_slug=project["slug"],
        api_key_id=key_record["id"],
        secret_key=auth_settings["secret_key"],
        scopes=key_record.get("scopes", []),
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": ttl,
    }


@api.get("/{project_slug}/{resource}")
def list_rows(request: Request, response: Response, project_slug: str, resource: str):
    db = _db(request)
    res = _get_resource(db, project_slug, resource, request=request, required_scope="read")
    rows = db.list_rows(res["project_id"], res["id"])
    rows = _apply_filters(rows, request.query_params)
    rows = _apply_sort(rows, request.query_params)
    rows = _apply_pagination(request, response, rows)
    return rows


@api.post("/{project_slug}/{resource}", status_code=201)
def create_row(request: Request, project_slug: str, resource: str, body: dict = Body(...)):
    db = _db(request)
    res = _get_resource(db, project_slug, resource, request=request, required_scope="write")
    _check_payload(res, body)
    return db.insert_row(res["project_id"], res["id"], body)


@api.get("/{project_slug}/{resource}/{row_id}")
def get_row(request: Request, project_slug: str, resource: str, row_id: int):
    db = _db(request)
    res = _get_resource(db, project_slug, resource, request=request, required_scope="read")
    row = db.get_row(res["project_id"], res["id"], row_id)
    if not row:
        raise ResourceNotFoundError(f"Row {row_id} not found in resource '{resource}'")
    return row


@api.put("/{project_slug}/{resource}/{row_id}")
def replace_row(request: Request, project_slug: str, resource: str, row_id: int, body: dict = Body(...)):
    db = _db(request)
    res = _get_resource(db, project_slug, resource, request=request, required_scope="write")
    _check_payload(res, body)
    row = db.update_row(res["project_id"], res["id"], row_id, body)
    if not row:
        raise ResourceNotFoundError(f"Row {row_id} not found in resource '{resource}'")
    return row


@api.delete("/{project_slug}/{resource}/{row_id}", status_code=204)
def delete_row(request: Request, project_slug: str, resource: str, row_id: int):
    db = _db(request)
    res = _get_resource(db, project_slug, resource, request=request, required_scope="write")
    if not db.delete_row(res["project_id"], res["id"], row_id):
        raise ResourceNotFoundError(f"Row {row_id} not found in resource '{resource}'")
    return Response(status_code=204)


@api.post("/projects/{slug}/resources/{resource}/generate-mocks", status_code=201)
def generate_mocks_api(request: Request, slug: str, resource: str, count: int = 10):
    db = _db(request)
    res = _get_resource(db, slug, resource, request=request, required_scope="write")
    if count < 1 or count > 500:
        raise InvalidPayloadError("Count must be between 1 and 500")
    generated = generate_mock_records(res["columns"], count=count)
    inserted = []
    for record in generated:
        inserted.append(db.insert_row(res["project_id"], res["id"], record))
    return {"inserted": len(inserted), "rows": inserted}


@api.get("/projects/{slug}/export/json")
def export_json_api(request: Request, slug: str):
    _get_project_and_authenticate(request, slug, required_scope="read")
    db = _db(request)
    data = export_project_json(db, slug)
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": f'attachment; filename="{slug}-export.json"'},
    )


@api.get("/projects/{slug}/export/openapi")
def export_openapi_api(request: Request, slug: str):
    _get_project_and_authenticate(request, slug, required_scope="read")
    db = _db(request)
    data = export_project_openapi(db, slug)
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": f'attachment; filename="{slug}-openapi.json"'},
    )


@api.post("/projects/{slug}/import/json", status_code=200)
def import_json_api(request: Request, slug: str, body: dict = Body(...)):
    db = _db(request)
    project = db.get_project(slug)
    if project:
        _authenticate_request(request, project, required_scope="write")
    return import_project_json(db, body, target_slug=slug)


@api.post("/projects/{slug}/import/openapi", status_code=200)
async def import_openapi_api(request: Request, slug: str, body: dict | str = Body(...)):
    db = _db(request)
    project = db.get_project(slug)
    if project:
        _authenticate_request(request, project, required_scope="write")
    return import_openapi_spec(db, slug, body)

