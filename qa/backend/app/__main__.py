"""Точки входа образа qa-system (ADR-002): `python -m app api | migrate`.

Точка входа `worker` появится вместе с исполнителем.
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def api() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, proxy_headers=True)


def migrate() -> None:
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(BACKEND_DIR / "alembic.ini")), "head")


def seed() -> None:
    from app.seed import main as load_demo_data

    load_demo_data()


COMMANDS = {"api": api, "migrate": migrate, "seed": seed}


def main(argv: list[str]) -> int:
    name = argv[1] if len(argv) > 1 else "api"
    if name not in COMMANDS:
        print(f"Использование: python -m app [{' | '.join(COMMANDS)}]", file=sys.stderr)
        return 2
    COMMANDS[name]()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
