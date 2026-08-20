import base64
import hashlib
import hmac
import json
import time

TOKEN_TTL_SECONDS = 300


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64decode(data: str) -> bytes:
    padding = 4 - (len(data) % 4)
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data.encode("utf-8"))


def generate_bearer_token(project_slug: str, api_key_id: int, secret_key: str, scopes: list[str], ttl: int = TOKEN_TTL_SECONDS) -> tuple[str, int]:
    now = int(time.time())
    payload = {
        "slug": project_slug,
        "key_id": api_key_id,
        "scopes": scopes,
        "iat": now,
        "exp": now + ttl,
    }
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = _b64encode(payload_json)
    signature = hmac.new(secret_key.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).digest()
    sig_b64 = _b64encode(signature)
    token = f"{payload_b64}.{sig_b64}"
    return token, ttl


def verify_bearer_token(token: str, secret_key: str) -> dict | None:
    parts = token.split(".")
    if len(parts) != 2:
        return None
    payload_b64, sig_b64 = parts
    expected_sig = hmac.new(secret_key.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).digest()
    expected_sig_b64 = _b64encode(expected_sig)
    if not hmac.compare_digest(sig_b64, expected_sig_b64):
        return None
    try:
        payload_bytes = _b64decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        return None

    if int(time.time()) > payload.get("exp", 0):
        return None
    return payload


def has_scope(required_scope: str, granted_scopes: list[str]) -> bool:
    if "admin" in granted_scopes or "all" in granted_scopes or "*" in granted_scopes:
        return True
    return required_scope in granted_scopes
