import asyncio
import json
import unittest

from fastapi.testclient import TestClient

from src.app import create_app
from src.core.logs import log_manager


class TestTestingAndLogs(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = TestClient(self.app)
        self.client.post("/api/projects", json={"slug": "test-project"})

    def test_workspace_tester_and_logs_tabs_rendered(self):
        res = self.client.get("/projects/test-project")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Endpoint Tester", res.text)
        self.assertIn("Logs Monitor", res.text)

    def test_workspace_tab_tester_fragment(self):
        res = self.client.get(
            "/projects/test-project?tab=tester",
            headers={"hx-request": "true", "hx-target": "workspace-tab-content"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("Endpoint Tester", res.text)
        self.assertIn("/projects/test-project/test-request", res.text)

    def test_workspace_tab_logs_fragment(self):
        # Trigger an API call first to test historical log rendering
        self.client.get("/api/projects/test-project/resources")

        res = self.client.get(
            "/projects/test-project?tab=logs",
            headers={"hx-request": "true", "hx-target": "workspace-tab-content"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("Real-Time Request Logs", res.text)
        self.assertIn("/events/logs/test-project", res.text)
        self.assertIn('hx-ext="sse"', res.text)
        self.assertIn("/api/projects/test-project/resources", res.text)

    def test_endpoint_tester_get_request(self):
        # Create resource and insert row
        self.client.post(
            "/api/projects/test-project/resources",
            json={"name": "users", "columns": [{"name": "name", "type": "text"}]},
        )
        self.client.post("/api/test-project/users", json={"name": "Alice"})

        # Test tester sending GET
        res = self.client.post(
            "/projects/test-project/test-request",
            data={"method": "GET", "path": "/api/test-project/users"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("Status: 200", res.text)
        self.assertIn("Alice", res.text)

    def test_endpoint_tester_post_request_with_json_body(self):
        self.client.post(
            "/api/projects/test-project/resources",
            json={"name": "products", "columns": [{"name": "title", "type": "text"}]},
        )

        res = self.client.post(
            "/projects/test-project/test-request",
            data={
                "method": "POST",
                "path": "/api/test-project/products",
                "body": json.dumps({"title": "Keyboard"}),
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("Status: 201", res.text)
        self.assertIn("Keyboard", res.text)

    def test_endpoint_tester_invalid_json_body(self):
        res = self.client.post(
            "/projects/test-project/test-request",
            data={
                "method": "POST",
                "path": "/api/test-project/products",
                "body": "{invalid-json",
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("Status: 400", res.text)
        self.assertIn("Invalid JSON body", res.text)

    def test_endpoint_tester_path_without_leading_slash(self):
        res = self.client.post(
            "/projects/test-project/test-request",
            data={"method": "GET", "path": "api/projects"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("Status: 200", res.text)

    def test_sse_logs_stream_endpoint_404_if_project_missing(self):
        res = self.client.get("/events/logs/nonexistent-project")
        self.assertEqual(res.status_code, 404)

    def test_sse_logs_stream_endpoint_and_filtering(self):
        # Subscribe queue directly to verify manager
        queue = log_manager.subscribe("test-project")
        try:
            # Trigger API call for test-project
            self.client.get("/api/projects/test-project/resources")

            # Check event captured in queue
            event = queue.get_nowait()
            self.assertEqual(event["method"], "GET")
            self.assertEqual(event["path"], "/api/projects/test-project/resources")
            self.assertEqual(event["status_code"], 200)
            self.assertEqual(event["project_slug"], "test-project")
            self.assertIn("duration_ms", event)
            self.assertIn("timestamp", event)
        finally:
            log_manager.unsubscribe("test-project", queue)

    def test_audit_log_filters_by_project(self):
        self.client.post("/api/projects", json={"slug": "other-project"})

        queue_test = log_manager.subscribe("test-project")
        queue_other = log_manager.subscribe("other-project")

        try:
            # Call route for test-project
            self.client.get("/api/test-project/items")

            # queue_test must receive the event, queue_other should not
            event = queue_test.get_nowait()
            self.assertEqual(event["project_slug"], "test-project")
            self.assertTrue(queue_other.empty())
        finally:
            log_manager.unsubscribe("test-project", queue_test)
            log_manager.unsubscribe("other-project", queue_other)

    def test_sse_stream_response_content(self):
        import asyncio
        from src.router.web import stream_project_logs
        from unittest.mock import AsyncMock, MagicMock

        mock_request = MagicMock()
        mock_request.app.state.db = self.app.state.db
        mock_request.is_disconnected = AsyncMock(side_effect=[False, True])

        async def run_test():
            resp = await stream_project_logs(mock_request, "test-project")
            self.assertEqual(resp.media_type, "text/event-stream")

            # Broadcast after subscribing
            await log_manager.broadcast(
                "test-project",
                {
                    "timestamp": "2026-08-19 12:00:00",
                    "method": "POST",
                    "path": "/api/test-project/orders",
                    "status_code": 201,
                    "duration_ms": 1.23,
                    "project_slug": "test-project",
                },
            )

            chunks = []
            async for chunk in resp.body_iterator:
                chunks.append(chunk)
                if "event: message" in chunk:
                    break

            combined = "".join(chunks)
            self.assertIn("event: message", combined)
            self.assertIn("/api/test-project/orders", combined)
            self.assertIn("POST", combined)
            self.assertIn("201", combined)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
