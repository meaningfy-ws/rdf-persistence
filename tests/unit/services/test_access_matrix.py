"""PD-9's matrix of the toy library, every cell: who may do what, answered allow, 403 or 404."""

from itertools import product
from pathlib import Path

import pytest

from rdf_persistence import Action, Grant, Prohibition, TenantState, VerifiedCaller
from rdf_persistence.domain.exceptions import Forbidden, NotFound
from rdf_persistence.domain.generated.service.rp_service import CallerAccess
from rdf_persistence.services.access import AccessRules, load_role_definitions
from tests.toy import ADA, TENANT, book_iri

ROLES = Path(__file__).parents[2] / "fixtures" / "library" / "library_roles.yaml"
BOOK_B = book_iri(1)
OTHER_BOOK = book_iri(2)
BOOK_B_GRAPH = f"{BOOK_B}/graph"
ALLOW = None  # the cell answers "allow": the check returns


def caller(*global_roles: str) -> VerifiedCaller:
    return VerifiedCaller(principal=ADA, global_roles=list(global_roles) or None)


def role(name: str) -> Grant:
    return Grant(assignee=ADA, target=TENANT, role=name)


def direct_modify_on_b() -> Grant:
    return Grant(assignee=ADA, target=BOOK_B_GRAPH, action=Action.MODIFY)


def held(
    *grants: Grant, prohibitions: list[Prohibition] | None = None, deleting: bool = False
) -> CallerAccess:
    state = TenantState.DELETING if deleting else TenantState.ACTIVE
    return CallerAccess(
        tenant=TENANT, state=state, grants=list(grants) or None, prohibitions=prohibitions
    )


# The callers, the rows of the matrix.
CALLERS = {
    "admin": (caller("admin"), held()),
    "librarian": (caller(), held(role("librarian"))),
    "reader": (caller(), held(role("reader"))),
    "direct-modify-on-B": (caller(), held(direct_modify_on_b())),
    "reader+direct-modify-on-B": (caller(), held(role("reader"), direct_modify_on_b())),
    "librarian+prohibition-of-modify-on-B": (
        caller(),
        held(
            role("librarian"),
            prohibitions=[Prohibition(assignee=ADA, target=BOOK_B_GRAPH, action=Action.MODIFY)],
        ),
    ),
    "outsider": (caller(), held()),
    "deleting-librarian": (caller(), held(role("librarian"), deleting=True)),
    "deleting-admin": (caller("admin"), held(deleting=True)),
}

# The columns: what is asked of whom. "create" is modify at tenant scope (PD-9).
REQUESTS = {
    "read B": (BOOK_B, Action.READ),
    "read other": (OTHER_BOOK, Action.READ),
    "modify B": (BOOK_B, Action.MODIFY),
    "modify other": (OTHER_BOOK, Action.MODIFY),
    "create": (TENANT, Action.MODIFY),
    "delete B": (BOOK_B, Action.DELETE),
    "delete other": (OTHER_BOOK, Action.DELETE),
    "administer grants": (TENANT, Action.ADMINISTER),
    "delete tenant": (TENANT, Action.DELETE),
    "list books": (TENANT, Action.READ),
}
COLUMNS = tuple(REQUESTS)


def row(
    *answers: type[Forbidden | NotFound] | None,
) -> dict[str, type[Forbidden | NotFound] | None]:
    """One row of the table: an answer per column, in the order of COLUMNS."""
    assert len(answers) == len(COLUMNS), "a row answers every column"
    return dict(zip(COLUMNS, answers, strict=True))


F, N = Forbidden, NotFound
#          read B  read o  mod B   mod o   create  del B   del o   admin   del T   list
EXPECTED = {
    "admin": row(ALLOW, ALLOW, F, F, F, F, F, F, F, ALLOW),
    "librarian": row(*[ALLOW] * 10),
    "reader": row(ALLOW, ALLOW, F, F, F, F, F, F, F, ALLOW),
    "direct-modify-on-B": row(ALLOW, N, ALLOW, N, N, F, N, N, N, N),
    "reader+direct-modify-on-B": row(ALLOW, ALLOW, ALLOW, F, F, F, F, F, F, ALLOW),
    "librarian+prohibition-of-modify-on-B": row(
        ALLOW, ALLOW, F, ALLOW, ALLOW, ALLOW, ALLOW, ALLOW, ALLOW, ALLOW
    ),
    "outsider": row(*[N] * 10),
    "deleting-librarian": row(*[N] * 10),
    "deleting-admin": row(*[N] * 10),
}
CELLS = [(who, column) for who, column in product(CALLERS, COLUMNS)]


def test_the_table_has_a_row_for_every_caller_and_a_cell_for_every_column():
    assert set(EXPECTED) == set(CALLERS), "a caller without a row, or a row without a caller"
    assert {(who, column) for who in EXPECTED for column in EXPECTED[who]} == set(CELLS), "cells"


@pytest.mark.parametrize(("who", "column"), CELLS, ids=[f"{w}|{c}" for w, c in CELLS])
def test_each_cell_of_the_matrix(who: str, column: str):
    rules = AccessRules(load_role_definitions(ROLES))
    verified, access = CALLERS[who]
    target, action = REQUESTS[column]
    expected = EXPECTED[who][column]
    if expected is ALLOW:
        rules.allowed(verified, access, target, action)
        return
    with pytest.raises(expected):
        rules.allowed(verified, access, target, action)
