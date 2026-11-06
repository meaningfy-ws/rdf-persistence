"""Which aggregates a listing leaves out for a caller: the ones a Prohibition of ``read`` names (PD-9)."""

import pytest

from rdf_persistence import Action
from rdf_persistence.services.access import AccessRules, load_role_definitions
from tests.toy import ADA, BOB, ROLES, ban, book_iri, caller, graph_of, held, role

RULES = AccessRules(load_role_definitions(ROLES))
ONE, TWO = graph_of(book_iri(1)), graph_of(book_iri(2))


@pytest.mark.parametrize(
    ("bans", "hidden"),
    [
        ([], []),
        ([ban(Action.READ, ONE)], [ONE]),
        ([ban(Action.READ, TWO), ban(Action.READ, ONE)], [ONE, TWO]),
        ([ban(Action.MODIFY, ONE)], []),
        ([ban(Action.DELETE, ONE)], []),
        ([ban(Action.READ, ONE, who=BOB)], []),
        ([ban(Action.READ, ONE), ban(Action.READ, ONE)], [ONE]),
    ],
    ids=[
        "no prohibition",
        "read of one book",
        "two books, sorted",
        "a prohibition of modify still lists the book",
        "a prohibition of delete still lists the book",
        "another principal's prohibition",
        "the same one twice",
    ],
)
def test_a_listing_leaves_out_the_aggregates_the_caller_is_prohibited_from_reading(bans, hidden):
    assert RULES.hidden_graphs(caller(principal=ADA), held(role("reader"), bans=bans)) == hidden
