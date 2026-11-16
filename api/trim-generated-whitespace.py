"""Remove trailing whitespace emitted by OpenAPI Generator."""

import sys
from pathlib import Path


def trim(file: Path):
    original = file.read_text(encoding="utf-8")
    normalized = "\n".join(line.rstrip(" \t") for line in original.splitlines()).rstrip("\n") + "\n"
    if normalized != original:
        file.write_text(normalized, encoding="utf-8")


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        path = Path(arg)
        for file in path.rglob("*") if path.is_dir() else [path]:
            if file.is_file() and file.suffix in {".java", ".py", ".ts"}:
                trim(file)
