"""Validate against the owner's OpenAPI, without maintaining a second schema."""
import os
from functools import lru_cache
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker, ValidationError
from adapters import Rejected


@lru_cache
def tracker_validator(name):
    configured = os.getenv("REPORTS_TRACKER_CONTRACT")
    if configured:
        path = Path(configured)
    else:
        parents = Path(__file__).resolve().parents
        if len(parents) < 3:
            raise Rejected("TRACKER_CONTRACT_PATH_REQUIRED")
        path = parents[2] / "task-tracker/docs/block-g-api-and-events/openapi.yaml"
    document = yaml.safe_load(path.read_text())
    schema = {"$ref": "#/components/schemas/" + name, "components": document["components"]}
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validate_tracker(name, item):
    try:
        tracker_validator(name).validate(item)
    except ValidationError:
        raise Rejected("TRACKER_CONTRACT_VIOLATION") from None
