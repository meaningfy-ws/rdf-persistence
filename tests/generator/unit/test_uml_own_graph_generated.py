"""A generated «own graph» part converts to a dependent root (dependent-aggregates PD-13, DEC-1).

``Audit`` composes ``AuditResult`` «own graph»; the association's role on ``Audit``'s end is the pointer
the result holds. Each row is one drawing, with the converter's answer: the root with ``rp_dependent_on``
and its required single slot, or a problem naming the association. The last test writes the output and
gives it to the lint rules and the boundary check of ``rp-generate``, the dependence check among them.
"""

from collections.abc import Callable
from pathlib import Path

import pytest

from rdf_persistence_generation.generated.rp_generation import UmlLink, UmlModel
from tests.generator.uml_accept import generator_problems
from tests.generator.uml_model import Converted, composition, klass, link, model, run

AUDIT, RESULT = 20, 21
MODULE = "app_library"
POINTER = "of_audit"
LISTING = "results"
PAIR = "Audit -> AuditResult"
PART_END_LINE = "Audit.results: a role on the part's end is not converted"


def pointer(card: str | None = "1") -> UmlLink:
    """The association whose role on ``Audit``'s end is the slot ``AuditResult`` holds over ``Audit``."""
    return link(1, RESULT, AUDIT, target_role="lib:ofAudit", target_card=card)


def listing() -> UmlLink:
    """The association whose role on ``AuditResult``'s end would be a slot of ``Audit``."""
    return link(2, AUDIT, RESULT, target_role="lib:results", target_card="0..*")


def drawn(*links: UmlLink, own_graph: bool = True) -> UmlModel:
    return model(
        klass(AUDIT, "lib:Audit"),
        klass(RESULT, "lib:AuditResult"),
        links=links,
        compositions=(
            composition(
                3,
                AUDIT,
                RESULT,
                own_graph=own_graph,
                stereotype="own graph" if own_graph else None,
            ),
        ),
    )


def _converts(out: Converted) -> None:
    assert out.problems == [], out.problem_texts()
    part = out.klass(MODULE, "AuditResult")
    assert part.mixins == ["AggregateRoot"], "the part is a root, not a part of the whole"
    assert part.annotations["rp_dependent_on"].value == POINTER, "it depends through the pointer"
    assert part.annotations["rp_path"].value == "audit-results", "a root has its path"
    slot = out.slot(MODULE, POINTER)
    assert (slot.required, slot.multivalued, slot.range) == (True, None, "Audit"), (
        "the pointer is required, single-valued and ranges over the whole"
    )
    assert "rp_dependent_on" not in out.klass(MODULE, "Audit").annotations, "the whole is free"
    assert LISTING not in out.schemas[MODULE].slots, "the whole lists no parts"
    assert "AuditResult" in out.schemas[MODULE].classes, "the part is generated"


def _part_end_reported(out: Converted) -> None:
    _converts(out)
    assert out.report_lines("composition_named") == [
        f"{PART_END_LINE}: the whole lists no parts of its own graph"
    ], "a role on the part's end gets one report line"


def _refused(*fragments: str) -> Callable[[Converted], None]:
    def check(out: Converted) -> None:
        texts = out.problem_texts()
        assert len(texts) == 1, f"one problem expected, got {texts}"
        assert all(each in texts[0] for each in fragments), f"{fragments} are not all in {texts}"
        assert out.schemas == {}, "a refused model writes nothing"

    return check


ROWS = [
    pytest.param(drawn(pointer()), _converts, id="a role on the whole's end, exactly one"),
    pytest.param(drawn(pointer("1..1")), _converts, id="a role on the whole's end, 1..1"),
    pytest.param(
        drawn(pointer(), listing()), _part_end_reported, id="a role on the part's end as well"
    ),
    pytest.param(
        drawn(), _refused(PAIR, "role", "whole"), id="failure: no association, so no whole-end role"
    ),
    pytest.param(
        drawn(listing()),
        _refused(PAIR, "role", "whole"),
        id="failure: a role on the part's end only",
    ),
    pytest.param(
        drawn(pointer("0..1")),
        _refused(f"AuditResult.{POINTER}", "1", "0..1"),
        id="failure: the pointer is optional",
    ),
    pytest.param(
        drawn(pointer("*")),
        _refused(f"AuditResult.{POINTER}", "1", "*"),
        id="failure: the pointer is many",
    ),
    pytest.param(
        drawn(pointer("1..*")),
        _refused(f"AuditResult.{POINTER}", "1", "1..*"),
        id="failure: the pointer is one or many",
    ),
]


@pytest.mark.parametrize(("uml", "check"), ROWS)
def test_a_generated_own_graph_part(uml: UmlModel, check: Callable[[Converted], None]) -> None:
    check(run(uml))


def test_rp_generate_accepts_the_converted_schema(tmp_path: Path) -> None:
    """The lint, the boundary check and the dependence check of ``rp-generate`` find nothing to refuse."""
    found = generator_problems(run(drawn(pointer(), listing())), tmp_path)

    assert found == [], "rp-generate accepts the converted schema"
