import unittest
from fastapi.testclient import TestClient

from src.app import create_app


class TestEndpointsTab(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = TestClient(self.app)
        self.client.post("/api/projects", json={"slug": "test-endpoints"})

    def test_render_endpoints_tab_empty(self):
        res = self.client.get("/projects/test-endpoints?tab=endpoints")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Endpoints", res.text)
        self.assertIn("+ Add Endpoint", res.text)
        self.assertIn("No endpoints defined yet", res.text)

    def test_render_endpoints_tab_htmx(self):
        res = self.client.get(
            "/projects/test-endpoints?tab=endpoints",
            headers={"hx-request": "true", "hx-target": "workspace-tab-content"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("tab-endpoints-container", res.text)

    def test_create_endpoint_form_htmx_success(self):
        res = self.client.post(
            "/projects/test-endpoints/endpoints",
            data={
                "name": "posts",
                "column_name": ["title", "views"],
                "column_type": ["text", "number"],
            },
            headers={"hx-request": "true"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("posts", res.text)
        self.assertIn("/api/test-endpoints/posts", res.text)
        self.assertIn("title: text", res.text)
        self.assertIn("views: number", res.text)

    def test_create_endpoint_form_validation_error(self):
        # duplicate column name
        res = self.client.post(
            "/projects/test-endpoints/endpoints",
            data={
                "name": "posts",
                "column_name": ["title", "title"],
                "column_type": ["text", "text"],
            },
            headers={"hx-request": "true"},
        )
        self.assertEqual(res.status_code, 422)
        self.assertIn("Duplicate column", res.text)

    def test_create_endpoint_project_not_found(self):
        res = self.client.post(
            "/projects/non-existent/endpoints",
            data={"name": "posts", "column_name": ["title"], "column_type": ["text"]},
        )
        self.assertEqual(res.status_code, 404)

    def test_edit_and_cancel_endpoint_row(self):
        # Create endpoint first
        create_res = self.client.post(
            "/api/projects/test-endpoints/resources",
            json={"name": "users", "columns": [{"name": "username", "type": "text"}]},
        )
        resource_id = create_res.json()["id"]

        # GET edit row form
        res_edit = self.client.get(
            f"/projects/test-endpoints/endpoints/{resource_id}/edit",
            headers={"hx-request": "true"},
        )
        self.assertEqual(res_edit.status_code, 200)
        self.assertIn(f"hx-put=\"/projects/test-endpoints/endpoints/{resource_id}\"", res_edit.text)

        # GET cancel edit
        res_cancel = self.client.get(
            f"/projects/test-endpoints/endpoints/{resource_id}/cancel",
            headers={"hx-request": "true"},
        )
        self.assertEqual(res_cancel.status_code, 200)
        self.assertIn("users", res_cancel.text)

    def test_edit_endpoint_not_found_errors(self):
        res = self.client.get("/projects/test-endpoints/endpoints/9999/edit")
        self.assertEqual(res.status_code, 404)

        res_cancel = self.client.get("/projects/test-endpoints/endpoints/9999/cancel")
        self.assertEqual(res_cancel.status_code, 404)

        res_proj = self.client.get("/projects/non-existent/endpoints/1/edit")
        self.assertEqual(res_proj.status_code, 404)

        res_proj_cancel = self.client.get("/projects/non-existent/endpoints/1/cancel")
        self.assertEqual(res_proj_cancel.status_code, 404)

    def test_update_endpoint_form(self):
        create_res = self.client.post(
            "/api/projects/test-endpoints/resources",
            json={"name": "items", "columns": [{"name": "name", "type": "text"}]},
        )
        resource_id = create_res.json()["id"]

        # Valid update
        res_put = self.client.put(
            f"/projects/test-endpoints/endpoints/{resource_id}",
            data={
                "name": "products",
                "column_name": ["name", "price"],
                "column_type": ["text", "number"],
            },
            headers={"hx-request": "true"},
        )
        self.assertEqual(res_put.status_code, 200)
        self.assertIn("products", res_put.text)
        self.assertIn("price: number", res_put.text)

        # Invalid update: duplicate columns
        res_put_invalid = self.client.put(
            f"/projects/test-endpoints/endpoints/{resource_id}",
            data={
                "name": "products",
                "column_name": ["dup", "dup"],
                "column_type": ["text", "text"],
            },
            headers={"hx-request": "true"},
        )
        self.assertEqual(res_put_invalid.status_code, 422)
        self.assertIn("Duplicate column", res_put_invalid.text)

    def test_update_endpoint_errors(self):
        res = self.client.put(
            "/projects/test-endpoints/endpoints/9999",
            data={"name": "x", "column_name": ["a"], "column_type": ["text"]},
        )
        self.assertEqual(res.status_code, 404)

        res_proj = self.client.put(
            "/projects/non-existent/endpoints/1",
            data={"name": "x", "column_name": ["a"], "column_type": ["text"]},
        )
        self.assertEqual(res_proj.status_code, 404)

    def test_delete_endpoint_flow(self):
        create_res = self.client.post(
            "/api/projects/test-endpoints/resources",
            json={"name": "comments", "columns": [{"name": "body", "type": "text"}]},
        )
        resource_id = create_res.json()["id"]

        res_del = self.client.delete(
            f"/projects/test-endpoints/endpoints/{resource_id}",
            headers={"hx-request": "true"},
        )
        self.assertEqual(res_del.status_code, 200)

        # Confirm deleted
        res_del_404 = self.client.delete(f"/projects/test-endpoints/endpoints/{resource_id}")
        self.assertEqual(res_del_404.status_code, 404)

        res_del_proj_404 = self.client.delete(f"/projects/non-existent/endpoints/{resource_id}")
        self.assertEqual(res_del_proj_404.status_code, 404)

    def test_api_resource_crud_endpoints(self):
        # Create resource
        res_create = self.client.post(
            "/api/projects/test-endpoints/resources",
            json={"name": "customers", "columns": [{"name": "email", "type": "text"}]},
        )
        self.assertEqual(res_create.status_code, 201)
        res_id = res_create.json()["id"]

        # Get resource
        res_get = self.client.get(f"/api/projects/test-endpoints/resources/{res_id}")
        self.assertEqual(res_get.status_code, 200)
        self.assertEqual(res_get.json()["name"], "customers")

        # Put resource
        res_put = self.client.put(
            f"/api/projects/test-endpoints/resources/{res_id}",
            json={"name": "clients", "columns": [{"name": "email", "type": "text"}, {"name": "active", "type": "boolean"}]},
        )
        self.assertEqual(res_put.status_code, 200)
        self.assertEqual(res_put.json()["name"], "clients")

        # Delete resource
        res_del = self.client.delete(f"/api/projects/test-endpoints/resources/{res_id}")
        self.assertEqual(res_del.status_code, 204)

        # Verify not found after delete
        res_get_404 = self.client.get(f"/api/projects/test-endpoints/resources/{res_id}")
        self.assertEqual(res_get_404.status_code, 404)


if __name__ == "__main__":
    unittest.main()
