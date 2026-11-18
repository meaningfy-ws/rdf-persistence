"""The toy service's ``/openapi.json`` is byte-identical to its golden file, whichever targets are served (TC-07, PD-10).

The golden was written before the technical schemas were split into themes; a merged document that
differs after a split is a failure to fix in the schemas, never a new golden. ``make refresh-served-golden``
rewrites it (``RP_REFRESH_GOLDEN``), for a deliberate change of the toy's API only.
"""

import json
import os
from pathlib import Path

import pytest

from tests.generator.unit.golden import REFRESH_VARIABLE
from tests.toy_service import ToyService

GOLDEN = Path(__file__).parents[2] / "fixtures" / "library" / "golden" / "openapi" / "openapi.json"


@pytest.fixture(scope="module")
def served_text() -> str:
    return json.dumps(ToyService().app.openapi(), indent=2, ensure_ascii=False) + "\n"


def test_the_document_equals_the_golden_file(served_text: str) -> None:  # TC-07
    if os.environ.get(REFRESH_VARIABLE):
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(served_text, encoding="utf-8")
    assert served_text == GOLDEN.read_text(encoding="utf-8"), (
        "/openapi.json differs from the golden file: fix the schemas, not the golden"
    )
