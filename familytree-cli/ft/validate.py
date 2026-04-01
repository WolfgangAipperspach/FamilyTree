"""JSON Schema validation helpers."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
from jsonschema import Draft202012Validator

# Schemas live alongside the familytree-specs directory in the repo root
_SPECS_DIR = Path(__file__).parent.parent.parent / "familytree-specs"


def _load_schema(filename: str) -> dict:
    with (_SPECS_DIR / filename).open(encoding="utf-8") as fh:
        return json.load(fh)


def _validate(data: dict, schema: dict) -> list[str]:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    return [e.message for e in errors]


def validate_person(data: dict) -> list[str]:
    return _validate(data, _load_schema("person.schema.json"))


def validate_relation(data: dict) -> list[str]:
    return _validate(data, _load_schema("relation.schema.json"))


def validate_control(data: dict) -> list[str]:
    return _validate(data, _load_schema("familytree.schema.json"))
