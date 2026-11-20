"""ReferencedRemovals.in_use: the diagnosis of a refused removal, named and capped (PD-7, PD-10, TC-6)."""

from collections.abc import Iterable, Sequence

import pytest
from rdflib import URIRef

from rdf_persistence.collaboration.services.referenced_removals import ReferencedRemovals
from rdf_persistence.core.domain.exceptions import InUse
from rdf_persistence.persistence.services.generated.settings.rp_persistence_settings import (
    LimitSettings,
)
from rdf_persistence.persistence.services.session import ReferrerRow
from rdf_persistence.schema.services import schema_structure
from rdf_persistence.schema.services.schema import load_schema
from tests.toy import TOY_SCHEMA, book_iri

VIEW = load_schema(TOY_SCHEMA)
BOOK = VIEW.get_uri("Book", expand=True)
WRITTEN_BY = VIEW.get_uri("written_by", expand=True)
A1 = "https://example.org/tenants/t1/authors/a1"
A2 = "https://example.org/tenants/t1/authors/a2"


def removals(cap: int = 20) -> ReferencedRemovals:
    return ReferencedRemovals(VIEW, LimitSettings(max_named_referrers=cap))


def written_by(*books: str) -> list[ReferrerRow]:
    return [(b, BOOK, None, WRITTEN_BY) for b in books]


def only(readable: Iterable[str]):
    """A ``readable`` that lets the caller read the listed referrers and no other."""
    allowed = set(readable)

    async def read(iri: str, rows: Sequence[ReferrerRow]) -> set[str]:
        return {row[0] for row in rows} & allowed

    return read


def test_it_refuses_the_classes_the_schema_marks_as_refusing():
    assert removals().refusing == schema_structure.refusing_classes(VIEW)
    assert URIRef(VIEW.get_uri("Author", expand=True)) in removals().refusing


async def test_a_readable_referrer_is_named_with_its_class_and_slot():  # E1
    refused = await removals().in_use([A1], written_by(book_iri(1)), only([book_iri(1)]))
    assert isinstance(refused, InUse)
    assert refused.iris == (A1,), "the refused root"
    assert refused.referrers == ((book_iri(1), "Book", "written_by"),), "named by the schema"
    assert (refused.more_count, refused.hidden_count) == (0, 0), "nothing left out"


async def test_only_unreadable_referrers_are_counted_and_not_named():  # E2
    refused = await removals().in_use([A1], written_by(book_iri(2)), only([]))
    assert refused.referrers == (), "nothing is named"
    assert refused.hidden_count == 1, "the aggregate is counted"
    assert refused.more_count == 0


async def test_the_named_are_capped_and_the_rest_counted_in_more_count():  # E5
    books = [book_iri(n) for n in range(1, 26)]
    refused = await removals(cap=20).in_use([A1], written_by(*books), only(books))
    assert [r[0] for r in refused.referrers] == sorted(books)[:20], "the first 20 by IRI"
    assert refused.more_count == 5, "the other 25 - 20 readable"
    assert refused.hidden_count == 0


async def test_a_comment_seen_in_its_thread_is_named_and_one_not_seen_is_hidden():  # matrix 9
    comment = VIEW.get_uri("Comment", expand=True)
    on = VIEW.get_uri("comment_references", expand=True)
    seen, unseen = (
        "urn:uuid:00000000-0000-4000-8000-000000000001",
        "urn:uuid:00000000-0000-4000-8000-000000000002",
    )
    rows = [(seen, comment, None, on), (unseen, comment, None, on)]
    refused = await removals().in_use([A1], rows, only([seen]))
    assert refused.referrers == ((seen, "Comment", "comment_references"),)
    assert refused.hidden_count == 1, "the comment the thread hides is counted"


async def test_a_referrer_with_two_slots_is_named_with_each_and_counted_once():
    book = book_iri(1)
    sequel = VIEW.get_uri("sequel_of", expand=True)
    rows = [*written_by(book), (book, BOOK, None, sequel)]
    refused = await removals(cap=1).in_use([A1], rows, only([book]))
    assert refused.referrers == ((book, "Book", "sequel_of"), (book, "Book", "written_by"))
    assert refused.more_count == 0, "one aggregate, so within the cap of one"


async def test_a_cap_of_zero_names_none_and_counts_all_as_more():
    books = [book_iri(1), book_iri(2)]
    refused = await removals(cap=0).in_use([A1], written_by(*books), only(books))
    assert refused.referrers == ()
    assert refused.more_count == 2
    assert refused.hidden_count == 0


async def test_no_readable_callable_means_every_referrer_is_readable():
    books = [book_iri(n) for n in range(1, 4)]
    refused = await removals(cap=2).in_use([A1], written_by(*books), None)
    assert [r[0] for r in refused.referrers] == books[:2]
    assert (refused.more_count, refused.hidden_count) == (1, 0)


async def test_the_refused_roots_are_all_reported_sorted():
    refused = await removals().in_use([A2, A1], written_by(book_iri(1)), None)
    assert refused.iris == (A1, A2)


@pytest.mark.parametrize("cap", [0, 1, 20])
async def test_no_rows_name_nothing(cap):
    refused = await removals(cap).in_use([A1], [], None)
    assert (refused.referrers, refused.more_count, refused.hidden_count) == ((), 0, 0)
