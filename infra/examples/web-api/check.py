#!/usr/bin/env python3
"""Клиент эталона Web API: успех, ошибка валидации, временный отказ и идемпотентный повтор."""

from __future__ import annotations

import os
import time
import uuid

import requests

BASE = os.environ.get("API_URL", "http://127.0.0.1:8090")
TOKEN = os.environ.get("API_TOKEN", "")


def headers(key: str, extra: dict | None = None) -> dict:
    value = {"Content-Type": "application/json", "Idempotency-Key": key}
    if TOKEN:
        value["Authorization"] = f"Bearer {TOKEN}"
    if extra:
        value.update(extra)
    return value


def post(key: str, body: dict, extra: dict | None = None) -> requests.Response:
    return requests.post(f"{BASE}/v1/operations", json=body, headers=headers(key, extra), timeout=5)


def main() -> None:
    alive = requests.get(f"{BASE}/v1/health/livez", timeout=5)
    if alive.status_code != 200:
        raise SystemExit(f"health {alive.status_code}")

    key = str(uuid.uuid4())
    created = post(key, {"name": "demo"})
    if created.status_code != 201:
        raise SystemExit(f"create {created.status_code} {created.text}")
    again = post(key, {"name": "demo"})
    if again.status_code != 200 or again.json()["id"] != created.json()["id"]:
        raise SystemExit("idempotent replay created a duplicate")

    invalid = post(str(uuid.uuid4()), {"name": " "})
    if invalid.status_code != 422:
        raise SystemExit(f"validation {invalid.status_code}")

    retry_key = str(uuid.uuid4())
    first = post(retry_key, {"name": "retry"}, {"X-Demo-Failure": "temporary"})
    if first.status_code != 503:
        raise SystemExit(f"expected temporary failure, got {first.status_code}")
    time.sleep(0.05)
    recovered = post(retry_key, {"name": "retry"}, {"X-Demo-Failure": "temporary"})
    if recovered.status_code != 201:
        raise SystemExit(f"retry {recovered.status_code} {recovered.text}")
    third = post(retry_key, {"name": "retry"})
    if third.json()["id"] != recovered.json()["id"]:
        raise SystemExit("retry created a duplicate")
    print("web-api checks passed")


if __name__ == "__main__":
    main()
