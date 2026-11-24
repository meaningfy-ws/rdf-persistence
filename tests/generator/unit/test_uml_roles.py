"""PD-3: a role definition drawn as an Object, one table row for each case of the error matrix.

Each row builds a ``UmlModel`` with Objects typed by the drawn ``rp:RoleDefinition``, converts it and checks
the one problem it gives, naming the object, or the report line a valid entry gets. Entries are the
library's ``RoleDefinition`` records, sorted by role and level; the converted schemas do not change with them.
"""

import pytest
from linkml_runtime.dumpers import yaml_dumper

from rdf_persistence.access.domain.generated.rp_access import RoleDefinition
from rdf_persistence_generation.uml.context import Context
from rdf_persistence_generation.uml.roles import role_entries
from rdf_persistence_generation.uml.toolkit import load_toolkit
from tests.generator.uml_model import (
    BOOK,
    klass,
    model,
    object_,
    run,
    settings,
)

from .uml_role_rows import READER, ROLE_DEFINITION, ROLE_ROWS, RoleRow, _given, _uml


@pytest.mark.parametrize("row", [pytest.param(r, id=r.case) for r in ROLE_ROWS])
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
