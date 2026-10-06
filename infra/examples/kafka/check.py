#!/usr/bin/env python3
"""Проверяет успех, дубль, падение до commit, исчерпание попыток, недоступный DLQ и восстановление."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time
import uuid
from pathlib import Path

from confluent_kafka import Consumer, Producer

TOPIC = "dev.infra.examples.v1"
DLQ = "dev.infra.examples.v1.dlq"
STATE = os.environ.get("EXAMPLE_STATE", "/tmp/example-state.sqlite")
GROUP = os.environ.get("KAFKA_GROUP", f"example-workers-{uuid.uuid4()}")
WORKER = str(Path(__file__).with_name("worker.py"))


def producer(username: str, password: str) -> Producer:
    return Producer(
        {
            "bootstrap.servers": os.environ.get("KAFKA_BOOTSTRAP", "kafka:9092"),
            "security.protocol": "SASL_SSL",
            "sasl.mechanisms": "PLAIN",
            "sasl.username": username,
            "sasl.password": password,
            "ssl.ca.location": os.environ.get("KAFKA_CA", "/certs/kafka.crt"),
        }
    )


def send(username: str, password: str, body: dict, topic: str = TOPIC) -> None:
    client = producer(username, password)
    client.produce(topic, json.dumps(body).encode(), key=body.get("eventId", "invalid"))
    remaining = client.flush(10)
    if remaining:
        raise RuntimeError(f"publish failed for {username} topic {topic}")


def event(mode: str, event_id: str | None = None) -> dict:
    return {
        "eventId": event_id or str(uuid.uuid4()),
        "eventType": "ExampleObserved",
        "occurredAt": "2026-10-06T09:00:00Z",
        "schemaVersion": "1.0.0",
        "payload": {"mode": mode},
    }


def run_worker(stop_after: int, dlq: str = DLQ, seconds: int = 40) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "KAFKA_USERNAME": "example",
            "KAFKA_PASSWORD": os.environ["KAFKA_EXAMPLE_PASSWORD"],
            "KAFKA_GROUP": GROUP,
            "DLQ_TOPIC": dlq,
            "EXAMPLE_STATE": STATE,
            "EXAMPLE_EVENT_ID": os.environ.get("EXAMPLE_EVENT_ID", ""),
            "WORKER_STOP_AFTER": str(stop_after),
            "WORKER_SECONDS": str(seconds),
        }
    )
    return subprocess.run([sys.executable, WORKER], env=env, text=True, capture_output=True, check=False)


def applied_count() -> int:
    if not os.path.exists(STATE):
        return 0
    connection = sqlite3.connect(STATE)
    return connection.execute("SELECT COUNT(*) FROM applied").fetchone()[0]


def read_dlq() -> list[dict]:
    consumer = Consumer(
        {
            "bootstrap.servers": os.environ.get("KAFKA_BOOTSTRAP", "kafka:9092"),
            "security.protocol": "SASL_SSL",
            "sasl.mechanisms": "PLAIN",
            "sasl.username": "example",
            "sasl.password": os.environ["KAFKA_EXAMPLE_PASSWORD"],
            "ssl.ca.location": os.environ.get("KAFKA_CA", "/certs/kafka.crt"),
            "group.id": f"example-workers-dlq-{uuid.uuid4()}",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
            "session.timeout.ms": 6000,
            "heartbeat.interval.ms": 2000,
        }
    )
    consumer.subscribe([DLQ])
    found = []
    deadline = time.time() + 8
    while time.time() < deadline:
        message = consumer.poll(1.0)
        if message is None or message.error():
            continue
        found.append(json.loads(message.value()))
    consumer.close()
    return found


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    for path in (STATE, STATE + ".crashed"):
        if os.path.exists(path):
            os.remove(path)
    password = os.environ["KAFKA_EXAMPLE_PASSWORD"]
    success = event("ok")
    os.environ["EXAMPLE_EVENT_ID"] = success["eventId"]
    send("example", password, success)
    result = run_worker(1)
    expect(result.returncode == 0, result.stderr or result.stdout)
    expect(applied_count() == 1, "success was not stored")

    send("example", password, success)
    result = run_worker(1)
    expect(result.returncode == 0, result.stderr)
    expect("duplicate" in result.stdout, result.stdout)
    expect(applied_count() == 1, "duplicate was applied twice")

    crashed = event("crash-once")
    os.environ["EXAMPLE_EVENT_ID"] = crashed["eventId"]
    send("example", password, crashed)
    result = run_worker(1)
    expect(result.returncode == 99, f"crash exit {result.returncode} {result.stderr}")
    expect(applied_count() == 2, "result was not stored before crash")
    result = run_worker(1)
    expect(result.returncode == 0, result.stderr)
    expect("duplicate" in result.stdout, result.stdout)
    expect(applied_count() == 2, "redelivery applied the crashed event again")

    failing = event("always-fail")
    os.environ["EXAMPLE_EVENT_ID"] = failing["eventId"]
    send("example", password, failing)
    result = run_worker(1)
    expect(result.returncode == 0, result.stderr)
    expect("dlq" in result.stdout, result.stdout)

    invalid = {"eventType": "ExampleObserved"}
    os.environ["EXAMPLE_EVENT_ID"] = ""
    send("example", password, invalid)
    result = run_worker(1)
    expect(result.returncode == 0 and "dlq" in result.stdout, result.stdout or result.stderr)

    retained = event("always-fail")
    os.environ["EXAMPLE_EVENT_ID"] = retained["eventId"]
    send("example", password, retained)
    result = run_worker(1, dlq="dev.infra.examples.missing")
    expect(result.returncode != 0, "worker committed or ignored a failed DLQ publish")
    result = run_worker(1, dlq=DLQ)
    expect(result.returncode == 0 and "dlq" in result.stdout, result.stderr or result.stdout)

    records = read_dlq()
    matching = [item for item in records if item.get("eventId") == retained["eventId"]]
    expect(matching, "original message was lost when DLQ was unavailable")
    expect(matching[-1]["sourceTopic"] == TOPIC, "DLQ record has no source topic")
    expect(matching[-1]["attempts"] >= 1, "DLQ record has no attempt count")
    exhausted = [item for item in records if item.get("attempts") == 3]
    expect(exhausted, "retry exhaustion did not reach the DLQ")
    print("kafka checks passed")

    errors: list[str] = []

    def denied_delivery(err, _message) -> None:
        if err is not None:
            errors.append(str(err))

    denied = producer("qa", os.environ["KAFKA_QA_PASSWORD"])
    denied.produce("task-tracker.events.v1", b"{}", key="denied", on_delivery=denied_delivery)
    denied.flush(10)
    expect(bool(errors), "qa principal wrote to the task tracker topic")
    print("kafka acl denial passed")


if __name__ == "__main__":
    main()
