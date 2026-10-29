"""Реализация не расходится с qa/api/openapi/v1/openapi.yaml (130, раздел 1; NFR-13).

Спецификация описывает и ещё не реализованные операции, поэтому проверяется вложение:
каждая операция приложения есть в спецификации, а у общих схем совпадает набор полей.
"""

import itertools
import re
from pathlib import Path

import pytest
import yaml

from app.main import API_PREFIX, create_app

SPEC_PATH = Path(__file__).resolve().parents[2] / "api" / "openapi" / "v1" / "openapi.yaml"
METHODS = {"get", "post", "put", "patch", "delete"}

# Схемы, которые реализованы целиком; имена — как в спецификации.
SCHEMAS = [
    "TestCase",
    "TestCaseInput",
    "TestCaseVersionInfo",
    "LastResult",
    "Step",
    "TemplateInput",
    "Template",
    "TemplateBody",
    "SuiteInput",
    "Suite",
    "CaseFilter",
    "ClassifierInput",
    "ClassifierUpdate",
    "Classifier",
    "EnvironmentInput",
    "EnvironmentUpdate",
    "Environment",
]


@pytest.fixture(scope="module")
def spec() -> dict:
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def generated() -> dict:
    return create_app().openapi()


def spec_operations(spec: dict) -> set[tuple[str, str]]:
    """Пути вида /runs/{id}/{action} с enum раскрываются в конкретные пути."""
    operations = set()
    for path, item in spec["paths"].items():
        enums = {
            p["name"]: p["schema"]["enum"]
            for p in item.get("parameters", [])
            if p.get("in") == "path" and "enum" in p.get("schema", {})
        }
        names = list(enums)
        for values in itertools.product(*enums.values()):
            concrete = path
            for name, value in zip(names, values):
                concrete = concrete.replace("{" + name + "}", value)
            operations |= {(method, concrete) for method in item if method in METHODS}
    return operations


def test_version_matches(spec, generated):
    assert generated["info"]["version"] == spec["info"]["version"]


def test_every_operation_is_specified(spec, generated):
    implemented = {
        (method, path.removeprefix(API_PREFIX))
        for path, item in generated["paths"].items()
        for method in item
    }

    assert implemented - spec_operations(spec) == set()


@pytest.mark.parametrize("name", SCHEMAS)
def test_schema_fields_match(spec, generated, name):
    assert _properties(generated, _generated_name(generated, name)) == _properties(spec, name)


def _generated_name(document: dict, name: str) -> str:
    # FastAPI делит схему на -Input и -Output, если они различаются.
    schemas = document["components"]["schemas"]
    for candidate in (name, f"{name}-Output", f"{name}-Input"):
        if candidate in schemas:
            return candidate
    raise AssertionError(f"Схемы {name} нет в приложении")


def _properties(document: dict, name: str) -> set[str]:
    schema = document["components"]["schemas"][name]
    properties = set(schema.get("properties", {}))
    for part in schema.get("allOf", []):
        if "$ref" in part:
            properties |= _properties(document, re.sub(r".*/", "", part["$ref"]))
        properties |= set(part.get("properties", {}))
    return properties
