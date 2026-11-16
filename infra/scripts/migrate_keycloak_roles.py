#!/usr/bin/env python3
"""Preview and apply reviewed migrations. The journal prevents automatic regrants."""

import argparse
import fcntl
import hashlib
import json
import os
import urllib.parse
import uuid
from collections import Counter
from pathlib import Path

from keycloak_converge import assign_client_roles, find_client, request, wait_ready

ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / "keycloak/realm/desired.json").read_text())
CLIENTS = {row["clientId"]: row for row in CATALOG["clients"]}
PLANNING = dict(zip(
    ("R-01", "R-02", "R-03", "R-04", "R-05", "R-06"),
    ("PORTFOLIO_OWNER", "PLANNER", "PROJECT_MANAGER", "RESOURCE_MANAGER", "TEAM_MEMBER", "MODULE_ADMIN"),
))
HUMAN = {
    "task-tracker": {"MEMBER", "LEAD", "ADMIN"},
    "planning-system": set(PLANNING.values()),
    "reference-manager": {"reference-reader", "reference-admin", "reference-hr-admin", "reference-hr-reader"},
    "reports": {"reports-project-manager", "reports-team-lead", "reports-qa-lead",
                "reports-member", "reports-analyst", "reports-admin"},
    "qa-system": {"qa-viewer", "qa-tester", "qa-automation", "qa-lead", "qa-admin"},
}


def identity(subject):
    return isinstance(subject, str) and uuid.UUID(subject).__str__() == subject


def migrate_role(row):
    client, source, role = row["client"], row["source"], row["role"]
    if source == "local_access" and client == "task-tracker" and role in HUMAN[client]:
        return role
    if source == "realm" and client in {"planning-system", "reference-manager"}:
        candidate = PLANNING.get(role, role) if client == "planning-system" else role
        if candidate in HUMAN[client]:
            return candidate
    if source == "service":
        permissions = CLIENTS.get(row.get("serviceClient"), {}).get("clientRoles", {})
        if role in permissions.get(client, []):
            return role
    return None


class Realm:
    def __init__(self, issuer, token):
        parsed = urllib.parse.urlsplit(issuer)
        if parsed.username or parsed.password or parsed.query or parsed.fragment or not parsed.hostname:
            raise ValueError("Invalid issuer")
        if not parsed.path.endswith("/realms/" + CATALOG["realm"]):
            raise ValueError("Issuer does not identify the target realm")
        self.realm = CATALOG["realm"]
        _, discovery = request("GET", f"/realms/{self.realm}/.well-known/openid-configuration")
        if discovery["issuer"] != issuer:
            raise ValueError("Configured Keycloak advertises a different issuer")
        self.base = "/admin/realms/" + self.realm
        self.token = token
        self.issuer = issuer
        self.clients = {}

    def get(self, path, allow_missing=False):
        status, body = request("GET", self.base + path, self.token,
                               ok=(200, 404) if allow_missing else (200,))
        return body if status == 200 else None

    def roles(self, subject, client, suffix=""):
        if client not in self.clients:
            found = find_client(self.token, self.realm, client)
            if not found:
                raise ValueError("Target client is missing: " + client)
            self.clients[client] = found["id"]
        path = f"/users/{subject}/role-mappings/clients/{self.clients[client]}{suffix}"
        return {role["name"] for role in self.get(path)}


def evaluate(kc, row):
    item = {**row, "status": "conflict"}
    try:
        subject = row["sub"]
        if row["iss"] != kc.issuer or not identity(subject):
            return {**item, "reason": "UNVERIFIED_IDENTITY"}
        target = migrate_role(row)
        if target is None:
            return {**item, "reason": "UNMAPPED_ROLE"}
    except (KeyError, TypeError, ValueError):
        return {**item, "reason": "INVALID_SOURCE"}
    item["targetRole"] = target
    user = kc.get("/users/" + subject, allow_missing=True)
    if not user or user["id"] != subject:
        return {**item, "reason": "UNKNOWN_SUBJECT"}
    direct = kc.roles(subject, row["client"])
    inherited = kc.roles(subject, row["client"], "/composite") - direct
    item.update(username=user.get("username"), direct=sorted(direct), inherited=sorted(inherited))
    if row.get("allowed") is not True or user.get("enabled") is not True:
        return {**item, "status": "blocked", "reason": "LEGACY_OR_ACCOUNT_DISABLED"}
    if row["source"] == "service":
        if user.get("serviceAccountClientId") != row.get("serviceClient"):
            return {**item, "reason": "SERVICE_ACCOUNT_MISMATCH"}
    elif user.get("serviceAccountClientId"):
        return {**item, "reason": "EXPECTED_USER"}
    if row["source"] == "realm":
        path = f"/users/{subject}/role-mappings/realm"
        current = {role["name"] for role in kc.get(path)}
        if row["role"] not in current:
            effective = {role["name"] for role in kc.get(path + "/composite")}
            reason = "REVIEW_GROUP_OR_COMPOSITE" if row["role"] in effective else "SOURCE_ROLE_MISSING"
            return {**item, "reason": reason}
    return {**item, "status": "present" if target in direct | inherited else "ready"}


def preview(kc, rows):
    blocked = {(r.get("sub"), r.get("client")) for r in rows if r.get("allowed") is False}
    local_counts = Counter((r.get("sub"), r.get("client")) for r in rows if r.get("source") == "local_access")
    results = []
    for row in rows:
        result = evaluate(kc, row)
        key = row.get("sub"), row.get("client")
        if result["status"] == "ready" and (key in blocked or local_counts[key] > 1):
            result.update(status="conflict",reason="CONTRADICTORY_SOURCE")
        results.append(result)
    return {"issuer": kc.issuer, "rows": results}


def apply(kc, report, journal_path):
    if report["issuer"] != kc.issuer:
        raise ValueError("Report issuer does not match")
    candidates = [row for row in report["rows"] if row.get("status") == "ready"]
    # Confirm the legacy source still exists and the target did not change after the preview.
    refreshed = preview(kc, report["rows"])
    checks = {key(row): row for row in refreshed["rows"] if "targetRole" in row}
    with os.fdopen(os.open(journal_path, os.O_CREAT | os.O_RDWR | os.O_APPEND, 0o600), "a+") as journal:
        fcntl.flock(journal, fcntl.LOCK_EX)
        journal.seek(0)
        attempted = {json.loads(line)["key"] for line in journal if line.strip()}
        for row in candidates:
            current = checks.get(key(row), {})
            if key(row) in attempted or current.get("status") != "ready":
                continue
            if not all(current.get(field) == row.get(field) for field in ("targetRole", "direct", "inherited")):
                continue
            entry = {"key": key(row), "sub": row["sub"], "client": row["client"], "role": row["targetRole"]}
            # Journal the intent first. An interrupted call must be reconciled by an operator.
            append(journal, {**entry, "state":"attempted"})
            attempted.add(entry["key"])
            assign_client_roles(kc.token, kc.realm, row["sub"], row["client"], [row["targetRole"]])
            append(journal, {**entry, "state":"applied"})


def key(row):
    coordinates = [row["iss"], row["sub"], row["client"], row["targetRole"]]
    return hashlib.sha256(json.dumps(coordinates).encode()).hexdigest()


def append(journal, event):
    journal.write(json.dumps(event) + "\n")
    journal.flush()
    os.fsync(journal.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issuer", required=True)
    modes = parser.add_subparsers(dest="mode", required=True)
    modes.add_parser("preview").add_argument("source", type=Path)
    execute = modes.add_parser("apply")
    execute.add_argument("report", type=Path)
    execute.add_argument("--journal", required=True, type=Path)
    args = parser.parse_args()
    kc = Realm(args.issuer.rstrip("/"), wait_ready())
    if args.mode == "preview":
        print(json.dumps(preview(kc, json.loads(args.source.read_text())), ensure_ascii=False, indent=2))
    else:
        apply(kc, json.loads(args.report.read_text()), args.journal)


if __name__ == "__main__":
    main()
