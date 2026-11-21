"""The role-definition rows of the UML error matrix, shared by ``test_uml_roles`` and ``test_uml_rules``."""

from collections.abc import Callable
from dataclasses import dataclass

from rdf_persistence_generation.generated.rp_generation import UmlRule
from tests.generator.uml_model import BOOK, Converted, klass, model, object_

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


ROLE_ROWS = [
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
