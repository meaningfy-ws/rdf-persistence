"""PD-9's matrix of the toy library, every cell: who may do what, answered allow, 403 or 404."""

from itertools import product

import pytest

from rdf_persistence import Action, TenantState
from rdf_persistence.domain.exceptions import Forbidden, NotFound
from rdf_persistence.services.access import AccessRules, load_role_definitions
from tests.toy import ROLES, TENANT, ban, book_iri, caller, direct, graph_of, held, role

BOOK_B = book_iri(1)
OTHER_BOOK = book_iri(2)
BOOK_B_GRAPH = graph_of(BOOK_B)
ALLOW = None  # the cell answers "allow": the check returns
DELETING = TenantState.DELETING


# The callers, the rows of the matrix.
CALLERS = {
    "admin": (caller("admin"), held()),
    "librarian": (caller(), held(role("librarian"))),
    "reader": (caller(), held(role("reader"))),
    "direct-modify-on-B": (caller(), held(direct(Action.MODIFY, BOOK_B_GRAPH))),
    "reader+direct-modify-on-B": (
        caller(),
        held(role("reader"), direct(Action.MODIFY, BOOK_B_GRAPH)),
    ),
    "librarian+prohibition-of-modify-on-B": (
        caller(),
        held(role("librarian"), bans=[ban(Action.MODIFY, BOOK_B_GRAPH)]),
    ),
    "outsider": (caller(), held()),
    "deleting-librarian": (caller(), held(role("librarian"), state=DELETING)),
    "deleting-admin": (caller("admin"), held(state=DELETING)),
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
        rules.require(verified, access, target, action)
        return
    with pytest.raises(expected):
        rules.require(verified, access, target, action)
