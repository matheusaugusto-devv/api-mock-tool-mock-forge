import unittest
from fastapi.testclient import TestClient

from src.app import create_app


class TestWorkspaceEditAndDelete(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = TestClient(self.app)

    def test_json_api_update_project_success(self):
        self.client.post("/api/projects", json={"slug": "original-slug"})
        # Criar resource e row para garantir preservação dos dados
        self.client.post(
            "/api/projects/original-slug/resources",
            json={"name": "users", "columns": [{"name": "name", "type": "text"}]},
        )
        self.client.post("/api/original-slug/users", json={"name": "Alice"})

        res = self.client.put("/api/projects/original-slug", json={"slug": "renamed-slug"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["slug"], "renamed-slug")

        # Verificar se os dados continuam acessíveis sob o novo slug
        res_rows = self.client.get("/api/renamed-slug/users")
        self.assertEqual(res_rows.status_code, 200)
        self.assertEqual(len(res_rows.json()), 1)
        self.assertEqual(res_rows.json()[0]["name"], "Alice")

    def test_json_api_update_project_duplicate_slug_conflict(self):
        self.client.post("/api/projects", json={"slug": "proj-a"})
        self.client.post("/api/projects", json={"slug": "proj-b"})

        res = self.client.put("/api/projects/proj-a", json={"slug": "proj-b"})
        self.assertEqual(res.status_code, 409)
        self.assertIn("already exists", res.json()["detail"])

    def test_json_api_update_project_invalid_slug(self):
        self.client.post("/api/projects", json={"slug": "valid-slug"})

        res = self.client.put("/api/projects/valid-slug", json={"slug": "Invalid Slug!"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("kebab-case", res.json()["detail"])

    def test_json_api_update_project_not_found(self):
        res = self.client.put("/api/projects/non-existent", json={"slug": "new-slug"})
        self.assertEqual(res.status_code, 404)

    def test_json_api_delete_project_cascade(self):
        self.client.post("/api/projects", json={"slug": "to-delete"})
        self.client.post(
            "/api/projects/to-delete/resources",
            json={"name": "items", "columns": [{"name": "title", "type": "text"}]},
        )
        self.client.post("/api/to-delete/items", json={"title": "Item 1"})

        # Obter DB para verificar cascade
        db = self.app.state.db
        proj = db.get_project("to-delete")
        proj_id = proj["id"]
        res = db.get_resource(proj_id, "items")
        res_id = res["id"]

        del_res = self.client.delete("/api/projects/to-delete")
        self.assertEqual(del_res.status_code, 204)

        # Verificar se o projeto não existe mais
        self.assertIsNone(db.get_project("to-delete"))
        # Verificar cascade no SQLite
        self.assertEqual(len(db.list_resources(proj_id)), 0)
        self.assertEqual(len(db.list_rows(proj_id, res_id)), 0)

        # Rotas devem retornar 404
        get_res = self.client.get("/api/to-delete/items")
        self.assertEqual(get_res.status_code, 404)

    def test_json_api_delete_project_not_found(self):
        res = self.client.delete("/api/projects/non-existent")
        self.assertEqual(res.status_code, 404)

    def test_json_api_auth_protection_on_edit_and_delete(self):
        self.client.post("/api/projects", json={"slug": "auth-proj"})
        db = self.app.state.db
        proj = db.get_project("auth-proj")

        # Configurar auth = api_key
        db.update_project_auth(proj["id"], auth_type="api_key")
        read_key = db.create_api_key(proj["id"], name="Reader", scopes=["read"])["key"]
        admin_key = db.create_api_key(proj["id"], name="Admin", scopes=["admin"])["key"]

        # PUT sem auth -> 401
        res_no_auth = self.client.put("/api/projects/auth-proj", json={"slug": "new-auth-proj"})
        self.assertEqual(res_no_auth.status_code, 401)

        # PUT com chave read (sem admin) -> 403
        res_read = self.client.put(
            "/api/projects/auth-proj",
            json={"slug": "new-auth-proj"},
            headers={"X-API-Key": read_key},
        )
        self.assertEqual(res_read.status_code, 403)

        # PUT com chave admin -> 200
        res_admin = self.client.put(
            "/api/projects/auth-proj",
            json={"slug": "new-auth-proj"},
            headers={"X-API-Key": admin_key},
        )
        self.assertEqual(res_admin.status_code, 200)

        # DELETE com chave read -> 403
        res_del_read = self.client.delete(
            "/api/projects/new-auth-proj",
            headers={"X-API-Key": read_key},
        )
        self.assertEqual(res_del_read.status_code, 403)

        # DELETE com chave admin -> 204
        res_del_admin = self.client.delete(
            "/api/projects/new-auth-proj",
            headers={"X-API-Key": admin_key},
        )
        self.assertEqual(res_del_admin.status_code, 204)

    def test_ui_render_project_card_with_actions(self):
        self.client.post("/api/projects", json={"slug": "ui-project"})
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("ui-project", res.text)
        self.assertIn('hx-get="/projects/ui-project/edit"', res.text)
        self.assertIn('hx-post="/projects/ui-project/delete"', res.text)
        self.assertIn("hx-confirm=\"Are you sure you want to delete workspace 'ui-project'?\"", res.text)

    def test_ui_get_edit_and_cancel_form(self):
        self.client.post("/api/projects", json={"slug": "ui-edit-cancel"})

        # GET edit form
        res_edit = self.client.get(
            "/projects/ui-edit-cancel/edit",
            headers={"hx-request": "true"},
        )
        self.assertEqual(res_edit.status_code, 200)
        self.assertIn("hx-post=\"/projects/ui-edit-cancel/edit\"", res_edit.text)
        self.assertIn("name=\"slug\"", res_edit.text)

        # GET cancel
        res_cancel = self.client.get(
            "/projects/ui-edit-cancel/cancel",
            headers={"hx-request": "true"},
        )
        self.assertEqual(res_cancel.status_code, 200)
        self.assertIn("ui-edit-cancel", res_cancel.text)
        self.assertIn("Open Workspace", res_cancel.text)

    def test_ui_edit_project_success(self):
        self.client.post("/api/projects", json={"slug": "before-edit"})

        res = self.client.post(
            "/projects/before-edit/edit",
            data={"slug": "after-edit"},
            headers={"hx-request": "true"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("after-edit", res.text)
        self.assertIn("id=\"project-after-edit\"", res.text)

    def test_ui_edit_project_validation_error(self):
        self.client.post("/api/projects", json={"slug": "ui-val-err"})

        res = self.client.post(
            "/projects/ui-val-err/edit",
            data={"slug": "Invalid Slug!"},
            headers={"hx-request": "true"},
        )
        self.assertEqual(res.status_code, 422)
        self.assertIn("kebab-case", res.text)

    def test_ui_edit_project_duplicate_error(self):
        self.client.post("/api/projects", json={"slug": "first-proj"})
        self.client.post("/api/projects", json={"slug": "second-proj"})

        res = self.client.post(
            "/projects/second-proj/edit",
            data={"slug": "first-proj"},
            headers={"hx-request": "true"},
        )
        self.assertEqual(res.status_code, 422)
        self.assertIn("already exists", res.text)

    def test_ui_delete_project_htmx(self):
        self.client.post("/api/projects", json={"slug": "delete-ui-proj"})

        res = self.client.post(
            "/projects/delete-ui-proj/delete",
            headers={"hx-request": "true"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertNotIn("delete-ui-proj", res.text)
        self.assertIn("projects-list", res.text)

    def test_ui_edit_and_delete_project_not_found(self):
        res_edit = self.client.get("/projects/non-existent/edit")
        self.assertEqual(res_edit.status_code, 404)

        res_cancel = self.client.get("/projects/non-existent/cancel")
        self.assertEqual(res_cancel.status_code, 404)

        res_post_edit = self.client.post("/projects/non-existent/edit", data={"slug": "new-slug"})
        self.assertEqual(res_post_edit.status_code, 404)

        res_del = self.client.post("/projects/non-existent/delete")
        self.assertEqual(res_del.status_code, 404)


if __name__ == "__main__":
    unittest.main()
