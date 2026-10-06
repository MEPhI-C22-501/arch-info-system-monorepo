#!/usr/bin/env python3
"""Проверяет, что манифест выпуска не использует latest и называет образы."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    releases = list((ROOT / "infra/releases").glob("*.yaml"))
    if not releases:
        raise SystemExit("нет манифеста выпуска")
    for path in releases:
        if path.name == "README.md":
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if data.get("status") not in {"local-only", "deployed"}:
            raise SystemExit(f"{path.name}: непонятный status")
        for image in data.get("images", []):
            ref = image.get("reference", "")
            if ref.endswith(":latest") or not str(image.get("digest", "")).startswith("sha256:"):
                raise SystemExit(f"{path.name}: образ без digest {ref}")
        for build in data.get("local_builds", []):
            if data.get("status") == "deployed" and not str(build.get("digest", "")).startswith("sha256:"):
                raise SystemExit(f"{path.name}: локальная сборка без digest в deployed")
        if not data.get("config_commit"):
            raise SystemExit(f"{path.name}: нет config_commit")
    print("release manifest ok")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # noqa: BLE001
        print(error, file=sys.stderr)
        sys.exit(1)
