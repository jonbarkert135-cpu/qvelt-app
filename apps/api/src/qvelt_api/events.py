"""Validate wire events using the generated, packaged shared JSON Schema."""
import json
from importlib.resources import files
from typing import Any, cast

from jsonschema import Draft7Validator

schema = json.loads(files("qvelt_api").joinpath("schemas/stream-event.schema.json").read_text())
Draft7Validator.check_schema(schema)
validator = Draft7Validator(schema)


def parse_event(data: str) -> dict[str, Any]:
    try:
        value = json.loads(data)
        # Python's JSON decoder accepts nonfinite constants/overflow; the wire does not.
        json.dumps(value, allow_nan=False)
        if validator.is_valid(value):
            return cast(dict[str, Any], value)
    except (ValueError, TypeError, RecursionError, OverflowError):
        pass
    raise ValueError("Invalid stream event")
