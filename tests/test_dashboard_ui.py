import unittest

from fastapi.testclient import TestClient

from src.app import create_app


class TestDashboardUI(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = TestClient(self.app)

    def test_ssr_render_projects_hub(self):
        self.client.post("/api/projects", json={"slug": "proj-one"})
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/html", res.headers["content-type"])
        self.assertIn("API Hub", res.text)
        self.assertIn("proj-one", res.text)

    def test_projects_hub_search_htmx_fragment(self):
        self.client.post("/api/projects", json={"slug": "alpha-app"})
        self.client.post("/api/projects", json={"slug": "beta-api"})

        res = self.client.get(
            "/projects?q=alpha",
            headers={"hx-request": "true", "hx-target": "projects-list-container"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("alpha-app", res.text)
        self.assertNotIn("beta-api", res.text)

    def test_projects_hub_search_no_match(self):
        self.client.post("/api/projects", json={"slug": "alpha-app"})
        res = self.client.get(
            "/projects?q=gamma",
            headers={"hx-request": "true", "hx-target": "projects-list-container"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("No projects found", res.text)

    def test_create_project_htmx_redirect_header(self):
        res = self.client.post(
            "/projects",
            data={"slug": "my-store"},
            headers={"hx-request": "true"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("hx-redirect"), "/projects/my-store")

    def test_create_project_non_htmx_redirect(self):
        res = self.client.post(
            "/projects",
            data={"slug": "another-store"},
            follow_redirects=False,
        )
        self.assertEqual(res.status_code, 303)
        self.assertEqual(res.headers.get("location"), "/projects/another-store")

    def test_create_project_invalid_slug_htmx_returns_error(self):
        res = self.client.post(
            "/projects",
            data={"slug": "Invalid Slug!"},
            headers={"hx-request": "true"},
        )
        self.assertEqual(res.status_code, 422)
        self.assertIn("error", res.text)
        self.assertIn("kebab-case", res.text)

    def test_create_project_duplicate_slug_htmx_returns_error(self):
        self.client.post("/api/projects", json={"slug": "dup-proj"})
        res = self.client.post(
            "/projects",
            data={"slug": "dup-proj"},
            headers={"hx-request": "true"},
        )
        self.assertEqual(res.status_code, 422)
        self.assertIn("already exists", res.text)

    def test_create_project_invalid_slug_non_htmx_renders_error(self):
        res = self.client.post(
            "/projects",
            data={"slug": "Invalid Slug!"},
        )
        self.assertEqual(res.status_code, 422)
        self.assertIn("kebab-case", res.text)

    def test_ssr_render_workspace(self):
        self.client.post("/api/projects", json={"slug": "proj-ws"})
        res = self.client.get("/projects/proj-ws")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Workspace: <code>proj-ws</code>", res.text)
        self.assertIn("Endpoints", res.text)

    def test_workspace_missing_project_404(self):
        res = self.client.get("/projects/non-existent")
        self.assertEqual(res.status_code, 404)

    def test_workspace_tab_navigation_htmx_fragments(self):
        self.client.post("/api/projects", json={"slug": "proj-tabs"})

        # Tab schema
        res_schema = self.client.get(
            "/projects/proj-tabs?tab=schema",
            headers={"hx-request": "true", "hx-target": "workspace-tab-content"},
        )
        self.assertEqual(res_schema.status_code, 200)
        self.assertIn("schema-builder-section", res_schema.text)

        # Tab data
        res_data = self.client.get(
            "/projects/proj-tabs?tab=data",
            headers={"hx-request": "true", "hx-target": "workspace-tab-content"},
        )
        self.assertEqual(res_data.status_code, 200)
        self.assertIn("Data Explorer", res_data.text)

    def test_get_column_row_fragment(self):
        res = self.client.get("/fragments/column-row")
        self.assertEqual(res.status_code, 200)
        self.assertIn("column_name", res.text)
        self.assertIn("column_type", res.text)

    def test_schema_builder_create_resource_htmx_success(self):
        self.client.post("/api/projects", json={"slug": "store"})

        res = self.client.post(
            "/projects/store/resources",
            data={
                "name": "product",
                "column_name": ["title", "price"],
                "column_type": ["text", "number"],
            },
            headers={"hx-request": "true"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("products", res.text)
        self.assertIn("title: text", res.text)
        self.assertIn("price: number", res.text)

    def test_schema_builder_resource_sanitized_to_plural_lowercase(self):
        self.client.post("/api/projects", json={"slug": "store-san"})

        res = self.client.post(
            "/projects/store-san/resources",
            data={
                "name": "User",
                "column_name": ["name"],
                "column_type": ["text"],
            },
            headers={"hx-request": "true"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("users", res.text)

    def test_schema_builder_duplicate_column_rejected(self):
        self.client.post("/api/projects", json={"slug": "store-col-dup"})

        res = self.client.post(
            "/projects/store-col-dup/resources",
            data={
                "name": "items",
                "column_name": ["title", "title"],
                "column_type": ["text", "text"],
            },
            headers={"hx-request": "true"},
        )
        self.assertEqual(res.status_code, 422)
        self.assertIn("Duplicate column &#39;title&#39;", res.text)

    def test_schema_builder_duplicate_resource_rejected(self):
        self.client.post("/api/projects", json={"slug": "store-dup"})
        self.client.post(
            "/projects/store-dup/resources",
            data={"name": "users", "column_name": ["name"], "column_type": ["text"]},
        )
        res = self.client.post(
            "/projects/store-dup/resources",
            data={"name": "users", "column_name": ["name"], "column_type": ["text"]},
            headers={"hx-request": "true"},
        )
        self.assertEqual(res.status_code, 422)
        self.assertIn("already exists", res.text)

    def test_schema_builder_missing_project_404(self):
        res = self.client.post(
            "/projects/missing/resources",
            data={"name": "users", "column_name": ["name"], "column_type": ["text"]},
        )
        self.assertEqual(res.status_code, 404)

    def test_desktop_responsive_layout_styles(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("max-width: 1440px;", res.text)
        self.assertIn("flex-wrap: wrap;", res.text)
        self.assertIn("@media (min-width: 1920px)", res.text)
        self.assertIn("overflow-x: auto;", res.text)


if __name__ == "__main__":
    unittest.main()
