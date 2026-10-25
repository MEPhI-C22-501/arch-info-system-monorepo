"""Source-owned pagination. No mutation of Tracker, QA or HR data."""
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections import Counter
from datetime import datetime, timezone

# Fixed namespace: the same portfolio and slot always give the same key, so a
# retried or repeated POST /exports returns the owner's stored batch.
EXPORT_KEY_NAMESPACE = uuid.UUID("6f3c2a1e-9b7d-5e4f-8a2c-1d0e9f8b7a65")


class Rejected(ValueError):
    """A whole extraction is rejected; the last checkpoint stays intact."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Do not forward Authorization to another endpoint.


class Client:
    def __init__(self, base, token=None, *, allow_http=False, interval=0.2):
        url = urllib.parse.urlsplit(base)
        if url.username or url.password or url.query or url.fragment:
            raise ValueError("Base URL must not contain credentials, query or fragment")
        if url.scheme != "https" and not (allow_http and url.scheme == "http"):
            raise ValueError("HTTPS required; allow HTTP explicitly for a local stand")
        self.base, self.token, self.interval = base.rstrip("/"), token, interval
        self.last_request = 0.0
        self.opener = urllib.request.build_opener(NoRedirect)

    def request(self, path, params=None, body=None, *, idempotency_key=None):
        if not path.startswith("/") or ".." in path or "?" in path:
            raise ValueError("Invalid source path")
        url = self.base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        data = None if body is None else json.dumps(body).encode()
        if data is not None:
            headers["Content-Type"] = "application/json"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        # A POST is retried only with an Idempotency-Key: the owner replays the
        # stored response, so a lost reply cannot create a second object.
        attempts = 4 if body is None or idempotency_key else 1
        for attempt in range(attempts):
            time.sleep(max(0, self.last_request + self.interval - time.monotonic()))
            self.last_request = time.monotonic()
            try:
                req = urllib.request.Request(url, data=data, headers=headers)
                with self.opener.open(req, timeout=10) as response:
                    raw = response.read(16 * 1024 * 1024 + 1)
                if len(raw) > 16 * 1024 * 1024:
                    raise Rejected("RESPONSE_TOO_LARGE")
                return json.loads(raw)
            except urllib.error.HTTPError as error:
                if error.code not in (429, 500, 502, 503, 504) or attempt == attempts - 1:
                    raise Rejected(f"SOURCE_HTTP_{error.code}") from None
            except (urllib.error.URLError, TimeoutError):
                if attempt == attempts - 1:
                    raise Rejected("SOURCE_UNAVAILABLE") from None
            except (json.JSONDecodeError, UnicodeDecodeError):
                raise Rejected("INVALID_JSON") from None
            time.sleep(2 ** (attempt + 1))


def unique(rows, field="id"):
    ids = [r.get(field) for r in rows]
    if any(x is None or isinstance(x, (bool, dict, list)) or x == "" for x in ids):
        raise Rejected("MISSING_ID")
    if len({str(x) for x in ids}) != len(ids):
        raise Rejected("DUPLICATE_ID")
    return rows


def integer(value, minimum=0):
    if type(value) is not int or value < minimum:
        raise Rejected("INVALID_PAGE_METADATA")
    return value


def numbered(client, resource, *, tracker=True, page_size=100, validate=None):
    rows, expected = [], None
    for page in range(1, 10001):
        result = client.request("/api/v1/reports/" + resource,
                                {"page": page, "pageSize": page_size})
        if not isinstance(result, dict) or not isinstance(result.get("items"), list):
            raise Rejected("INVALID_PAGE")
        total_pages = integer(result.get("totalPages"))
        size = integer(result.get("pageSize"), 1)
        if integer(result.get("page"), 1) != page or size != page_size:
            raise Rejected("PAGE_MISMATCH")
        total = integer(result.get("total")) if tracker else None
        metadata = (total_pages, total)
        if expected is None:
            expected = metadata
        if metadata != expected or total_pages > 10000:
            raise Rejected("UNSTABLE_PAGES")
        if tracker and total_pages != math.ceil(total / size):
            raise Rejected("COUNT_MISMATCH")
        items = result["items"]
        if len(items) > size or (page < total_pages and len(items) != size):
            raise Rejected("INCOMPLETE_PAGE")
        if total_pages and not items:
            raise Rejected("EMPTY_PAGE")
        if not total_pages and items:
            raise Rejected("COUNT_MISMATCH")
        for item in items:
            if not isinstance(item, dict):
                raise Rejected("INVALID_ITEM")
            if validate:
                validate(item)
        rows.extend(items)
        if page >= total_pages:
            if tracker and len(rows) != total:
                raise Rejected("COUNT_MISMATCH")
            return unique(rows)
    raise Rejected("PAGE_LIMIT")


HR_RESOURCES = {"employees", "org_units", "positions", "project_roles", "grades"}
QA_RESOURCES = {"test-cases", "test-plans", "test-runs", "test-results", "defects"}


def reference(client, resource):
    if resource not in HR_RESOURCES:
        raise Rejected("UNSUPPORTED_HR_RESOURCE")
    rows, seen, token = [], set(), None
    for _ in range(10000):
        params = {"pageSize": 100, "allowDeleted": "true"}
        if token:
            params["pageToken"] = token
        result = client.request("/v1/" + resource + "/", params)
        if not isinstance(result, dict) or not isinstance(result.get(resource), list):
            raise Rejected("INVALID_HR_PAGE")
        for row in result[resource]:
            if not isinstance(row, dict) or type(row.get("id")) is not int or row["id"] <= 0:
                raise Rejected("INVALID_HR_ID")
        rows.extend(result[resource])
        token = result.get("nextPageToken")
        if not token:
            return unique(rows)
        if not isinstance(token, str) or token in seen or not result[resource]:
            raise Rejected("REPEATED_CURSOR")
        seen.add(token)
    raise Rejected("PAGE_LIMIT")


def export_slot(moment=None):
    """One UTC hour: at most one new Planning batch per portfolio per slot."""
    return (moment or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H")


def export_key(portfolio_id, slot):
    return str(uuid.uuid5(EXPORT_KEY_NAMESPACE, f"reports:planning-export:v1:{portfolio_id}:{slot}"))


def planning(client, portfolio_id, slot=None):
    created = client.request("/api/v1/exports", body={"portfolioId": portfolio_id},
                             idempotency_key=export_key(portfolio_id, slot or export_slot()))
    batch_id = created.get("batchId")
    if not isinstance(batch_id, str) or not batch_id or "/" in batch_id:
        raise Rejected("INVALID_BATCH_ID")
    if created.get("portfolioId") not in (None, portfolio_id):
        raise Rejected("FOREIGN_BATCH")
    path = "/api/v1/exports/" + batch_id
    manifest = client.request(path)
    validate_manifest(manifest, batch_id)
    if manifest.get("portfolioId") not in (None, portfolio_id):
        raise Rejected("FOREIGN_BATCH")
    rows, cursors, cursor = [], set(), None
    for _ in range(10000):
        params = {"pageSize": 200}
        if cursor:
            params["cursor"] = cursor
        page = client.request(path + "/rows", params)
        if page.get("batchId") != batch_id or page.get("dataAsOf") != manifest["dataAsOf"]:
            raise Rejected("BATCH_MISMATCH")
        items = page.get("items")
        if not isinstance(items, list) or len(items) > 200:
            raise Rejected("INVALID_BATCH_PAGE")
        rows.extend(items)
        cursor = page.get("nextCursor")
        if not cursor:
            break
        if not isinstance(cursor, str) or cursor in cursors or not items:
            raise Rejected("REPEATED_CURSOR")
        cursors.add(cursor)
    else:
        raise Rejected("PAGE_LIMIT")
    counts = Counter()
    keys = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("data"), dict):
            raise Rejected("INVALID_BATCH_ROW")
        kind, eid = row.get("entityType"), row.get("entityId")
        if kind not in {"plan", "demand", "availability", "allocation", "forecast"} or not isinstance(eid, str) or not eid:
            raise Rejected("INVALID_BATCH_ROW")
        if (kind, eid) in keys:
            raise Rejected("DUPLICATE_ID")
        keys.add((kind, eid))
        counts[kind] += 1
    expected = {c["entityType"]: c["count"] for c in manifest["counts"]}
    if any(counts[k] != n for k, n in expected.items()) or set(counts) - set(expected):
        raise Rejected("COUNT_MISMATCH")
    # Check expiry and permission changes again before exposing the batch.
    after = client.request(path)
    validate_manifest(after, batch_id)
    if any(after[k] != manifest[k] for k in ("counts", "dataAsOf", "schemaVersion")):
        raise Rejected("UNSTABLE_MANIFEST")
    return manifest, rows


def validate_manifest(manifest, batch_id):
    if manifest.get("batchId") != batch_id or manifest.get("status") != "READY":
        raise Rejected("BATCH_NOT_READY")
    if manifest.get("schemaVersion") != "1.0.0":
        raise Rejected("UNSUPPORTED_SCHEMA")
    try:
        expiry = datetime.fromisoformat(manifest["expiresAt"].replace("Z", "+00:00"))
        datetime.fromisoformat(manifest["dataAsOf"].replace("Z", "+00:00"))
        if expiry <= datetime.now(timezone.utc):
            raise Rejected("BATCH_EXPIRED")
        counts = manifest["counts"]
        kinds = [c["entityType"] for c in counts]
        if set(kinds) != {"plan", "demand", "availability", "allocation", "forecast"} or len(kinds) != 5:
            raise Rejected("INVALID_MANIFEST")
        for count in counts:
            integer(count["count"])
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, Rejected):
            raise
        raise Rejected("INVALID_MANIFEST") from None
