from datetime import datetime, timezone
import json
import secrets
import sqlite3

from ..core.errors import ConflictError, ResourceNotFoundError


class Database:
    def __init__(self, path: str = ":memory:"):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS resources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                columns TEXT NOT NULL,
                UNIQUE (project_id, name)
            );
            CREATE TABLE IF NOT EXISTS rows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
                data TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS project_auth (
                project_id INTEGER PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
                auth_type TEXT NOT NULL DEFAULT 'none',
                basic_username TEXT,
                basic_password TEXT,
                secret_key TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                key TEXT NOT NULL UNIQUE,
                scopes TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def create_project(self, slug: str) -> dict:
        try:
            cur = self.conn.execute("INSERT INTO projects (slug) VALUES (?)", (slug,))
            self.conn.commit()
        except sqlite3.IntegrityError:
            raise ConflictError(f"Project '{slug}' already exists")
        return {"id": cur.lastrowid, "slug": slug}

    def get_project(self, slug: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM projects WHERE slug = ?", (slug,)).fetchone()
        return dict(row) if row else None

    def list_projects(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM projects ORDER BY id").fetchall()
        return [dict(row) for row in rows]

    def create_resource(self, project_id: int, name: str, columns: list[dict]) -> dict:
        try:
            cur = self.conn.execute(
                "INSERT INTO resources (project_id, name, columns) VALUES (?, ?, ?)",
                (project_id, name, json.dumps(columns)),
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            raise ConflictError(f"Resource '{name}' already exists in this project")
        return {"id": cur.lastrowid, "name": name, "columns": columns}

    def get_resource(self, project_id: int, name: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM resources WHERE project_id = ? AND name = ?",
            (project_id, name),
        ).fetchone()
        if not row:
            return None
        resource = dict(row)
        resource["columns"] = json.loads(resource["columns"])
        return resource

    def get_resource_by_id(self, project_id: int, resource_id: int) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM resources WHERE project_id = ? AND id = ?",
            (project_id, resource_id),
        ).fetchone()
        if not row:
            return None
        resource = dict(row)
        resource["columns"] = json.loads(resource["columns"])
        return resource

    def update_resource(self, project_id: int, resource_id: int, name: str, columns: list[dict]) -> dict | None:
        try:
            cur = self.conn.execute(
                "UPDATE resources SET name = ?, columns = ? WHERE id = ? AND project_id = ?",
                (name, json.dumps(columns), resource_id, project_id),
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            raise ConflictError(f"Resource '{name}' already exists in this project")
        if cur.rowcount == 0:
            return None
        return {"id": resource_id, "project_id": project_id, "name": name, "columns": columns}

    def delete_resource(self, project_id: int, resource_id: int) -> bool:
        cur = self.conn.execute(
            "DELETE FROM resources WHERE id = ? AND project_id = ?",
            (resource_id, project_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def list_resources(self, project_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM resources WHERE project_id = ? ORDER BY id", (project_id,)
        ).fetchall()
        return [
            {**dict(row), "columns": json.loads(row["columns"])} for row in rows
        ]

    def insert_row(self, project_id: int, resource_id: int, data: dict) -> dict:
        cur = self.conn.execute(
            "INSERT INTO rows (project_id, resource_id, data) VALUES (?, ?, ?)",
            (project_id, resource_id, json.dumps(data)),
        )
        self.conn.commit()
        return {"id": cur.lastrowid, **data}

    def get_row(self, project_id: int, resource_id: int, row_id: int) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM rows WHERE id = ? AND project_id = ? AND resource_id = ?",
            (row_id, project_id, resource_id),
        ).fetchone()
        if not row:
            return None
        return {"id": row_id, **json.loads(row["data"])}

    def update_row(self, project_id: int, resource_id: int, row_id: int, data: dict) -> dict | None:
        cur = self.conn.execute(
            "UPDATE rows SET data = ? WHERE id = ? AND project_id = ? AND resource_id = ?",
            (json.dumps(data), row_id, project_id, resource_id),
        )
        self.conn.commit()
        if cur.rowcount == 0:
            return None
        return {"id": row_id, **data}

    def delete_row(self, project_id: int, resource_id: int, row_id: int) -> bool:
        cur = self.conn.execute(
            "DELETE FROM rows WHERE id = ? AND project_id = ? AND resource_id = ?",
            (row_id, project_id, resource_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def list_rows(self, project_id: int, resource_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM rows WHERE project_id = ? AND resource_id = ? ORDER BY id",
            (project_id, resource_id),
        ).fetchall()
        return [{"id": row["id"], **json.loads(row["data"])} for row in rows]

    def get_project_auth(self, project_id: int) -> dict:
        row = self.conn.execute("SELECT * FROM project_auth WHERE project_id = ?", (project_id,)).fetchone()
        if not row:
            secret = secrets.token_hex(32)
            self.conn.execute(
                "INSERT INTO project_auth (project_id, auth_type, basic_username, basic_password, secret_key) VALUES (?, 'none', '', '', ?)",
                (project_id, secret),
            )
            self.conn.commit()
            return {
                "project_id": project_id,
                "auth_type": "none",
                "basic_username": "",
                "basic_password": "",
                "secret_key": secret,
            }
        return dict(row)

    def update_project_auth(
        self,
        project_id: int,
        auth_type: str,
        basic_username: str = "",
        basic_password: str = "",
    ) -> dict:
        auth = self.get_project_auth(project_id)
        self.conn.execute(
            "UPDATE project_auth SET auth_type = ?, basic_username = ?, basic_password = ? WHERE project_id = ?",
            (auth_type, basic_username, basic_password, project_id),
        )
        self.conn.commit()
        return {
            "project_id": project_id,
            "auth_type": auth_type,
            "basic_username": basic_username,
            "basic_password": basic_password,
            "secret_key": auth["secret_key"],
        }

    def create_api_key(self, project_id: int, name: str, scopes: list[str], custom_key: str | None = None) -> dict:
        key = custom_key or f"mf_{secrets.token_urlsafe(24)}"
        created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        try:
            cur = self.conn.execute(
                "INSERT INTO api_keys (project_id, name, key, scopes, created_at) VALUES (?, ?, ?, ?, ?)",
                (project_id, name, key, json.dumps(scopes), created_at),
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            raise ConflictError("API key already exists")
        return {
            "id": cur.lastrowid,
            "project_id": project_id,
            "name": name,
            "key": key,
            "scopes": scopes,
            "created_at": created_at,
        }

    def get_api_key(self, key: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM api_keys WHERE key = ?", (key,)).fetchone()
        if not row:
            return None
        res = dict(row)
        res["scopes"] = json.loads(res["scopes"])
        return res

    def list_api_keys(self, project_id: int) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM api_keys WHERE project_id = ? ORDER BY id DESC", (project_id,)).fetchall()
        return [{**dict(row), "scopes": json.loads(row["scopes"])} for row in rows]

    def delete_api_key(self, project_id: int, key_id: int) -> bool:
        cur = self.conn.execute("DELETE FROM api_keys WHERE id = ? AND project_id = ?", (key_id, project_id))
        self.conn.commit()
        return cur.rowcount > 0
