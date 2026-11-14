"""``visible``: the one rule of who sees a comment, on models alone, no store (PD-14, PD-30 items 4 and 9)."""

import random
from datetime import UTC, datetime, timedelta

from rdf_persistence.domain.generated.rp_discussion import Comment, Motivation
from rdf_persistence.services.discussion import visible

TARGET = "https://example.org/libraries/6f1c0c1e/books/b1"
T0 = datetime(2026, 11, 14, 9, tzinfo=UTC)
CHAIN = 5000
SEEN = {"reader"}


def comment_id(n: int) -> str:
    return f"https://example.org/libraries/6f1c0c1e/rp-comments/{n:08d}"


def comment(
    n: int, *, parent: int | None = None, created: datetime | None = T0, **slots
) -> Comment:
    """The comment number ``n`` (its IRI sorts like ``n``), a reply to ``parent`` when given."""
    return Comment(
        id=comment_id(n),
        has_target=TARGET,
        body_value="remark",
        motivated_by=Motivation.COMMENTING if parent is None else Motivation.REPLYING,
        replies_to=None if parent is None else comment_id(parent),
        created=created,
        **slots,
    )


def chain(*, hidden: int | None = None) -> list[Comment]:
    """``CHAIN`` replies, each answering the one before it, each a second later; ``hidden`` has an audience nobody meets."""
    return [
        comment(
            n,
            parent=None if n == 1 else n - 1,
            created=T0 + timedelta(seconds=n),
            comment_audience=["nobody"] if n == hidden else None,
        )
        for n in range(1, CHAIN + 1)
    ]


def test_a_chain_of_five_thousand_replies_in_any_order_is_visible_in_order() -> None:
    shuffled = chain()
    random.Random(7).shuffle(shuffled)
    found = visible(shuffled, SEEN)
    assert [c.id for c in found] == [comment_id(n) for n in range(1, CHAIN + 1)], (
        "no RecursionError, and every reply of the chain is seen, oldest first"
    )


def test_a_hidden_comment_in_the_middle_of_a_long_chain_hides_everything_below_it() -> None:
    shuffled = chain(hidden=2500)
    random.Random(7).shuffle(shuffled)
    found = visible(shuffled, SEEN)
    assert [c.id for c in found] == [comment_id(n) for n in range(1, 2500)], (
        "the replies above the hidden comment stay, it and its descendants go"
    )


def test_a_cycle_in_stored_replies_is_hidden() -> None:
    one, two = comment(1, parent=2), comment(2, parent=1)
    assert visible([one, two, comment(3)], SEEN) == [comment(3)], (
        "only the comment outside the cycle"
    )


def test_a_reply_whose_parent_is_missing_is_hidden() -> None:
    assert visible([comment(2, parent=1)], SEEN) == [], "the parent is not in the thread"


def test_a_naive_time_and_a_missing_time_do_not_break_the_order() -> None:
    naive = comment(2, created=datetime(2026, 11, 14, 8))
    aware = comment(3, created=T0)
    untimed = comment(1, created=None)
    assert [c.id for c in visible([aware, naive, untimed], SEEN)] == [
        comment_id(1),
        comment_id(2),
        comment_id(3),
    ], "no time first, then by time, a naive one read as UTC"
