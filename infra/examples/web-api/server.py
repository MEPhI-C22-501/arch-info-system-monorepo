#!/usr/bin/env python3
"""Эталон Web API: идемпотентное создание и проверка токена, если задан OIDC."""

from __future__ import annotations

import json
import os
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import jwt
import requests

STORE_PATH = os.environ.get("API_STORE", "/tmp/operations.json")
ISSUER = os.environ.get("OIDC_ISSUER", "")
JWKS_URI = os.environ.get("OIDC_JWKS_URI", "")
AUDIENCE = os.environ.get("OIDC_AUDIENCE", "example-api")
PORT = int(os.environ.get("API_PORT", "8090"))


def load_store() -> dict:
    if not os.path.exists(STORE_PATH):
        return {"operations": {}, "failures": {}}
    with open(STORE_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def save_store(store: dict) -> None:
    temporary = STORE_PATH + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(store, handle)
    os.replace(temporary, STORE_PATH)


def authorized(header: str | None) -> bool:
    if not ISSUER:
        return True
    if not header or not header.startswith("Bearer "):
        return False
    token = header.split(" ", 1)[1]
    try:
        header_data = jwt.get_unverified_header(token)
        jwks = requests.get(JWKS_URI, timeout=5).json()
        key = None
        for item in jwks["keys"]:
            if item.get("kid") == header_data.get("kid"):
                key = jwt.PyJWK.from_dict(item).key
                break
        if key is None:
            return False
        jwt.decode(token, key, algorithms=["RS256"], audience=AUDIENCE, issuer=ISSUER)
    except (jwt.PyJWTError, requests.RequestException, ValueError, KeyError):
        return False
    return True


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        return

    def send_json(self, status: int, body: dict) -> None:
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/v1/health/livez":
            self.send_json(200, {"status": "up"})
            return
        if self.path == "/v1/operations":
            if not authorized(self.headers.get("Authorization")):
                self.send_json(401, {"error": "unauthorized"})
                return
            store = load_store()
            self.send_json(200, {"count": len(store["operations"])})
            return
        self.send_json(404, {"error": "not-found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/operations":
            self.send_json(404, {"error": "not-found"})
            return
        if not authorized(self.headers.get("Authorization")):
            self.send_json(401, {"error": "unauthorized"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self.send_json(422, {"error": "invalid-json"})
            return
        name = payload.get("name")
        if not isinstance(name, str) or not name.strip():
            self.send_json(422, {"error": "name-required"})
            return
        key = self.headers.get("Idempotency-Key")
        if not key:
            self.send_json(422, {"error": "idempotency-key-required"})
            return
        store = load_store()
        if self.headers.get("X-Demo-Failure") == "temporary":
            seen = store["failures"].get(key, 0)
            if seen < 1:
                store["failures"][key] = seen + 1
                save_store(store)
                self.send_json(503, {"error": "temporary"})
                return
        existing = store["operations"].get(key)
        if existing:
            self.send_json(200, existing)
            return
        created = {"id": str(uuid.uuid4()), "name": name, "idempotencyKey": key}
        store["operations"][key] = created
        save_store(store)
        self.send_json(201, created)


def main() -> None:
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
