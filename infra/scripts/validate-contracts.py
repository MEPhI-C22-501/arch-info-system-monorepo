#!/usr/bin/env python3
"""Проверяет, что файлы каталога существуют, а примеры схем валидны или намеренно невалидны."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    catalog = yaml.safe_load((ROOT / "infra/contracts/catalog.yaml").read_text(encoding="utf-8"))
    missing = []
    for item in catalog["apis"]:
        path = ROOT / item["path"]
        if item["implementation"] == "file-missing":
            if path.exists():
                raise SystemExit(f"ожидалось отсутствие {path}")
            continue
        if not path.exists():
            missing.append(str(path))
    if missing:
        raise SystemExit("нет файлов:\n" + "\n".join(missing))

    envelope = json.loads((ROOT / "infra/contracts/schemas/envelope.schema.json").read_text(encoding="utf-8"))
    dlq = json.loads((ROOT / "infra/contracts/schemas/dlq.schema.json").read_text(encoding="utf-8"))
    examples = ROOT / "infra/contracts/schemas/examples"
    jsonschema.validate(json.loads((examples / "envelope.valid.json").read_text()), envelope)
    jsonschema.validate(json.loads((examples / "dlq.valid.json").read_text()), dlq)
    for name, schema in (("envelope.invalid.json", envelope), ("dlq.invalid.json", dlq)):
        try:
            jsonschema.validate(json.loads((examples / name).read_text()), schema)
        except jsonschema.ValidationError:
            continue
        raise SystemExit(f"{name} неожиданно прошёл схему")
    print("contracts ok")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # noqa: BLE001
        print(error, file=sys.stderr)
        sys.exit(1)
