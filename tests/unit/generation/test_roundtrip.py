"""An aggregate survives JSON, RDF and a frame unchanged (PD-27 item 4, PD-12)."""

import os
import subprocess
import sys
from functools import cache
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from linkml_runtime.linkml_model.meta import ClassDefinition
from rdflib import Graph

from rdf_persistence.testkit.conformance import Conformance
from rdf_persistence.testkit.roundtrip import round_trip
from rdf_persistence.testkit.strategies import IRI_BASE, aggregate

ROOT = Path(__file__).parents[3]
TOY_SCHEMA = ROOT / "tests" / "fixtures" / "library" / "library.yaml"
METAMODEL_SCHEMA = ROOT / "rdf_persistence" / "model" / "rp.yaml"
TOY_AGGREGATES = ["Book", "Scan", "Library", "LibraryAccess"]

# CI runs the same examples every time (checklist 8); locally Hypothesis explores.
settings.register_profile(
    "ci", derandomize=True, max_examples=20, deadline=None, suppress_health_check=list(HealthCheck)
)
settings.register_profile(
    "default", max_examples=40, deadline=None, suppress_health_check=list(HealthCheck)
)
settings.load_profile(
    os.environ.get("HYPOTHESIS_PROFILE", "ci" if os.environ.get("CI") else "default")
)


@cache
def opened(schema: Path) -> Conformance:
    """The schema and its generated artefacts, opened once; not a fixture, so that Hypothesis does not
    print them into a failure's repr. The freshness plugin has checked the files this session."""
    return Conformance.of(schema)


@pytest.mark.parametrize("class_name", TOY_AGGREGATES)
@given(data=st.data())
def test_a_toy_aggregate_survives_json_rdf_and_a_frame(
    class_name: str, data: st.DataObject
) -> None:
    toy = opened(TOY_SCHEMA)
    round_trip(toy, data.draw(aggregate(toy, class_name)), class_name)


@given(data=st.data())
def test_the_tenant_access_record_survives_json_rdf_and_a_frame(data: st.DataObject) -> None:
    """Its internal database name is drawn and kept on the object, but never crosses the context."""
    metamodel = opened(METAMODEL_SCHEMA)
    round_trip(metamodel, data.draw(aggregate(metamodel, "TenantAccess")), "TenantAccess")


def test_a_backslash_followed_by_r_in_text_is_not_read_as_a_carriage_return() -> None:
    toy = opened(TOY_SCHEMA)
    book = toy.models["Book"].model_validate(
        {"id": f"{IRI_BASE}1", "label": "Dune", "description": "\\r"}
    )
    round_trip(toy, book, "Book")


def test_a_round_trip_that_loses_a_value_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    toy = opened(TOY_SCHEMA)
    book = toy.models["Book"].model_validate(
        {"id": f"{IRI_BASE}1", "label": "Dune", "description": "A planet.", "isbn": "9780441172719"}
    )
    real = toy.documents.frame

    def lossy(graph: Graph, cls: ClassDefinition) -> dict:
        return {k: v for k, v in real(graph, cls).items() if k != "isbn"}

    monkeypatch.setattr(toy.documents, "frame", lossy)
    with pytest.raises(AssertionError, match="objects differ"):
        round_trip(toy, book, "Book")


def test_the_strategies_name_hypothesis_when_it_is_missing() -> None:
    code = "import sys; sys.modules['hypothesis'] = None\nimport rdf_persistence.testkit.strategies"
    run = subprocess.run(
        [sys.executable, "-I", "-c", code], capture_output=True, text=True, check=False
    )
    assert "needs hypothesis" in run.stderr, f"the error does not name the dependency: {run.stderr}"


def test_the_testkit_and_the_round_trip_do_not_import_hypothesis() -> None:
    code = (
        "import sys, rdf_persistence.testkit, rdf_persistence.testkit.roundtrip\n"
        "sys.exit('hypothesis' in sys.modules)"
    )
    assert subprocess.run([sys.executable, "-I", "-c", code], check=False).returncode == 0
