import re

from .errors import InvalidPayloadError

SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def validate_slug(slug) -> str:
    if not isinstance(slug, str) or not SLUG_RE.match(slug):
        raise InvalidPayloadError(
            "Project slug must be lowercase kebab-case (ex: my-project)"
        )
    return slug


def sanitize_resource(name) -> str:
    if not isinstance(name, str) or not name.strip():
        raise InvalidPayloadError("Resource name is required")
    cleaned = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    if not cleaned:
        raise InvalidPayloadError("Resource name must contain letters or numbers")
    if not cleaned.endswith("s"):
        cleaned = f"{cleaned}s"
    return cleaned


def validate_columns(columns) -> list[dict]:
    if not isinstance(columns, list) or not columns:
        raise InvalidPayloadError("'columns' must be a non-empty list")
    seen = set()
    for column in columns:
        if not isinstance(column, dict) or not column.get("name"):
            raise InvalidPayloadError("Each column needs a 'name'")
        name = column["name"]
        if name in seen:
            raise InvalidPayloadError(f"Duplicate column '{name}'")
        seen.add(name)
    return columns