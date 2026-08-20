import unittest

from fastapi.testclient import TestClient

from src.app import create_app


def create_project_with_users(client, slug="proj-a") -> int:
    assert client.post("/api/projects", json={"slug": slug}).status_code == 201
    res = client.post(
        f"/api/projects/{slug}/resources",
        json={"name": "users", "columns": [{"name": "name", "type": "text"}, {"name": "age", "type": "number"}]},
    )
    assert res.status_code == 201
    return res.json()["id"]


class TestProjects(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app())

    def test_create_project(self):
        res = self.client.post("/api/projects", json={"slug": "proj-a"})
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["slug"], "proj-a")

    def test_invalid_slug_rejected(self):
        for bad in ["Proj A", "Proj_A", "proj a", "PROJ-A", ""]:
            res = self.client.post("/api/projects", json={"slug": bad})
            self.assertEqual(res.status_code, 400, msg=bad)

    def test_duplicate_project_conflict(self):
        self.client.post("/api/projects", json={"slug": "proj-a"})
        res = self.client.post("/api/projects", json={"slug": "proj-a"})
        self.assertEqual(res.status_code, 409)

    def test_list_projects(self):
        self.client.post("/api/projects", json={"slug": "proj-a"})
        self.client.post("/api/projects", json={"slug": "proj-b"})
        res = self.client.get("/api/projects")
        self.assertEqual([p["slug"] for p in res.json()], ["proj-a", "proj-b"])

    def test_create_resource_with_duplicate_columns(self):
        self.client.post("/api/projects", json={"slug": "proj-a"})
        res = self.client.post(
            "/api/projects/proj-a/resources",
            json={"name": "users", "columns": [{"name": "name"}, {"name": "name"}]},
        )
        self.assertEqual(res.status_code, 400)

    def test_resource_sanitized_to_lowercase(self):
        self.client.post("/api/projects", json={"slug": "proj-a"})
        res = self.client.post(
            "/api/projects/proj-a/resources",
            json={"name": "Users", "columns": [{"name": "name"}]},
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["name"], "users")


    def test_duplicate_resource_conflict(self):
        self.client.post("/api/projects", json={"slug": "proj-a"})
        res1 = self.client.post(
            "/api/projects/proj-a/resources",
            json={"name": "users", "columns": [{"name": "name"}]},
        )
        self.assertEqual(res1.status_code, 201)
        res2 = self.client.post(
            "/api/projects/proj-a/resources",
            json={"name": "users", "columns": [{"name": "name"}]},
        )
        self.assertEqual(res2.status_code, 409)

    def test_list_resources(self):
        self.client.post("/api/projects", json={"slug": "proj-a"})
        self.client.post(
            "/api/projects/proj-a/resources",
            json={"name": "users", "columns": [{"name": "name"}]},
        )
        self.client.post(
            "/api/projects/proj-a/resources",
            json={"name": "orders", "columns": [{"name": "total"}]},
        )
        res = self.client.get("/api/projects/proj-a/resources")
        self.assertEqual(res.status_code, 200)
        self.assertEqual([r["name"] for r in res.json()], ["users", "orders"])

    def test_create_or_list_resources_missing_project_404(self):
        self.assertEqual(
            self.client.get("/api/projects/nao-existe/resources").status_code, 404
        )
        self.assertEqual(
            self.client.post(
                "/api/projects/nao-existe/resources",
                json={"name": "users", "columns": [{"name": "name"}]},
            ).status_code,
            404,
        )


class TestDynamicRouter(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app())
        create_project_with_users(self.client)

    def test_post_get_put_delete_flow(self):
        created = self.client.post("/api/proj-a/users", json={"name": "ana", "age": 30})
        self.assertEqual(created.status_code, 201)
        row = created.json()
        self.assertEqual(row["name"], "ana")

        listed = self.client.get("/api/proj-a/users")
        self.assertEqual(len(listed.json()), 1)
        self.assertEqual(listed.json()[0]["id"], row["id"])

        single = self.client.get(f"/api/proj-a/users/{row['id']}")
        self.assertEqual(single.status_code, 200)
        self.assertEqual(single.json()["age"], 30)

        updated = self.client.put(
            f"/api/proj-a/users/{row['id']}", json={"name": "ana", "age": 31}
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["age"], 31)

        deleted = self.client.delete(f"/api/proj-a/users/{row['id']}")
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(self.client.get("/api/proj-a/users").json(), [])

    def test_post_row_with_unknown_column(self):
        res = self.client.post("/api/proj-a/users", json={"email": "x@y.com"})
        self.assertEqual(res.status_code, 400)

    def test_get_missing_project_404(self):
        res = self.client.get("/api/nao-existe/users")
        self.assertEqual(res.status_code, 404)

    def test_get_missing_resource_404(self):
        res = self.client.get("/api/proj-a/groups")
        self.assertEqual(res.status_code, 404)

    def test_row_not_found_404(self):
        self.assertEqual(self.client.get("/api/proj-a/users/999").status_code, 404)
        self.assertEqual(
            self.client.put("/api/proj-a/users/999", json={"name": "x"}).status_code, 404
        )
        self.assertEqual(self.client.delete("/api/proj-a/users/999").status_code, 404)

    def test_malformed_json_body_400(self):
        res = self.client.post(
            "/api/proj-a/users", content="{invalid", headers={"content-type": "application/json"}
        )
        self.assertEqual(res.status_code, 400)

    def test_invalid_payload_shape_400(self):
        res = self.client.post("/api/proj-a/users", json=["not", "an", "object"])
        self.assertEqual(res.status_code, 400)


class TestIsolation(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app())
        create_project_with_users(self.client, "proj-a")
        create_project_with_users(self.client, "proj-b")
        self.parent = {"name": "thedad", "age": 50}
        create_row_a = self.client.post("/api/proj-a/users", json=self.parent)
        self.row_a = create_row_a.json()

    def test_data_not_leaked_between_projects(self):
        rows_b = self.client.get("/api/proj-b/users").json()
        self.assertEqual(rows_b, [])

    def test_cross_project_row_operations_404(self):
        self.assertEqual(
            self.client.get(f"/api/proj-b/users/{self.row_a['id']}").status_code, 404
        )
        self.assertEqual(
            self.client.put(
                f"/api/proj-b/users/{self.row_a['id']}", json={"name": "x"}
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.delete(f"/api/proj-b/users/{self.row_a['id']}").status_code, 404
        )

    def test_write_to_own_project_does_not_touch_other(self):
        self.client.post("/api/proj-b/users", json={"name": "other", "age": 1})
        rows_a = self.client.get("/api/proj-a/users").json()
        self.assertEqual([r["name"] for r in rows_a], ["thedad"])


class TestQueryParams(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app())
        create_project_with_users(self.client)
        for name, age in [("zoe", 40), ("ana", 30), ("bia", 30), ("caio", 20)]:
            self.client.post("/api/proj-a/users", json={"name": name, "age": age})

    def test_pagination(self):
        res = self.client.get("/api/proj-a/users?_page=1&_limit=2")
        self.assertEqual(len(res.json()), 2)
        self.assertEqual(res.headers["x-total-count"], "4")
        res2 = self.client.get("/api/proj-a/users?_page=2&_limit=2")
        self.assertEqual(len(res2.json()), 2)
        self.assertNotEqual([r["id"] for r in res.json()], [r["id"] for r in res2.json()])

    def test_sort_asc(self):
        res = self.client.get("/api/proj-a/users?_sort=age")
        self.assertEqual([r["age"] for r in res.json()], [20, 30, 30, 40])

    def test_sort_desc(self):
        res = self.client.get("/api/proj-a/users?_sort=age&_order=desc")
        self.assertEqual([r["age"] for r in res.json()], [40, 30, 30, 20])

    def test_sort_by_text(self):
        res = self.client.get("/api/proj-a/users?_sort=name")
        self.assertEqual([r["name"] for r in res.json()], ["ana", "bia", "caio", "zoe"])

    def test_filter_equality(self):
        res = self.client.get("/api/proj-a/users?age=30")
        self.assertEqual(sorted(r["name"] for r in res.json()), ["ana", "bia"])

    def test_filter_combined_with_pagination(self):
        res = self.client.get("/api/proj-a/users?age=30&_page=1&_limit=1")
        self.assertEqual(len(res.json()), 1)
        self.assertEqual(res.headers["x-total-count"], "2")

    def test_invalid_pagination_value_400(self):
        self.assertEqual(self.client.get("/api/proj-a/users?_page=abc").status_code, 400)
        self.assertEqual(self.client.get("/api/proj-a/users?_limit=0").status_code, 400)


    def test_invalid_sort_order_400(self):
        self.assertEqual(
            self.client.get("/api/proj-a/users?_sort=age&_order=invalid").status_code, 400
        )

    def test_filter_no_match(self):
        res = self.client.get("/api/proj-a/users?age=999")
        self.assertEqual(res.json(), [])


if __name__ == "__main__":
    unittest.main()