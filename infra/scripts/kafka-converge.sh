#!/bin/bash
# Создаёт согласованные топики и ACL. Повтор не удаляет данные топиков.
set -euo pipefail

BOOTSTRAP="${KAFKA_BOOTSTRAP:-kafka:9092}"
CMD=(/opt/kafka/bin/kafka-topics.sh --bootstrap-server "$BOOTSTRAP" --command-config /var/lib/kafka/config/admin.properties)
ACL=(/opt/kafka/bin/kafka-acls.sh --bootstrap-server "$BOOTSTRAP" --command-config /var/lib/kafka/config/admin.properties)

create_topic() {
  local name="$1" partitions="$2" retention_ms="$3" max_bytes="$4"
  "${CMD[@]}" --create --if-not-exists --topic "$name" \
    --partitions "$partitions" --replication-factor 1 \
    --config "retention.ms=${retention_ms}" \
    --config "max.message.bytes=${max_bytes}"
}

allow() {
  local principal="$1" topic="$2"
  shift 2
  "${ACL[@]}" --add --allow-principal "User:${principal}" --topic "$topic" "$@" \
    || true
}

allow_group() {
  local principal="$1" group="$2"
  shift 2
  "${ACL[@]}" --add --allow-principal "User:${principal}" --group "$group" \
    --operation Read --operation Describe "$@" || true
}

# 7 суток. Бизнес-топики остаются draft: создание инфраструктуры не означает согласие издателя.
create_topic task-tracker.events.v1 3 604800000 1048576
create_topic dev.qa.test-run.v1 3 604800000 262144
create_topic dev.qa.defect.v1 3 604800000 262144
create_topic dev.infra.examples.v1 1 604800000 1048576
create_topic dev.infra.examples.v1.dlq 1 604800000 1048576

allow task_tracker task-tracker.events.v1 --operation Write --operation Describe
allow planning task-tracker.events.v1 --operation Read --operation Describe
allow reports task-tracker.events.v1 --operation Read --operation Describe
allow_group planning planning-task-tracker
allow_group reports reports-task-tracker

allow qa dev.qa.test-run.v1 --operation Write --operation Describe
allow qa dev.qa.defect.v1 --operation Write --operation Describe
allow reports dev.qa.test-run.v1 --operation Read --operation Describe
allow reports dev.qa.defect.v1 --operation Read --operation Describe
allow_group reports reports-qa-ingest

allow example dev.infra.examples.v1 --operation Write --operation Read --operation Describe
allow example dev.infra.examples.v1.dlq --operation Write --operation Read --operation Describe
# Префикс: каждая проверка создаёт новую группу example-workers-<uuid>, чтобы не читать старые offset.
allow_group example example-workers --resource-pattern-type prefixed

# QA не получает запись в топик Task Tracker: входящий контракт не согласован.
echo "kafka topics and acls converged"
