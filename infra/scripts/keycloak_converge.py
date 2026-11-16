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


def ensure_client(token: str, realm: str, spec: dict) -> tuple[dict, bool]:
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
        "fullScopeAllowed": False,
        "attributes": {},
    }
    if spec.get("pkce"):
        payload["attributes"]["pkce.code.challenge.method"] = spec["pkce"]
    if spec.get("postLogoutRedirectUris"):
        payload["attributes"]["post.logout.redirect.uris"] = "##".join(spec["postLogoutRedirectUris"])
    if secret:
        payload["secret"] = secret
    created = current is None
    if created:
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
    return current, created


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


def scope_roles(token, realm, base_path, target, roles):
    client = find_client(token, realm, target)
    reps = [role_representation(token, realm, target, role) for role in roles]
    path = f"{base_path}/scope-mappings/clients/{client['id']}"
    _, existing = request("GET", path, token)
    wanted = {role["id"] for role in reps}
    stale = [role for role in existing if role["id"] not in wanted]
    if stale:
        request("DELETE", path, token, stale, ok=(204,))
    if reps:
        request("POST", path, token, reps, ok=(204,))


def ensure_client_scopes(token, realm, clients):
    base = f"/admin/realms/{realm}"
    _, scopes = request("GET", f"{base}/client-scopes", token)
    by_name = {scope["name"]: scope["id"] for scope in scopes}
    grants = {
        "cost.read": ({"reports": ["cost.read"], "planning-system": ["cost.read"]},
                      ["reports", "planning-system", "reports-superset", "reports-client"]),
        "publication.read": ({"planning-system": ["S-03"]}, ["tracker-planning"]),
        "publication.ack": ({"planning-system": ["S-03"]}, ["tracker-planning"]),
        "facts.write": ({"planning-system": ["S-03"]}, ["tracker-planning"]),
        "reports.read": ({"planning-system": ["S-06"]}, ["reports-client"]),
        "reports.export": ({"planning-system": ["S-06"]}, ["reports-client"]),
        "qa.read": ({"planning-system": ["S-07"]}, ["qa-executor"]),
    }
    for name, (mappings, recipients) in grants.items():
        if name not in by_name:
            request("POST", f"{base}/client-scopes", token, {
                "name": name, "protocol": "openid-connect",
                "attributes": {"include.in.token.scope": "true"},
            }, ok=(201,))
            _, scopes = request("GET", f"{base}/client-scopes", token)
            by_name = {scope["name"]: scope["id"] for scope in scopes}
        scope = by_name[name]
        for target, roles in mappings.items():
            scope_roles(token, realm, f"{base}/client-scopes/{scope}", target, roles)
        for target in recipients:
            if target in clients:
                request("PUT", f"{base}/clients/{clients[target][0]['id']}/default-client-scopes/{scope}", token)


def ensure_claim_mappers(token, realm, internal_id, attributes):
    path = f"/admin/realms/{realm}/clients/{internal_id}/protocol-mappers/models"
    _, existing = request("GET", path, token)
    names = {row["name"] for row in existing}
    for field in attributes:
        if field in names:
            continue
        request("POST", path, token, {
            "name": field, "protocol": "openid-connect", "protocolMapper": "oidc-usermodel-attribute-mapper",
            "config": {"user.attribute": field, "claim.name": field, "jsonType.label": "String",
                       "multivalued": "true", "access.token.claim": "true", "id.token.claim": "false"},
        }, ok=(201,))


def protect_scope_attributes(token, base, attributes):
    if not attributes:
        return
    path = f"{base}/users/profile"
    _, config = request("GET", path, token)
    existing = {entry["name"]: entry for entry in config["attributes"]}
    for field in sorted(attributes):
        entry = existing.get(field)
        if entry is None:
            entry = {"name": field}
            config["attributes"].append(entry)
        entry.update(permissions={"view": ["admin"], "edit": ["admin"]}, multivalued=True)
    request("PUT", path, token, config, ok=(200, 204))


def main() -> None:
    with open(REALM_FILE, encoding="utf-8") as realm_file:
        spec = json.load(realm_file)
    realm = spec["realm"]
    base = f"/admin/realms/{realm}"
    token = wait_ready()
    try:
        request("GET", f"/admin/realms/{realm}", token)
    except RuntimeError:
        request("POST", "/admin/realms", token, {"realm": realm, "enabled": True, "sslRequired": "none"}, ok=(201,))
    request("PUT", base, token, {"accessTokenLifespan": 300}, ok=(204,))
    request("PUT", f"{base}/events/config", token, {
        "adminEventsEnabled": True, "adminEventsDetailsEnabled": False,
        "eventsExpiration": 90 * 24 * 3600,
    }, ok=(204,))

    by_id = {}
    for client in spec["clients"]:
        by_id[client["clientId"]] = ensure_client(token, realm, client)

    for client in spec["clients"]:
        current, created = by_id[client["clientId"]]
        path = f"{base}/clients/{current['id']}"
        grants = dict(client.get("clientRoles", {}))
        if client.get("realmManagementRoles"):
            grants["realm-management"] = client["realmManagementRoles"]
        mappings = {target: set(roles) for target, roles in grants.items()}
        for target, roles in client.get("scopeRoles", {}).items():
            mappings.setdefault(target, set()).update(roles)
        if client.get("roles"):
            mappings.setdefault(client["clientId"], set()).update(client["roles"])
        for target, roles in mappings.items():
            scope_roles(token, realm, path, target, sorted(roles))
        ensure_claim_mappers(token, realm, current["id"], client.get("attributeClaims", []))
        # Keycloak admins own assignments after creation. A converge must never restore a revocation.
        if created and grants:
            _, service_user = request("GET", f"{path}/service-account-user", token)
            for target, roles in grants.items():
                assign_client_roles(token, realm, service_user["id"], target, roles)
    ensure_client_scopes(token, realm, by_id)
    protect_scope_attributes(token, base, {name for c in spec["clients"] for name in c.get("attributeClaims", [])})

    seeds = []
    for user in spec["users"]:
        if not os.getenv(user["passwordEnv"]):
            continue
        query = urllib.parse.urlencode({"username": user["username"], "exact": "true"})
        _, found = request("GET", f"{base}/users?{query}", token)
        if found:
            if found[0]["id"] != user["id"]:
                print(f"demo user {user['username']} already has another subject; skipped", file=sys.stderr)
            continue
        seeds.append({
            "id": user["id"], "username": user["username"], "enabled": True,
            "firstName": user.get("firstName"), "lastName": user.get("lastName"),
            "email": user["username"] + "@example.invalid", "emailVerified": True,
            "attributes": user.get("attributes", {}), "clientRoles": user.get("clientRoles", {}),
            "credentials": [{"type": "password", "value": os.environ[user["passwordEnv"]], "temporary": False}],
        })
    if seeds:
        # Partial import preserves explicit subject IDs and assigns roles in the same transaction.
        request("POST", f"{base}/partialImport", token, {"ifResourceExists": "SKIP", "users": seeds})
        for user in seeds:
            _, found = request("GET", f"{base}/users/{user['id']}", token)
            if found["id"] != user["id"]:
                raise RuntimeError(f"unexpected subject for {user['username']}")
    print("keycloak realm converged")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # noqa: BLE001
        print(f"keycloak converge failed: {error}", file=sys.stderr)
        sys.exit(1)
