import asyncio
import json
import sys
from pathlib import Path
import time
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request as StarletteRequest

from ..core.errors import ConflictError, InvalidPayloadError
from ..core.faker_generator import generate_mock_records
from ..core.importer_exporter import (
    export_project_json,
    export_project_openapi,
    import_openapi_spec,
    import_project_json,
    import_resource_json_data,
)
from ..core.logs import log_manager
from ..core.validation import sanitize_resource, validate_columns, validate_slug
from ..db.database import Database

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    BASE_DIR = Path(sys._MEIPASS) / "src"
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

web = APIRouter()


def _db(request: Request) -> Database:
    return request.app.state.db


def _is_htmx(request: Request) -> bool:
    return request.headers.get("hx-request") == "true"


@web.get("/events/logs/{project_slug}")
async def stream_project_logs(request: Request, project_slug: str):
    db = _db(request)
    project = db.get_project(project_slug)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_slug}' not found")

    queue = log_manager.subscribe(project_slug)

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    log_event = await asyncio.wait_for(queue.get(), timeout=1.0)
                    row_html = templates.get_template("fragments/log_row.html").render({"log": log_event})
                    single_line_html = "".join(line.strip() for line in row_html.splitlines())
                    yield f"event: message\ndata: {single_line_html}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            log_manager.unsubscribe(project_slug, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@web.post("/projects/{slug}/test-request", response_class=HTMLResponse)
async def execute_test_request(
    request: Request,
    slug: str,
    method: str = Form("GET"),
    path: str = Form(...),
    body: Optional[str] = Form(None),
):
    clean_method = method.upper()
    target_path = path.strip()
    if not target_path.startswith("/"):
        target_path = "/" + target_path

    parsed_body = None
    if body and body.strip():
        try:
            parsed_body = json.loads(body.strip())
        except Exception as e:
            return templates.TemplateResponse(
                request=request,
                name="fragments/test_response.html",
                context={
                    "status_code": 400,
                    "duration_ms": 0,
                    "response_json": json.dumps({"error": f"Invalid JSON body: {str(e)}"}, indent=2),
                },
            )

    start_time = time.perf_counter()
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=request.app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        req_kwargs = {}
        if parsed_body is not None:
            req_kwargs["json"] = parsed_body

        resp = await client.request(clean_method, target_path, **req_kwargs)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        try:
            formatted_json = json.dumps(resp.json(), indent=2)
        except Exception:
            formatted_json = resp.text

        return templates.TemplateResponse(
            request=request,
            name="fragments/test_response.html",
            context={
                "status_code": resp.status_code,
                "duration_ms": duration_ms,
                "response_json": formatted_json,
            },
        )


@web.get("/", response_class=HTMLResponse)
@web.get("/projects", response_class=HTMLResponse)
async def get_projects(request: Request, q: Optional[str] = None):
    db = _db(request)
    projects = db.list_projects()
    if q:
        query = q.strip().lower()
        projects = [p for p in projects if query in p["slug"].lower()]

    if _is_htmx(request) and request.headers.get("hx-target") == "projects-list-container":
        return templates.TemplateResponse(
            request=request,
            name="fragments/projects_list.html",
            context={"projects": projects},
        )

    return templates.TemplateResponse(
        request=request,
        name="projects.html",
        context={"projects": projects, "q": q or ""},
    )


@web.post("/projects")
async def create_project_form(request: Request, slug: str = Form(...)):
    db = _db(request)
    try:
        validated_slug = validate_slug(slug.strip())
        db.create_project(validated_slug)
    except (InvalidPayloadError, ConflictError) as exc:
        if _is_htmx(request):
            return HTMLResponse(
                f'<div class="error">{str(exc)}</div>',
                status_code=422,
            )
        projects = db.list_projects()
        return templates.TemplateResponse(
            request=request,
            name="projects.html",
            context={"projects": projects, "error": str(exc)},
            status_code=422,
        )

    workspace_url = f"/projects/{validated_slug}"
    if _is_htmx(request):
        response = Response(status_code=200)
        response.headers["HX-Redirect"] = workspace_url
        return response

    return RedirectResponse(url=workspace_url, status_code=303)


@web.get("/projects/{slug}/edit", response_class=HTMLResponse)
async def get_project_edit_view(request: Request, slug: str):
    db = _db(request)
    project = db.get_project(slug)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")
    return templates.TemplateResponse(
        request=request,
        name="fragments/project_edit_card.html",
        context={"project": project},
    )


@web.get("/projects/{slug}/cancel", response_class=HTMLResponse)
async def get_project_cancel_view(request: Request, slug: str):
    db = _db(request)
    project = db.get_project(slug)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")
    return templates.TemplateResponse(
        request=request,
        name="fragments/project_card.html",
        context={"project": project},
    )


@web.post("/projects/{slug}/edit", response_class=HTMLResponse)
async def edit_project_form(request: Request, slug: str, new_slug: Optional[str] = Form(None)):
    db = _db(request)
    project = db.get_project(slug)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")

    form_data = await request.form()
    input_slug = form_data.get("slug") or new_slug or ""
    error = None
    updated_project = None

    try:
        validated_slug = validate_slug(input_slug.strip())
        updated_project = db.update_project(project["id"], validated_slug)
    except (InvalidPayloadError, ConflictError) as exc:
        error = str(exc)

    if error or not updated_project:
        return templates.TemplateResponse(
            request=request,
            name="fragments/project_edit_card.html",
            context={
                "project": project,
                "new_slug": input_slug,
                "error": error or "Update failed",
            },
            status_code=422 if error else 400,
        )

    return templates.TemplateResponse(
        request=request,
        name="fragments/project_card.html",
        context={"project": updated_project},
    )


@web.post("/projects/{slug}/delete", response_class=HTMLResponse)
@web.delete("/projects/{slug}", response_class=HTMLResponse)
async def delete_project_view(request: Request, slug: str):
    db = _db(request)
    project = db.get_project(slug)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")

    db.delete_project(project["id"])
    projects = db.list_projects()
    return templates.TemplateResponse(
        request=request,
        name="fragments/projects_list.html",
        context={"projects": projects},
    )


@web.get("/projects/{slug}", response_class=HTMLResponse)
async def get_workspace(request: Request, slug: str, tab: str = "endpoints", resource: Optional[str] = None, q: Optional[str] = None):
    db = _db(request)
    project = db.get_project(slug)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")

    resources = db.list_resources(project["id"])
    active_tab = tab if tab in ("endpoints", "schema", "data", "tester", "auth", "logs") else "endpoints"

    selected_resource = None
    rows = []
    logs = []
    auth = {}
    api_keys = []

    if active_tab == "logs":
        logs = log_manager.get_history(slug)
    elif active_tab == "auth":
        auth = db.get_project_auth(project["id"])
        api_keys = db.list_api_keys(project["id"])
    elif active_tab == "data" and resources:
        if resource:
            selected_resource = next((r for r in resources if r["name"] == resource), None)
        if not selected_resource:
            selected_resource = resources[0]

        all_rows = db.list_rows(project["id"], selected_resource["id"])
        if q:
            query = q.strip().lower()
            rows = [
                row for row in all_rows
                if any(query in str(v).lower() for k, v in row.items() if k != "id")
            ]
        else:
            rows = all_rows

    context = {
        "project": project,
        "resources": resources,
        "active_tab": active_tab,
        "selected_resource": selected_resource,
        "rows": rows,
        "logs": logs,
        "auth": auth,
        "api_keys": api_keys,
        "q": q or "",
    }

    if _is_htmx(request) and request.headers.get("hx-target") == "workspace-tab-content":
        tab_templates = {
            "endpoints": "fragments/tab_endpoints.html",
            "schema": "fragments/tab_schema.html",
            "data": "fragments/tab_data.html",
            "tester": "fragments/tab_tester.html",
            "auth": "fragments/tab_auth.html",
            "logs": "fragments/tab_logs.html",
        }
        template_name = tab_templates.get(active_tab, "fragments/tab_endpoints.html")
        return templates.TemplateResponse(
            request=request,
            name=template_name,
            context=context,
        )

    return templates.TemplateResponse(
        request=request,
        name="workspace.html",
        context=context,
    )


@web.get("/projects/{slug}/data", response_class=HTMLResponse)
async def get_project_data(request: Request, slug: str, resource: Optional[str] = None, q: Optional[str] = None):
    return await get_workspace(request, slug=slug, tab="data", resource=resource, q=q)


@web.post("/projects/{slug}/resources/{resource}/generate-mocks", response_class=HTMLResponse)
async def generate_mocks_view(request: Request, slug: str, resource: str, count: int = Form(10)):
    db = _db(request)
    project = db.get_project(slug)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")
    res = db.get_resource(project["id"], resource)
    if not res:
        raise HTTPException(status_code=404, detail=f"Resource '{resource}' not found")

    mock_count = min(max(count, 1), 100)
    generated = generate_mock_records(res["columns"], count=mock_count)
    for record in generated:
        db.insert_row(project["id"], res["id"], record)

    return await get_workspace(request, slug=slug, tab="data", resource=resource)


@web.post("/projects/{slug}/resources/{resource}/import-data", response_class=HTMLResponse)
async def import_resource_data_view(
    request: Request,
    slug: str,
    resource: str,
    file: UploadFile = File(...),
):
    db = _db(request)
    project = db.get_project(slug)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")
    res = db.get_resource(project["id"], resource)
    if not res:
        raise HTTPException(status_code=404, detail=f"Resource '{resource}' not found")

    content = await file.read()
    error = None
    try:
        text = content.decode("utf-8")
        data = json.loads(text)
        import_resource_json_data(db, project["id"], res["id"], data)
    except json.JSONDecodeError:
        error = "Invalid JSON file syntax"
    except Exception as exc:
        error = f"Import failed: {str(exc)}"

    resources = db.list_resources(project["id"])
    rows = db.list_rows(project["id"], res["id"])
    context = {
        "project": project,
        "resources": resources,
        "active_tab": "data",
        "selected_resource": res,
        "rows": rows,
        "error": error,
    }
    return templates.TemplateResponse(
        request=request,
        name="fragments/tab_data.html",
        context=context,
        status_code=422 if error else 200,
    )


@web.post("/projects/{slug}/resources/{resource}/rows/{row_id}/edit", response_class=HTMLResponse)
async def inline_edit_row(request: Request, slug: str, resource: str, row_id: int):
    db = _db(request)
    project = db.get_project(slug)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")
    res = db.get_resource(project["id"], resource)
    if not res:
        raise HTTPException(status_code=404, detail=f"Resource '{resource}' not found")

    form_data = await request.form()
    data = {}
    for col in res["columns"]:
        col_name = col["name"]
        if col_name in form_data:
            val = form_data.get(col_name)
            data[col_name] = val

    updated = db.update_row(project["id"], res["id"], row_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Row {row_id} not found")

    return templates.TemplateResponse(
        request=request,
        name="fragments/row_tr.html",
        context={"project": project, "selected_resource": res, "row": updated},
    )


@web.delete("/projects/{slug}/resources/{resource}/rows/{row_id}", response_class=HTMLResponse)
async def inline_delete_row(request: Request, slug: str, resource: str, row_id: int):
    db = _db(request)
    project = db.get_project(slug)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")
    res = db.get_resource(project["id"], resource)
    if not res:
        raise HTTPException(status_code=404, detail=f"Resource '{resource}' not found")

    db.delete_row(project["id"], res["id"], row_id)
    return HTMLResponse("")


@web.get("/projects/{slug}/export/json")
async def export_json_view(request: Request, slug: str):
    db = _db(request)
    data = export_project_json(db, slug)
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": f'attachment; filename="{slug}-export.json"'},
    )


@web.get("/projects/{slug}/export/openapi")
async def export_openapi_view(request: Request, slug: str):
    db = _db(request)
    data = export_project_openapi(db, slug)
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": f'attachment; filename="{slug}-openapi.json"'},
    )


@web.post("/projects/{slug}/import", response_class=HTMLResponse)
async def import_file_view(request: Request, slug: str, file: UploadFile = File(...), format: str = Form("auto")):
    db = _db(request)
    project = db.get_project(slug)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")

    content = await file.read()
    text = content.decode("utf-8")
    error = None

    try:
        if format == "openapi" or (format == "auto" and ("openapi" in text or "swagger" in text)):
            import_openapi_spec(db, slug, text)
        else:
            data = json.loads(text)
            if "openapi" in data or "swagger" in data:
                import_openapi_spec(db, slug, data)
            else:
                import_project_json(db, data, target_slug=slug)
    except Exception as e:
        error = f"Import error: {str(e)}"

    resources = db.list_resources(project["id"])
    context = {
        "project": project,
        "resources": resources,
        "active_tab": "data",
        "selected_resource": resources[0] if resources else None,
        "rows": db.list_rows(project["id"], resources[0]["id"]) if resources else [],
        "error": error,
    }
    return templates.TemplateResponse(
        request=request,
        name="fragments/tab_data.html",
        context=context,
        status_code=422 if error else 200,
    )



@web.post("/projects/{slug}/endpoints", response_class=HTMLResponse)
async def create_endpoint_form(request: Request, slug: str):
    db = _db(request)
    project = db.get_project(slug)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")

    form_data = await request.form()
    raw_name = form_data.get("name", "")
    column_names = form_data.getlist("column_name")
    column_types = form_data.getlist("column_type")

    columns = []
    for i, col_name in enumerate(column_names):
        col_type = column_types[i] if i < len(column_types) else "text"
        columns.append({"name": col_name.strip(), "type": col_type})

    error = None
    try:
        sanitized_name = sanitize_resource(raw_name)
        validated_cols = validate_columns(columns)
        db.create_resource(project["id"], sanitized_name, validated_cols)
    except (InvalidPayloadError, ConflictError) as exc:
        error = str(exc)

    resources = db.list_resources(project["id"])
    return templates.TemplateResponse(
        request=request,
        name="fragments/tab_endpoints.html",
        context={
            "project": project,
            "resources": resources,
            "error": error,
            "show_add_form": bool(error),
        },
        status_code=422 if error else 200,
    )


@web.get("/projects/{slug}/endpoints/{resource_id}/edit", response_class=HTMLResponse)
async def get_endpoint_edit_form(request: Request, slug: str, resource_id: int):
    db = _db(request)
    project = db.get_project(slug)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")
    res = db.get_resource_by_id(project["id"], resource_id)
    if not res:
        raise HTTPException(status_code=404, detail=f"Endpoint {resource_id} not found")

    return templates.TemplateResponse(
        request=request,
        name="fragments/endpoint_edit_row.html",
        context={"project": project, "res": res},
    )


@web.get("/projects/{slug}/endpoints/{resource_id}/cancel", response_class=HTMLResponse)
async def cancel_endpoint_edit(request: Request, slug: str, resource_id: int):
    db = _db(request)
    project = db.get_project(slug)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")
    res = db.get_resource_by_id(project["id"], resource_id)
    if not res:
        raise HTTPException(status_code=404, detail=f"Endpoint {resource_id} not found")

    return templates.TemplateResponse(
        request=request,
        name="fragments/endpoint_row.html",
        context={"project": project, "res": res},
    )


@web.put("/projects/{slug}/endpoints/{resource_id}", response_class=HTMLResponse)
async def update_endpoint_form(request: Request, slug: str, resource_id: int):
    db = _db(request)
    project = db.get_project(slug)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")
    res = db.get_resource_by_id(project["id"], resource_id)
    if not res:
        raise HTTPException(status_code=404, detail=f"Endpoint {resource_id} not found")

    form_data = await request.form()
    raw_name = form_data.get("name", "")
    column_names = form_data.getlist("column_name")
    column_types = form_data.getlist("column_type")

    columns = []
    for i, col_name in enumerate(column_names):
        col_type = column_types[i] if i < len(column_types) else "text"
        columns.append({"name": col_name.strip(), "type": col_type})

    error = None
    updated = None
    try:
        sanitized_name = sanitize_resource(raw_name)
        validated_cols = validate_columns(columns)
        updated = db.update_resource(project["id"], resource_id, sanitized_name, validated_cols)
    except (InvalidPayloadError, ConflictError) as exc:
        error = str(exc)

    if error or not updated:
        return templates.TemplateResponse(
            request=request,
            name="fragments/endpoint_edit_row.html",
            context={
                "project": project,
                "res": {"id": resource_id, "name": raw_name, "columns": columns},
                "error": error or "Update failed",
            },
            status_code=422 if error else 400,
        )

    return templates.TemplateResponse(
        request=request,
        name="fragments/endpoint_row.html",
        context={"project": project, "res": updated},
    )


@web.delete("/projects/{slug}/endpoints/{resource_id}", response_class=HTMLResponse)
async def delete_endpoint_view(request: Request, slug: str, resource_id: int):
    db = _db(request)
    project = db.get_project(slug)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")
    if not db.delete_resource(project["id"], resource_id):
        raise HTTPException(status_code=404, detail=f"Endpoint {resource_id} not found")

    return HTMLResponse("")


@web.post("/projects/{slug}/resources", response_class=HTMLResponse)
async def create_resource_form(request: Request, slug: str):
    db = _db(request)
    project = db.get_project(slug)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")

    form_data = await request.form()
    raw_name = form_data.get("name", "")
    column_names = form_data.getlist("column_name")
    column_types = form_data.getlist("column_type")

    columns = []
    for i, col_name in enumerate(column_names):
        col_type = column_types[i] if i < len(column_types) else "text"
        columns.append({"name": col_name.strip(), "type": col_type})

    error = None
    try:
        sanitized_name = sanitize_resource(raw_name)
        validated_cols = validate_columns(columns)
        db.create_resource(project["id"], sanitized_name, validated_cols)
    except (InvalidPayloadError, ConflictError) as exc:
        error = str(exc)

    resources = db.list_resources(project["id"])
    return templates.TemplateResponse(
        request=request,
        name="fragments/tab_schema.html",
        context={
            "project": project,
            "resources": resources,
            "error": error,
        },
        status_code=422 if error else 200,
    )


@web.post("/projects/{slug}/auth/settings", response_class=HTMLResponse)
async def update_auth_settings_view(
    request: Request,
    slug: str,
    auth_type: str = Form("none"),
    basic_username: Optional[str] = Form(""),
    basic_password: Optional[str] = Form(""),
):
    db = _db(request)
    project = db.get_project(slug)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")

    error = None
    if auth_type == "basic":
        if not basic_username or not basic_username.strip() or not basic_password or not basic_password.strip():
            error = "Username and Password are required when Basic Auth is selected."

    if not error:
        db.update_project_auth(
            project["id"],
            auth_type=auth_type,
            basic_username=(basic_username or "").strip(),
            basic_password=(basic_password or "").strip(),
        )

    auth = db.get_project_auth(project["id"])
    api_keys = db.list_api_keys(project["id"])
    return templates.TemplateResponse(
        request=request,
        name="fragments/tab_auth.html",
        context={
            "project": project,
            "auth": auth,
            "api_keys": api_keys,
            "error": error,
            "success": "Authentication settings updated successfully!" if not error else None,
        },
        status_code=422 if error else 200,
    )


@web.post("/projects/{slug}/auth/keys", response_class=HTMLResponse)
async def create_api_key_view(request: Request, slug: str):
    db = _db(request)
    project = db.get_project(slug)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")

    form_data = await request.form()
    name = (form_data.get("name") or "").strip()
    scopes = form_data.getlist("scopes")

    key_error = None
    if not name:
        key_error = "API Key name is required."
    elif not scopes:
        key_error = "At least one scope must be selected."
    else:
        try:
            db.create_api_key(project["id"], name=name, scopes=scopes)
        except Exception as e:
            key_error = f"Error creating API Key: {str(e)}"

    auth = db.get_project_auth(project["id"])
    api_keys = db.list_api_keys(project["id"])
    return templates.TemplateResponse(
        request=request,
        name="fragments/tab_auth.html",
        context={
            "project": project,
            "auth": auth,
            "api_keys": api_keys,
            "key_error": key_error,
            "success": "API Key generated successfully!" if not key_error else None,
        },
        status_code=422 if key_error else 200,
    )


@web.delete("/projects/{slug}/auth/keys/{key_id}", response_class=HTMLResponse)
async def delete_api_key_view(request: Request, slug: str, key_id: int):
    db = _db(request)
    project = db.get_project(slug)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")

    if not db.delete_api_key(project["id"], key_id):
        raise HTTPException(status_code=404, detail=f"API Key {key_id} not found")

    auth = db.get_project_auth(project["id"])
    api_keys = db.list_api_keys(project["id"])
    return templates.TemplateResponse(
        request=request,
        name="fragments/tab_auth.html",
        context={
            "project": project,
            "auth": auth,
            "api_keys": api_keys,
            "success": "API Key revoked successfully!",
        },
    )


@web.get("/fragments/column-row", response_class=HTMLResponse)
async def get_column_row(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="fragments/column_row.html",
        context={},
    )
