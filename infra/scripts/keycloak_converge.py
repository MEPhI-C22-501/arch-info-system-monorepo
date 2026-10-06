#!/usr/bin/env python3
"""Сводит realm к desired.json. Существующих пользователей не удаляет и не сбрасывает им пароль."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request

BASE = os.environ["KEYCLOAK_INTERNAL_URL"].rstrip("/")
REALM_FILE = os.environ.get("KEYCLOAK_DESIRED", "/realm/desired.json")
ADMIN_USER = os.environ["KC_BOOTSTRAP_ADMIN_USERNAME"]
ADMIN_PASSWORD = os.environ["KC_BOOTSTRAP_ADMIN_PASSWORD"]


def request(method: str, path: str, token: str | None = None, body: dict | None = None, ok=(200, 201, 204)):
    data = None if body is None else json.dumps(body).encode()
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as error:
        raw = error.read()
        if error.code in ok:
            return error.code, json.loads(raw) if raw else None
        detail = raw.decode(errors="replace")[:500]
        raise RuntimeError(f"{method} {path} -> {error.code} {detail}") from error


def admin_token() -> str:
    form = urllib.parse.urlencode(
        {
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": ADMIN_USER,
            "password": ADMIN_PASSWORD,
        }
    ).encode()
    req = urllib.request.Request(
        f"{BASE}/realms/master/protocol/openid-connect/token",
        data=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read())["access_token"]


def wait_ready() -> str:
    last = "not started"
    for _ in range(60):
        try:
            return admin_token()
        except Exception as error:  # noqa: BLE001 - ждём готовность Keycloak
            last = str(error)
            time.sleep(2)
    raise RuntimeError(f"keycloak admin API недоступен: {last}")


def find_client(token: str, realm: str, client_id: str) -> dict | None:
    query = urllib.parse.urlencode({"clientId": client_id})
    _, rows = request("GET", f"/admin/realms/{realm}/clients?{query}", token)
    for row in rows or []:
        if row.get("clientId") == client_id:
            return row
    return None


def ensure_mapper(token: str, realm: str, internal_id: str, audience: str) -> None:
    _, mappers = request("GET", f"/admin/realms/{realm}/clients/{internal_id}/protocol-mappers/models", token)
    name = f"audience-{audience}"
    if any(item.get("name") == name for item in mappers or []):
        return
    request(
        "POST",
        f"/admin/realms/{realm}/clients/{internal_id}/protocol-mappers/models",
        token,
        {
            "name": name,
            "protocol": "openid-connect",
            "protocolMapper": "oidc-audience-mapper",
            "config": {
                "included.client.audience": audience,
                "access.token.claim": "true",
                "id.token.claim": "false",
            },
        },
        ok=(201,),
    )


def ensure_client_role(token: str, realm: str, internal_id: str, role: str) -> None:
    path = f"/admin/realms/{realm}/clients/{internal_id}/roles/{urllib.parse.quote(role)}"
    try:
        request("GET", path, token)
    except RuntimeError:
        request("POST", f"/admin/realms/{realm}/clients/{internal_id}/roles", token, {"name": role}, ok=(201,))


def ensure_client(token: str, realm: str, spec: dict) -> dict:
    current = find_client(token, realm, spec["clientId"])
    secret = os.environ[spec["secretEnv"]] if spec.get("secretEnv") else None
    payload = {
        "clientId": spec["clientId"],
        "enabled": True,
        "protocol": "openid-connect",
        "publicClient": spec["publicClient"],
        "standardFlowEnabled": spec["standardFlowEnabled"],
        "implicitFlowEnabled": False,
        "directAccessGrantsEnabled": spec["directAccessGrantsEnabled"],
        "serviceAccountsEnabled": spec["serviceAccountsEnabled"],
        "redirectUris": spec.get("redirectUris") or [],
        "webOrigins": spec.get("webOrigins") or [],
        "fullScopeAllowed": True,
        "attributes": {},
    }
    if spec.get("pkce"):
        payload["attributes"]["pkce.code.challenge.method"] = spec["pkce"]
    if secret:
        payload["secret"] = secret
    if current is None:
        request("POST", f"/admin/realms/{realm}/clients", token, payload, ok=(201,))
        current = find_client(token, realm, spec["clientId"])
    else:
        payload["id"] = current["id"]
        request("PUT", f"/admin/realms/{realm}/clients/{current['id']}", token, payload, ok=(204,))
    if current is None:
        raise RuntimeError(f"client {spec['clientId']} не создан")
    for audience in spec.get("audiences") or []:
        ensure_mapper(token, realm, current["id"], audience)
    for role in spec.get("roles") or []:
        ensure_client_role(token, realm, current["id"], role)
    return find_client(token, realm, spec["clientId"]) or current


def role_representation(token: str, realm: str, client_id: str, role: str) -> dict:
    client = find_client(token, realm, client_id)
    if client is None:
        raise RuntimeError(f"нет клиента {client_id} для роли {role}")
    _, body = request(
        "GET",
        f"/admin/realms/{realm}/clients/{client['id']}/roles/{urllib.parse.quote(role)}",
        token,
    )
    return body


def assign_client_roles(token: str, realm: str, user_id: str, client_id: str, roles: list[str]) -> None:
    client = find_client(token, realm, client_id)
    if client is None:
        raise RuntimeError(client_id)
    reps = [role_representation(token, realm, client_id, role) for role in roles]
    request(
        "POST",
        f"/admin/realms/{realm}/users/{user_id}/role-mappings/clients/{client['id']}",
        token,
        reps,
        ok=(204, 409),
    )


def main() -> None:
    spec = json.load(open(REALM_FILE, encoding="utf-8"))
    realm = spec["realm"]
    token = wait_ready()
    try:
        request("GET", f"/admin/realms/{realm}", token)
    except RuntimeError:
        request("POST", "/admin/realms", token, {"realm": realm, "enabled": True, "sslRequired": "none"}, ok=(201,))
    request("PUT", f"/admin/realms/{realm}", token, {"realm": realm, "enabled": True, "sslRequired": "none"}, ok=(204,))

    by_id = {}
    for client in spec["clients"]:
        by_id[client["clientId"]] = ensure_client(token, realm, client)

    for client in spec["clients"]:
        created = by_id[client["clientId"]]
        if client.get("realmManagementRoles"):
            _, service_user = request(
                "GET", f"/admin/realms/{realm}/clients/{created['id']}/service-account-user", token
            )
            assign_client_roles(token, realm, service_user["id"], "realm-management", client["realmManagementRoles"])
        for target, roles in (client.get("clientRoles") or {}).items():
            _, service_user = request(
                "GET", f"/admin/realms/{realm}/clients/{created['id']}/service-account-user", token
            )
            assign_client_roles(token, realm, service_user["id"], target, roles)

    for user in spec["users"]:
        query = urllib.parse.urlencode({"username": user["username"], "exact": "true"})
        _, found = request("GET", f"/admin/realms/{realm}/users?{query}", token)
        if found:
            continue
        request(
            "POST",
            f"/admin/realms/{realm}/users",
            token,
            {
                "id": user["id"],
                "username": user["username"],
                "enabled": True,
                "credentials": [
                    {"type": "password", "value": os.environ[user["passwordEnv"]], "temporary": False}
                ],
            },
            ok=(201,),
        )
    print("keycloak realm converged")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # noqa: BLE001
        print(f"keycloak converge failed: {error}", file=sys.stderr)
        sys.exit(1)
