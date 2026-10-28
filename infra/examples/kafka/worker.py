#!/usr/bin/env python3
"""Потребитель эталона: дедупликация, повторы в том же разделе, DLQ и commit после исхода."""

from __future__ import annotations

import json
import os
import sqlite3
import time

import jsonschema
from confluent_kafka import Consumer, KafkaError, Producer

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = (0.2, 0.4, 0.8)
TOPIC = os.environ.get("EXAMPLE_TOPIC", "dev.infra.examples.v1")
DLQ_TOPIC = os.environ.get("DLQ_TOPIC", "dev.infra.examples.v1.dlq")
STATE = os.environ.get("EXAMPLE_STATE", "/tmp/example-state.sqlite")

ENVELOPE = {
    "type": "object",
    "required": ["eventId", "eventType", "occurredAt", "schemaVersion", "payload"],
    "properties": {
        "eventId": {"type": "string", "minLength": 1},
        "eventType": {"type": "string"},
        "occurredAt": {"type": "string"},
        "schemaVersion": {"type": "string"},
        "payload": {"type": "object"},
    },
    "additionalProperties": True,
}


def client_config(group: str | None = None) -> dict:
    config = {
        "bootstrap.servers": os.environ.get("KAFKA_BOOTSTRAP", "kafka:9092"),
        "security.protocol": "SASL_SSL",
        "sasl.mechanisms": "PLAIN",
        "sasl.username": os.environ["KAFKA_USERNAME"],
        "sasl.password": os.environ["KAFKA_PASSWORD"],
        "ssl.ca.location": os.environ.get("KAFKA_CA", "/certs/kafka.crt"),
    }
    if group:
        config.update(
            {
                "group.id": group,
                "enable.auto.commit": False,
                "auto.offset.reset": "earliest",
                "session.timeout.ms": 6000,
                "heartbeat.interval.ms": 2000,
            }
        )
    return config


def db() -> sqlite3.Connection:
    connection = sqlite3.connect(STATE)
    connection.execute(
        "CREATE TABLE IF NOT EXISTS applied (event_id TEXT PRIMARY KEY, result TEXT NOT NULL)"
    )
    return connection


def publish_dlq(producer: Producer, original: dict, reason: str, attempts: int, source) -> None:
    record = {
        "sourceTopic": source.topic(),
        "sourcePartition": source.partition(),
        "sourceOffset": source.offset(),
        "eventId": original.get("eventId"),
        "reason": reason,
        "attempts": attempts,
        "original": original,
    }
    errors: list[str] = []

    def delivered(err, _message) -> None:
        if err is not None:
            errors.append(str(err))

    producer.produce(
        DLQ_TOPIC,
        json.dumps(record).encode(),
        key=str(original.get("eventId") or "invalid"),
        on_delivery=delivered,
    )
    remaining = producer.flush(10)
    if remaining or errors:
        raise RuntimeError(f"dlq unavailable: {errors or remaining}")


def handle(message_body: dict, connection: sqlite3.Connection) -> str:
    jsonschema.validate(message_body, ENVELOPE)
    event_id = message_body["eventId"]
    row = connection.execute("SELECT result FROM applied WHERE event_id = ?", (event_id,)).fetchone()
    if row:
        return "duplicate"
    mode = message_body["payload"].get("mode", "ok")
    if mode == "always-fail":
        raise RuntimeError("retryable processing failure")
    if mode == "bad-data":
        raise ValueError("non-retryable payload")
    connection.execute("INSERT INTO applied (event_id, result) VALUES (?, ?)", (event_id, mode))
    connection.commit()
    if mode == "crash-once" and not os.path.exists(STATE + ".crashed"):
        open(STATE + ".crashed", "w", encoding="utf-8").write(event_id)
        os._exit(99)
    return "applied"


def process_one(consumer: Consumer, producer: Producer, connection: sqlite3.Connection, timeout: float) -> str:
    message = consumer.poll(timeout)
    if message is None:
        return "idle"
    if message.error():
        if message.error().code() == KafkaError._PARTITION_EOF:
            return "idle"
        raise RuntimeError(message.error())
    raw = message.value()
    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        body = {"invalid": True}
    expected = os.environ.get("EXAMPLE_EVENT_ID")
    if expected:
        candidate = body.get("eventId") if isinstance(body, dict) else None
        if candidate != expected:
            consumer.commit(message=message, asynchronous=False)
            return "skip"
    attempts = 0
    outcome = "dlq"
    reason = "schema"
    try:
        jsonschema.validate(body, ENVELOPE)
    except jsonschema.ValidationError as error:
        publish_dlq(producer, body if isinstance(body, dict) else {"raw": raw.decode(errors="replace")}, str(error.message), 1, message)
        consumer.commit(message=message, asynchronous=False)
        return "dlq"
    while attempts < MAX_ATTEMPTS:
        attempts += 1
        try:
            outcome = handle(body, connection)
            reason = ""
            break
        except ValueError as error:
            reason = str(error)
            outcome = "dlq"
            break
        except Exception as error:  # noqa: BLE001
            reason = str(error)
            outcome = "retry"
            if attempts >= MAX_ATTEMPTS:
                outcome = "dlq"
                break
            time.sleep(BACKOFF_SECONDS[attempts - 1])
    if outcome == "dlq":
        publish_dlq(producer, body, reason, attempts, message)
    consumer.commit(message=message, asynchronous=False)
    return outcome


def main() -> None:
    group = os.environ["KAFKA_GROUP"]
    consumer = Consumer(client_config(group))
    producer = Producer(client_config())
    consumer.subscribe([TOPIC])
    connection = db()
    deadline = time.time() + float(os.environ.get("WORKER_SECONDS", "20"))
    seen = []
    while time.time() < deadline:
        outcome = process_one(consumer, producer, connection, 1.0)
        if outcome not in ("idle", "skip"):
            seen.append(outcome)
            if os.environ.get("WORKER_STOP_AFTER") and len(seen) >= int(os.environ["WORKER_STOP_AFTER"]):
                break
    consumer.unsubscribe()
    consumer.close()
    print(json.dumps({"outcomes": seen}))


if __name__ == "__main__":
    main()
