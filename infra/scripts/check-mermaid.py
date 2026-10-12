#!/usr/bin/env python3
"""Проверяет, что блоки Mermaid имеют известный тип и закрытые subgraph."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TYPES = ("flowchart", "sequenceDiagram", "graph")


def main() -> None:
    errors = []
    for path in list((ROOT / "infra").rglob("*.md")) + [ROOT / "README.md", ROOT / "core" / "README.md", ROOT / "keycloak" / "README.md"]:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"```mermaid\n(.*?)```", text, re.S):
            body = match.group(1).strip()
            kind = body.splitlines()[0].split()[0]
            if kind not in TYPES and not any(body.startswith(item) for item in TYPES):
                errors.append(f"{path}: неизвестный тип диаграммы")
            if body.startswith("flowchart") or body.startswith("graph"):
                subgraphs = len(re.findall(r"(?m)^\s*subgraph\b", body))
                ends = len(re.findall(r"(?m)^\s*end\s*$", body))
                if subgraphs != ends:
                    errors.append(f"{path}: subgraph не закрыт")
    if errors:
        raise SystemExit("\n".join(errors))
    print("mermaid ok")


if __name__ == "__main__":
    main()
