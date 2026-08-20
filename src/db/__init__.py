
import sqlite3
from pathlib import Path


def get_db_path(db_path: str = ":memory:") -> str:
    if db_path == ":memory:":
        return ":memory:"
    path = Path(db_path)
    return str(path if path.is_absolute() else Path.cwd() / path)
