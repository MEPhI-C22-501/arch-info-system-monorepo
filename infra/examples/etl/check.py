#!/usr/bin/env python3
"""Эталон ETL: extract из S3, transform, load в свою SQLite, checkpoint после commit."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid

import boto3
from botocore.client import Config

ENDPOINT = os.environ.get("S3_ENDPOINT", "http://minio:9000")
BUCKET = "arch-dev-examples"
DB = os.environ.get("ETL_DB", "/tmp/etl.sqlite")


def s3():
    return boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        aws_access_key_id="example-writer",
        aws_secret_access_key=os.environ["S3_EXAMPLE_WRITER_SECRET"],
        region_name="us-east-1",
        config=Config(s3={"addressing_style": "path"}),
    )


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB)
    connection.execute("CREATE TABLE IF NOT EXISTS fact (batch_id TEXT, row_id TEXT, hours REAL, PRIMARY KEY (batch_id, row_id))")
    connection.execute("CREATE TABLE IF NOT EXISTS checkpoint (batch_id TEXT PRIMARY KEY, loaded INTEGER NOT NULL)")
    return connection


def publish_batch(client, batch_id: str, rows: list[dict]) -> None:
    body = json.dumps(rows).encode()
    client.put_object(Bucket=BUCKET, Key=f"etl/{batch_id}.json", Body=body)
    manifest = {"batchId": batch_id, "count": len(rows), "sha256": hashlib.sha256(body).hexdigest()}
    client.put_object(Bucket=BUCKET, Key=f"etl/{batch_id}.manifest.json", Body=json.dumps(manifest).encode())


def load_batch(client, batch_id: str, fail_after: int | None) -> dict:
    manifest = json.loads(client.get_object(Bucket=BUCKET, Key=f"etl/{batch_id}.manifest.json")["Body"].read())
    raw = client.get_object(Bucket=BUCKET, Key=f"etl/{batch_id}.json")["Body"].read()
    if hashlib.sha256(raw).hexdigest() != manifest["sha256"]:
        raise RuntimeError("checksum")
    rows = json.loads(raw)
    connection = connect()
    done = connection.execute("SELECT loaded FROM checkpoint WHERE batch_id = ?", (batch_id,)).fetchone()
    start = done[0] if done else 0
    loaded = start
    rejected = 0
    for index, row in enumerate(rows):
        if index < start:
            continue
        if fail_after is not None and loaded - start >= fail_after:
            raise RuntimeError("injected failure")
        if not isinstance(row.get("hours"), (int, float)) or row["hours"] < 0:
            rejected += 1
            loaded = index + 1
            connection.execute(
                "INSERT INTO checkpoint (batch_id, loaded) VALUES (?, ?) ON CONFLICT(batch_id) DO UPDATE SET loaded = excluded.loaded",
                (batch_id, loaded),
            )
            connection.commit()
            continue
        connection.execute(
            "INSERT INTO fact (batch_id, row_id, hours) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
            (batch_id, row["rowId"], row["hours"]),
        )
        loaded = index + 1
        connection.execute(
            "INSERT INTO checkpoint (batch_id, loaded) VALUES (?, ?) ON CONFLICT(batch_id) DO UPDATE SET loaded = excluded.loaded",
            (batch_id, loaded),
        )
        connection.commit()
    count = connection.execute("SELECT COUNT(*), COALESCE(SUM(hours), 0) FROM fact WHERE batch_id = ?", (batch_id,)).fetchone()
    return {"rows": count[0], "hours": count[1], "rejected": rejected, "expected": manifest["count"]}


def main() -> None:
    if os.path.exists(DB):
        os.remove(DB)
    client = s3()
    batch_id = str(uuid.uuid4())
    rows = [
        {"rowId": "a", "hours": 1.5},
        {"rowId": "b", "hours": 2},
        {"rowId": "bad", "hours": -1},
        {"rowId": "c", "hours": 3},
    ]
    publish_batch(client, batch_id, rows)
    try:
        load_batch(client, batch_id, fail_after=1)
    except RuntimeError as error:
        if "injected" not in str(error):
            raise
    else:
        raise SystemExit("mid-batch failure was not injected")
    first = load_batch(client, batch_id, fail_after=None)
    second = load_batch(client, batch_id, fail_after=None)
    if first["rows"] != 3 or second["rows"] != 3:
        raise SystemExit(f"rows were duplicated or lost: {first} {second}")
    if first["hours"] != 6.5 or first["rejected"] < 1:
        raise SystemExit(f"transform or reject failed: {first} {second}")
    if second["hours"] != first["hours"]:
        raise SystemExit(f"replay changed loaded hours: {first} {second}")
    if first["rows"] + 1 != first["expected"]:
        raise SystemExit("completeness check failed")
    print("etl checks passed")


if __name__ == "__main__":
    main()
