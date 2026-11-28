"""PD-3: a role definition drawn as an Object, one table row for each case of the error matrix.

Each row builds a ``UmlModel`` with Objects typed by the drawn ``rp:RoleDefinition``, converts it and checks
the one problem it gives, naming the object, or the report line a valid entry gets. Entries are the
library's ``RoleDefinition`` records, sorted by role and level; the converted schemas do not change with them.
"""

import pytest
from linkml_runtime.dumpers import yaml_dumper

from rdf_persistence.access.domain.generated.rp_access import RoleDefinition
from rdf_persistence_generation.generated.rp_generation import UmlObject, UmlPackage, UmlRule
from rdf_persistence_generation.uml.context import Context
from rdf_persistence_generation.uml.roles import role_entries
from rdf_persistence_generation.uml.toolkit import load_toolkit
from tests.generator.uml_model import (
    BOOK,
    EXTERNAL_PKG,
    klass,
    model,
    object_,
    run,
    settings,
)

from .uml_role_rows import (
    READER,
    ROLE_DEFINITION,
    ROLE_ROWS,
    Check,
    RoleRow,
    _given,
    _problem,
    _uml,
    _valid,
)


@pytest.mark.parametrize("row", [pytest.param(r, id=r.case) for r in ROLE_ROWS])
def test_a_role_object_row(row: RoleRow) -> None:
    row.check(run(_uml(*row.objects)))


OUTSIDE_ROLE_DEFINITION = 31  # the same drawn toolkit class, outside the subtree
_EXTERNAL = (UmlPackage(package_id=EXTERNAL_PKG, name="external"),)


def _realising(drawn: UmlObject, *targets: int) -> UmlObject:
    """The Object as the reader gives it when it has Realisation connectors to ``targets`` (PD-11)."""
    return drawn.model_copy(update={"realised_ids": list(targets)})


def _in_outside_model(*objects: UmlObject):
    return model(
        klass(BOOK, "lib:Book"),
        klass(ROLE_DEFINITION, "rp:RoleDefinition"),
        objects=objects,
        outside=(klass(OUTSIDE_ROLE_DEFINITION, "rp:RoleDefinition", EXTERNAL_PKG),),
        outside_packages=_EXTERNAL,
    )


def _named(name: str, *fragments: str) -> Check:
    return _problem(UmlRule.ROLE_DEFINITION, name, *fragments)


REALISATION_ROWS = [
    pytest.param(
        _uml(_realising(_given(*READER, name="reader at tenant"), ROLE_DEFINITION)),
        _valid,
        id="agreeing_with_the_classifier",
    ),
    pytest.param(
        _uml(
            _realising(_given(*READER, name="reader at tenant", classifier=None), ROLE_DEFINITION)
        ),
        _valid,
        id="no_classifier_takes_the_target",
    ),
    pytest.param(
        _in_outside_model(
            _realising(
                _given(*READER, name="reader at tenant", classifier=None), OUTSIDE_ROLE_DEFINITION
            )
        ),
        _valid,
        id="no_classifier_takes_a_target_outside_the_subtree",
    ),
    pytest.param(
        _uml(_realising(_given(*READER), BOOK)),
        _named("the reader", "realises Book", "classifier is RoleDefinition"),
        id="disagreeing_with_the_classifier",
    ),
    pytest.param(
        _uml(_realising(_given(*READER, classifier=None), ROLE_DEFINITION, BOOK)),
        _named("the reader", "Book", "RoleDefinition"),
        id="two_targets_and_no_classifier",
    ),
    pytest.param(
        _uml(_realising(_given(*READER), ROLE_DEFINITION, BOOK)),
        _named("the reader", "Book", "RoleDefinition"),
        id="two_targets_one_the_classifier",
    ),
    pytest.param(
        _uml(_realising(_given(*READER, classifier=BOOK), BOOK)),
        _problem(UmlRule.NO_RULE, "the reader", "Object of Book"),
        id="an_object_of_a_domain_class_is_still_refused",
    ),
    pytest.param(
        _uml(_realising(_given(*READER, classifier=None), BOOK)),
        _problem(UmlRule.NO_RULE, "the reader", "Object of Book"),
        id="a_target_that_is_a_domain_class_is_refused",
    ),
]


@pytest.mark.parametrize(("uml", "check"), REALISATION_ROWS)
def test_a_realisation_row(uml, check: Check) -> None:
    check(run(uml))


def test_an_agreeing_realisation_leaves_the_roles_file_unchanged() -> None:
    drawn = _given(*READER, name="reader at tenant")
    plain = run(_uml(drawn))
    realised = run(_uml(_realising(drawn, ROLE_DEFINITION)))
    assert realised.files == plain.files, (
        "the roles file is the one written without the Realisation"
    )


def test_a_role_object_changes_no_schema() -> None:
    plain = run(model(klass(BOOK, "lib:Book"), klass(ROLE_DEFINITION, "rp:RoleDefinition")))
    drawn = run(_uml(_given(*READER)))
    assert drawn.problems == [], drawn.problem_texts()
    assert {n: yaml_dumper.dumps(s) for n, s in drawn.schemas.items()} == {
        n: yaml_dumper.dumps(s) for n, s in plain.schemas.items()
    }, "the entries are not part of the schemas"


def test_the_entries_are_role_definitions_sorted_by_role_then_level() -> None:
    ctx = Context(settings(), load_toolkit(), {})
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
