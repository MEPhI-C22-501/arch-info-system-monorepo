"""Publish the module-owned OpenAPI files in the shared API catalog."""

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "api" / "openapi"
SOURCES = {
    "planning-system/v1/openapi.json": "planning-system/docs/contracts/openapi.json",
    "planning-system/runtime/v1/openapi.json": "planning-system/docs/contracts/runtime.openapi.json",
    "qa/v1/openapi.yaml": "qa/api/openapi/v1/openapi.yaml",
    "reports/v1/openapi.yaml": "reports/api/openapi/v1/openapi.yaml",
    "task-tracker/v1/openapi.yaml": "task-tracker/docs/block-g-api-and-events/openapi.yaml",
}
RM_SOURCE = "reference-manager/backend/api/openapi/v1"
for resource in (
    "absence",
    "assignment",
    "country",
    "currency",
    "employee",
    "grade",
    "health",
    "org_unit",
    "position",
    "project_role",
    "salary",
):
    spec = "currency/v1" if resource == "currency" else resource
    SOURCES[f"reference-manager/{spec}/openapi.yaml"] = f"{RM_SOURCE}/{resource}/openapi.yaml"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Report stale copies without writing")
    args = parser.parse_args()

    stale = []
    for name, source in sorted(SOURCES.items()):
        destination = CATALOG / name
        expected = (ROOT / source).read_bytes()
        if destination.is_file() and destination.read_bytes() == expected:
            continue
        if args.check:
            stale.append(f"{destination.relative_to(ROOT)} (source: {source})")
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(expected)
            print(f"Updated {destination.relative_to(ROOT)}")

    if stale:
        print("Run python3 api/sync-specs.py to update:")
        print("\n".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
