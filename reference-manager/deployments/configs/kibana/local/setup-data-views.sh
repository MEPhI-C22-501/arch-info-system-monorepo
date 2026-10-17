#!/usr/bin/env bash
# creates the Kibana data views of the telemetry, it is run once after Kibana is up,
# the fixed ids and override make a repeated run update the views instead of duplicating them
set -euo pipefail

KIBANA_URL="${KIBANA_URL:-http://reference-manager-kibana:5601}"

create_data_view() {
  local id="$1" name="$2" pattern="$3"

  curl -sSf -X POST "${KIBANA_URL}/api/data_views/data_view" \
    -H 'kbn-xsrf: true' \
    -H 'Content-Type: application/json' \
    -d "{\"override\": true, \"data_view\": {\"id\": \"${id}\", \"name\": \"${name}\", \"title\": \"${pattern}\", \"timeFieldName\": \"@timestamp\"}}" \
    -o /dev/null

  echo "data view ${name} (${pattern}) is ready"
}

create_data_view reference-manager-logs "reference-manager logs" "logs-*.otel-*"
create_data_view reference-manager-traces "reference-manager traces" "traces-*.otel-*"
create_data_view reference-manager-metrics "reference-manager metrics" "metrics-*.otel-*"
