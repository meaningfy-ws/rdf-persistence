"""PD-3: a role definition drawn as an Object, one table row for each case of the error matrix.

Each row builds a ``UmlModel`` with Objects typed by the drawn ``rp:RoleDefinition``, converts it and checks
the one problem it gives, naming the object, or the report line a valid entry gets. Entries are the
library's ``RoleDefinition`` records, sorted by role and level; the converted schemas do not change with them.
"""

from collections.abc import Callable
from dataclasses import dataclass

import pytest
from linkml_runtime.dumpers import yaml_dumper

from rdf_persistence.access.domain.generated.rp_access import RoleDefinition
from rdf_persistence_generation.generated.rp_generation import UmlRule
from rdf_persistence_generation.uml.context import Context
from rdf_persistence_generation.uml.roles import role_entries
from tests.generator.uml_model import (
    BOOK,
    METAMODEL_PREFIXES,
    Converted,
    klass,
    model,
    object_,
    run,
    settings,
)

ROLE_DEFINITION = 30  # the drawn toolkit class rp:RoleDefinition
CLASSIFIED = {"classifier": ROLE_DEFINITION}
READER = ("role", "reader"), ("level", "tenant"), ("actions", "read,annotate")
Check = Callable[[Converted], None]


@dataclass(frozen=True)
class RoleRow:
    """One case of the Object rows of the error matrix: the objects drawn and what must hold."""

    case: str
    rule: UmlRule
    objects: tuple
    check: Check


def _uml(*objects):
    return model(
        klass(BOOK, "lib:Book"), klass(ROLE_DEFINITION, "rp:RoleDefinition"), objects=objects
    )


def _problem(rule: UmlRule, *fragments: str) -> Check:
    """The run fails with exactly one problem, of this rule, whose text holds every fragment."""

    def check(out: Converted) -> None:
        assert [p.rule for p in out.problems] == [rule.value], out.problem_texts()
        for fragment in fragments:
            assert fragment in out.problem_texts()[0], (
                f"the problem must say {fragment!r}: {out.problem_texts()}"
            )

    return check


def _valid(out: Converted) -> None:
    assert out.problems == [], out.problem_texts()
    assert out.report_lines("role") == ["reader at tenant: reader at tenant: read, annotate"], (
        out.report
    )


def _given(*values, name="the reader", classifier=ROLE_DEFINITION, rest=None):
    return object_(40, name, classifier, *values, rest=rest)


def _without(variable: str):
    return tuple(each for each in READER if each[0] != variable)


def _replacing(variable: str, value: str):
    return tuple((v, value if v == variable else x) for v, x in READER)


ROWS = [
    RoleRow(
        "a valid entry is a role line and no problem",
        UmlRule.ROLE_RUN_STATE,
        (_given(*READER, name="reader at tenant"),),
        _valid,
    ),
    RoleRow(
        "a domain class as classifier is no rule",
        UmlRule.NO_RULE,
        (_given(*READER, classifier=BOOK),),
        _problem(UmlRule.NO_RULE, "the reader", "Object of Book"),
    ),
    RoleRow(
        "no classifier is no rule",
        UmlRule.NO_RULE,
        (_given(*READER, classifier=None),),
        _problem(UmlRule.NO_RULE, "the reader", "Object without a classifier"),
    ),
    RoleRow(
        "a level outside RoleLevel",
        UmlRule.ROLE_DEFINITION,
        (_given(*_replacing("level", "planet")),),
        _problem(UmlRule.ROLE_DEFINITION, "the reader", "level", "planet"),
    ),
    RoleRow(
        "an action outside Action",
        UmlRule.ROLE_DEFINITION,
        (_given(*_replacing("actions", "read, fly")),),
        _problem(UmlRule.ROLE_DEFINITION, "the reader", "actions", "fly"),
    ),
    RoleRow(
        "no action left after splitting",
        UmlRule.ROLE_DEFINITION,
        (_given(*_replacing("actions", " , ")),),
        _problem(UmlRule.ROLE_DEFINITION, "the reader", "actions"),
    ),
    RoleRow(
        "a repeated action",
        UmlRule.ROLE_DEFINITION,
        (_given(*_replacing("actions", "read,annotate, read")),),
        _problem(UmlRule.ROLE_DEFINITION, "the reader", "actions", "read"),
    ),
    RoleRow(
        "an unknown variable",
        UmlRule.ROLE_RUN_STATE,
        (_given(*READER, ("colour", "red")),),
        _problem(UmlRule.ROLE_RUN_STATE, "the reader", "colour"),
    ),
    RoleRow(
        "a variable given twice",
        UmlRule.ROLE_RUN_STATE,
        (_given(*READER, ("level", "system")),),
        _problem(UmlRule.ROLE_RUN_STATE, "the reader", "level"),
    ),
    RoleRow(
        "a missing role",
        UmlRule.ROLE_RUN_STATE,
        (_given(*_without("role")),),
        _problem(UmlRule.ROLE_RUN_STATE, "the reader", "role"),
    ),
    RoleRow(
        "a missing level",
        UmlRule.ROLE_RUN_STATE,
        (_given(*_without("level")),),
        _problem(UmlRule.ROLE_RUN_STATE, "the reader", "level"),
    ),
    RoleRow(
        "a missing actions",
        UmlRule.ROLE_RUN_STATE,
        (_given(*_without("actions")),),
        _problem(UmlRule.ROLE_RUN_STATE, "the reader", "actions"),
    ),
    RoleRow(
        "an operator other than =",
        UmlRule.ROLE_RUN_STATE,
        (_given(*READER[:2], ("actions", "read", "<")),),
        _problem(UmlRule.ROLE_RUN_STATE, "the reader", "actions", "Op", "<"),
    ),
    RoleRow(
        "a block with no value",
        UmlRule.ROLE_RUN_STATE,
        (_given(*READER[:2], ("actions", None)),),
        _problem(UmlRule.ROLE_RUN_STATE, "the reader", "actions", "Value"),
    ),
    RoleRow(
        "text outside the blocks (D-4)",
        UmlRule.ROLE_RUN_STATE,
        (_given(*READER, rest="remember to review"),),
        _problem(UmlRule.ROLE_RUN_STATE, "the reader", "remember to review"),
    ),
    RoleRow(
        "two objects with one level and role",
        UmlRule.ROLE_DUPLICATE,
        (
            object_(41, "first reader", ROLE_DEFINITION, *READER),
            object_(42, "second reader", ROLE_DEFINITION, *_replacing("actions", "read")),
        ),
        _problem(UmlRule.ROLE_DUPLICATE, "first reader", "second reader", "reader", "tenant"),
    ),
]
ROLE_ROWS = ROWS


@pytest.mark.parametrize("row", [pytest.param(r, id=r.case) for r in ROWS])
def test_a_role_object_row(row: RoleRow) -> None:
    row.check(run(_uml(*row.objects)))


def test_a_role_object_changes_no_schema() -> None:
    plain = run(model(klass(BOOK, "lib:Book"), klass(ROLE_DEFINITION, "rp:RoleDefinition")))
    drawn = run(_uml(_given(*READER)))
    assert drawn.problems == [], drawn.problem_texts()
    assert {n: yaml_dumper.dumps(s) for n, s in drawn.schemas.items()} == {
        n: yaml_dumper.dumps(s) for n, s in plain.schemas.items()
    }, "the entries are not part of the schemas"


def test_the_entries_are_role_definitions_sorted_by_role_then_level() -> None:
    ctx = Context(settings(), METAMODEL_PREFIXES, {})
    ctx.drawn_toolkit[ROLE_DEFINITION] = "RoleDefinition"
    uml = _uml(
        object_(
            1, "c", ROLE_DEFINITION, ("role", "writer"), ("level", "system"), ("actions", "modify")
        ),
        object_(
            2, "b", ROLE_DEFINITION, ("role", "reader"), ("level", "tenant"), ("actions", "read")
        ),
        object_(
            3, "a", ROLE_DEFINITION, ("role", "reader"), ("level", "aggregate"), ("actions", "read")
        ),
    )
    entries = role_entries(ctx, uml)
    assert ctx.findings.problems() == []
    assert all(isinstance(entry, RoleDefinition) for entry in entries)
    assert [(e.role, e.level) for e in entries] == [
        ("reader", "aggregate"),
        ("reader", "tenant"),
        ("writer", "system"),
    ], "sorted by role, then level, not by drawing order"
