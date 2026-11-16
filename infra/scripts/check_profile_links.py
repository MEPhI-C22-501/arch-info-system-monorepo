#!/usr/bin/env python3
"""Preview exact Reference Manager profile links. The script never changes assignments."""

import argparse
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args):
        return None


def endpoint(value, allow_http):
    parsed = urllib.parse.urlsplit(value)
    if (not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment
            or (parsed.scheme != "https" and not (allow_http and parsed.scheme == "http"))):
        raise ValueError("Expected a trusted HTTPS endpoint")
    return value.rstrip("/")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("references", type=Path)
    parser.add_argument("--issuer", required=True)
    parser.add_argument("--allow-http", action="store_true", help="Isolated development only")
    args = parser.parse_args()
    base = endpoint(os.environ["RM_BASE_URL"], args.allow_http)
    token_url = endpoint(os.environ["RM_TOKEN_URL"], args.allow_http)
    opener = urllib.request.build_opener(NoRedirect)
    form = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": os.environ["RM_CLIENT_ID"],
        "client_secret": os.environ["RM_CLIENT_SECRET"],
    }).encode()
    with opener.open(urllib.request.Request(token_url, data=form), timeout=10) as response:
        token = json.load(response)["access_token"]
    rows = json.loads(args.references.read_text())
    output = []
    resolved = {}
    keys = sorted({(row["kind"], row["id"]) for row in rows})
    for index in range(0, len(keys), 100):
        batch = keys[index:index + 100]
        payload = json.dumps({"keys": [{"kind": kind, "id": identifier} for kind, identifier in batch]})
        call = urllib.request.Request(base + "/profiles/resolve", data=payload.encode(), headers={
            "Content-Type": "application/json", "Authorization": "Bearer " + token,
        })
        with opener.open(call, timeout=10) as response:
            matches = json.load(response)["items"]
        if [(item["key"]["kind"], item["key"]["id"]) for item in matches] != batch:
            raise ValueError("Reference Manager returned different or duplicated keys")
        for key, item in zip(batch, matches):
            resolved[key] = item["profile"]
    for row in rows:
        profile = resolved[row["kind"], row["id"]]
        if not profile:
            output.append({**row, "status": "missing"})
        elif row.get("iss", args.issuer) != args.issuer or profile["issuer"] != args.issuer:
            output.append({**row, "status": "issuer_conflict"})
        elif (row.get("expectedEmployeeId") is not None
              and str(profile["employeeId"]) != str(row["expectedEmployeeId"])):
            output.append({**row, "status": "employee_conflict"})
        else:
            output.append({**row, "status": "matched", "employeeId": profile["employeeId"],
                           "userId": profile["userId"], "isActive": profile["isActive"]})
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
