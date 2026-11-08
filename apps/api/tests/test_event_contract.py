import json
from importlib.resources import files
from pathlib import Path

import pytest

from qvelt_api.events import parse_event, schema

package = Path(__file__).parents[3] / "packages/events"
fixtures = json.loads((package / "fixtures/stream-events.json").read_text())


@pytest.mark.parametrize("case", fixtures["valid"], ids=lambda case: case["name"])
def test_shared_valid_events(case):
    assert parse_event(json.dumps(case["event"])) == case["event"]


@pytest.mark.parametrize("case", fixtures["invalid"], ids=lambda case: case["name"])
def test_shared_invalid_events(case):
    with pytest.raises(ValueError, match="^Invalid stream event$"):
        parse_event(case["json"])


def test_packaged_schema_matches_shared_export():
    shared = (package / "schema/stream-event.schema.json").read_bytes()
    packaged = files("qvelt_api").joinpath("schemas/stream-event.schema.json").read_bytes()
    assert shared == packaged
    assert len(schema["anyOf"]) == 9
