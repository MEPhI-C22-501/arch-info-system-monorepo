#!/bin/bash
# Запускает четыре эталона и проверки изоляции внутри сети стенда.
set -euo pipefail
cd /work

export OIDC_ISSUER="${OIDC_ISSUER:-http://localhost:8081/realms/arch-info-system}"
export OIDC_JWKS_URI="${OIDC_JWKS_URI:-http://keycloak:8080/realms/arch-info-system/protocol/openid-connect/certs}"
export OIDC_AUDIENCE=example-api
export API_TOKEN="$(python - <<'PY'
import json, os, urllib.parse, urllib.request
form = urllib.parse.urlencode({
    "grant_type": "client_credentials",
    "client_id": "example-caller",
    "client_secret": os.environ["KC_EXAMPLE_CALLER_SECRET"],
}).encode()
request = urllib.request.Request(
    os.environ["KEYCLOAK_INTERNAL_URL"].rstrip("/") + "/realms/arch-info-system/protocol/openid-connect/token",
    data=form,
)
with urllib.request.urlopen(request, timeout=10) as response:
    print(json.loads(response.read())["access_token"])
PY
)"

python /work/infra/examples/web-api/server.py &
SERVER_PID=$!
trap 'kill "$SERVER_PID"' EXIT
for _ in $(seq 1 50); do
  if python - <<'PY' >/dev/null 2>&1
import urllib.request
urllib.request.urlopen("http://127.0.0.1:8090/v1/health/livez", timeout=1).read()
PY
  then
    break
  fi
  sleep 0.2
done

python /work/infra/examples/web-api/check.py
python /work/infra/examples/s3/check.py
python /work/infra/examples/etl/check.py
python /work/infra/examples/kafka/check.py

python - <<'PY'
import json, os, urllib.parse, urllib.request, jwt, requests

base = os.environ["KEYCLOAK_INTERNAL_URL"].rstrip("/")
issuer = os.environ["OIDC_ISSUER"]
jwks_uri = os.environ["OIDC_JWKS_URI"]

def token(client_id, secret):
    form = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": secret,
    }).encode()
    request = urllib.request.Request(base + "/realms/arch-info-system/protocol/openid-connect/token", data=form)
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read())["access_token"]

def call(bearer):
    request = urllib.request.Request("http://127.0.0.1:8090/v1/operations", headers={"Authorization": f"Bearer {bearer}"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code

good = token("example-caller", os.environ["KC_EXAMPLE_CALLER_SECRET"])
claims = jwt.decode(good, options={"verify_signature": False})
if claims.get("iss") != issuer:
    raise SystemExit(f"unexpected issuer {claims.get('iss')}")
if call(good) != 200:
    raise SystemExit("valid token was rejected")
if call(token("example-stranger", os.environ["KC_EXAMPLE_STRANGER_SECRET"])) != 401:
    raise SystemExit("foreign audience was accepted")
if call("not-a-token") != 401:
    raise SystemExit("garbage token was accepted")
keys = requests.get(jwks_uri, timeout=5).json()["keys"]
if not keys:
    raise SystemExit("jwks empty")
print("oidc checks passed")
PY

python - <<'PY'
import json, os, urllib.request
payload = {
  "resourceSpans": [{
    "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "infra-smoke"}}]},
    "scopeSpans": [{"spans": [{
      "traceId": "0123456789abcdef0123456789abcdef",
      "spanId": "0123456789abcdef",
      "name": "infra-smoke",
      "kind": 1,
      "startTimeUnixNano": "1690000000000000000",
      "endTimeUnixNano": "1690000001000000000"
    }]}]
  }]
}
request = urllib.request.Request(
    "http://otel-collector:4318/v1/traces",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(request, timeout=5) as response:
    if response.status != 200:
        raise SystemExit(response.status)
print("otel signal sent")
PY

for _ in $(seq 1 30); do
  if grep -q infra-smoke /var/lib/otel/signals.json 2>/dev/null; then
    echo "otel signal stored"
    exit 0
  fi
  sleep 0.5
done
echo "collector did not store the test span" >&2
exit 1
