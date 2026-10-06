#!/usr/bin/env python3
"""Эталон S3: объект, manifest, повтор, повреждённый набор и запрет чужого бакета."""

from __future__ import annotations

import hashlib
import json
import os
import uuid

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

ENDPOINT = os.environ.get("S3_ENDPOINT", "http://minio:9000")
BUCKET = "arch-dev-examples"


def client(access: str, secret: str):
    return boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        aws_access_key_id=access,
        aws_secret_access_key=secret,
        region_name="us-east-1",
        config=Config(s3={"addressing_style": "path"}),
    )


def put_set(writer, key: str, body: bytes) -> dict:
    digest = hashlib.sha256(body).hexdigest()
    writer.put_object(Bucket=BUCKET, Key=key, Body=body)
    manifest = {"key": key, "sha256": digest, "operationId": str(uuid.uuid4())}
    writer.put_object(Bucket=BUCKET, Key=key + ".manifest.json", Body=json.dumps(manifest).encode())
    return manifest


def import_manifest(reader, manifest_key: str, ledger: dict) -> str:
    manifest = json.loads(reader.get_object(Bucket=BUCKET, Key=manifest_key)["Body"].read())
    operation = manifest["operationId"]
    if operation in ledger:
        return "replay"
    try:
        body = reader.get_object(Bucket=BUCKET, Key=manifest["key"])["Body"].read()
    except ClientError as error:
        raise RuntimeError("incomplete set") from error
    digest = hashlib.sha256(body).hexdigest()
    if digest != manifest["sha256"]:
        raise RuntimeError("checksum mismatch")
    ledger[operation] = manifest["key"]
    return "imported"


def main() -> None:
    writer = client("example-writer", os.environ["S3_EXAMPLE_WRITER_SECRET"])
    reader = client("example-reader", os.environ["S3_EXAMPLE_READER_SECRET"])
    stranger = client("example-stranger", os.environ["S3_EXAMPLE_STRANGER_SECRET"])
    key = f"exchange/{uuid.uuid4()}"
    manifest = put_set(writer, key, b"demo-object")
    ledger: dict[str, str] = {}
    manifest_key = key + ".manifest.json"
    if import_manifest(reader, manifest_key, ledger) != "imported":
        raise SystemExit("first import failed")
    if import_manifest(reader, manifest_key, ledger) != "replay":
        raise SystemExit("replay imported twice")

    broken = f"exchange/{uuid.uuid4()}"
    writer.put_object(
        Bucket=BUCKET,
        Key=broken + ".manifest.json",
        Body=json.dumps({"key": broken, "sha256": "abc", "operationId": str(uuid.uuid4())}).encode(),
    )
    try:
        import_manifest(reader, broken + ".manifest.json", {})
    except RuntimeError as error:
        if "incomplete" not in str(error):
            raise
    else:
        raise SystemExit("incomplete set was accepted")

    corrupt_key = f"exchange/{uuid.uuid4()}"
    writer.put_object(Bucket=BUCKET, Key=corrupt_key, Body=b"data")
    writer.put_object(
        Bucket=BUCKET,
        Key=corrupt_key + ".manifest.json",
        Body=json.dumps({"key": corrupt_key, "sha256": "0" * 64, "operationId": str(uuid.uuid4())}).encode(),
    )
    try:
        import_manifest(reader, corrupt_key + ".manifest.json", {})
    except RuntimeError as error:
        if "checksum" not in str(error):
            raise
    else:
        raise SystemExit("corrupt object was accepted")

    try:
        stranger.put_object(Bucket=BUCKET, Key="forbidden", Body=b"no")
    except ClientError:
        pass
    else:
        raise SystemExit("stranger wrote the examples bucket")
    print("s3 checks passed")
    print(manifest["sha256"])


if __name__ == "__main__":
    main()
