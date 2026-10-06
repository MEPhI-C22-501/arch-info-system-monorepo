#!/bin/bash
# Бакеты и отдельные ключи команд. Повтор не удаляет объекты.
set -euo pipefail

: "${MINIO_ROOT_USER:?}"
: "${MINIO_ROOT_PASSWORD:?}"

mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"

create_bucket() {
  mc mb --ignore-existing "local/$1"
  mc anonymous set none "local/$1" >/dev/null
}

put_policy() {
  local name="$1" file="$2"
  if mc admin policy create local "$name" "$file" 2>/dev/null; then
    return 0
  fi
  mc admin policy add local "$name" "$file"
}

attach_policy() {
  local policy="$1" user="$2"
  if mc admin policy attach local "$policy" --user "$user" 2>/dev/null; then
    return 0
  fi
  mc admin policy set local "$policy" user="$user"
}

ensure_user() {
  local user="$1" password="$2" policy="$3" file="$4"
  if ! mc admin user info local "$user" >/dev/null 2>&1; then
    mc admin user add local "$user" "$password"
  fi
  put_policy "$policy" "$file"
  attach_policy "$policy" "$user"
}

create_bucket arch-dev-task-tracker
create_bucket arch-dev-planning-system
create_bucket arch-dev-reference-manager
create_bucket arch-dev-reports
create_bucket arch-dev-qa
create_bucket arch-dev-infra
create_bucket arch-dev-examples
create_bucket arch-dev-stranger

ensure_user task-tracker "$S3_TASK_TRACKER_SECRET" task-tracker-own /policies/task-tracker.json
ensure_user planning-system "$S3_PLANNING_SECRET" planning-own /policies/planning.json
ensure_user reference-manager "$S3_REFERENCE_MANAGER_SECRET" reference-own /policies/reference-manager.json
ensure_user reports "$S3_REPORTS_SECRET" reports-own /policies/reports.json
ensure_user qa-system "$S3_QA_SECRET" qa-own /policies/qa.json
ensure_user example-writer "$S3_EXAMPLE_WRITER_SECRET" example-own /policies/examples.json
ensure_user example-reader "$S3_EXAMPLE_READER_SECRET" example-read /policies/examples-read.json
ensure_user example-stranger "$S3_EXAMPLE_STRANGER_SECRET" stranger-own /policies/stranger.json

echo "minio buckets and users converged"
