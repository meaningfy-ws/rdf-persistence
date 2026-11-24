"""Listings over the router and the fakes: the cases that write (PD-9, PD-15).

The read-only cases share one store in ``test_listing_routes_read.py`` (PD-3); the five here
change the store, so each gets a shelf of its own.
"""

import httpx
import pytest

from rdf_persistence import Page
from rdf_persistence.access.domain.generated.rp_access import Action, Grant, Prohibition
from tests.toy_service import DUNE_BODY, TENANT_BODY, ToyService, assert_problem, principal_of
from tests.unit.api.listing_shelf import Shelf

PROBLEM_BAD_QUERY_SLUG = "bad-query"


@pytest.fixture
async def shelf(service: ToyService, client: httpx.AsyncClient) -> Shelf:
    return await Shelf.set_up(service, client)


async def test_a_listing_never_shows_the_books_of_another_tenant(shelf, client, service) -> None:
    other = await client.post("/libraries", json=TENANT_BODY, headers=shelf.headers("bob"))
    await client.post(
        f"{other.headers['location']}/books", json=DUNE_BODY, headers=shelf.headers("bob")
    )
    assert len(await shelf.labels()) == 5, "the caller sees the five books of the own tenant"
    theirs = await client.get(f"{other.headers['location']}/books", headers=shelf.headers("bob"))
    assert theirs.json()["total"] == 1, "the other tenant's listing counts only its own book"


async def test_a_permission_on_one_book_alone_does_not_list_books(shelf) -> None:
    book = shelf.books["Dune"]
    await shelf.grant(
        Grant(assignee=principal_of("bea"), target=f"{book}/graph", action=Action.MODIFY)
    )
    own = await shelf.http.get(
        shelf.path + "/" + book.rsplit("/", 1)[1], headers=shelf.headers("bea")
    )
    listing = await shelf.page_of(who="bea")
    assert own.status_code == 200, "she can read the book she may modify"
    assert listing.status_code == 404, "but a listing needs read on the tenant"


async def test_a_book_the_caller_is_prohibited_from_reading_is_not_listed_or_counted(shelf) -> None:
    hidden = shelf.books["Emma"]
    await shelf.grant(
        prohibitions=[
            Prohibition(assignee=principal_of("rita"), target=f"{hidden}/graph", action=Action.READ)
        ]
    )
    page = Page.model_validate((await shelf.page_of("limit=2", who="rita")).json())
    assert "Emma" not in [i["label"] for i in page.items], (
        "the prohibited book is left out of the listing"
    )
    assert page.total == 4, "the total leaves it out as well"
    assert len(await shelf.labels(who="ada")) == 5, "the librarian is not prohibited"


async def test_a_prohibition_of_modify_leaves_the_book_in_the_listing(shelf) -> None:
    book = shelf.books["Emma"]
    await shelf.grant(
        prohibitions=[
            Prohibition(assignee=principal_of("rita"), target=f"{book}/graph", action=Action.MODIFY)
        ]
    )
    assert len(await shelf.labels(who="rita")) == 5, (
        "a modify prohibition leaves all five books listed"
    )


async def test_the_tenant_listing_is_paged_by_iri_like_any_other(shelf, client) -> None:
    for name in ("Two", "Three"):
        await client.post(
            "/libraries", json={**TENANT_BODY, "label": name}, headers=shelf.headers()
        )
    everyone = (await client.get("/libraries", headers=shelf.headers())).json()
    ids = [t["id"] for t in everyone["items"]]
    page = Page.model_validate(
        (await client.get("/libraries?limit=2&offset=1", headers=shelf.headers())).json()
    )
    assert ids == sorted(ids), "ordered by IRI"
    assert page.total == 3, "the total counts every library"
    assert page.limit == 2, "the page keeps the requested limit"
    assert page.offset == 1, "the page keeps the requested offset"
    assert [t["id"] for t in page.items] == ids[1:3], (
        "the page holds the libraries at the requested offset, in IRI order"
    )


@pytest.fixture
async def dunes(service: ToyService, client: httpx.AsyncClient) -> Shelf:
    """A tenant of ``ada`` with three books: Dune, Children of Dune (nonfiction) and Emma."""
    shelf = Shelf(service, client)
    made = await client.post("/libraries", json=TENANT_BODY, headers=shelf.headers())
    shelf.tenant, shelf.tenant_iri = made.headers["location"], made.json()["id"]
    for label, genre in [
        ("Dune", "fiction"),
        ("Children of Dune", "nonfiction"),
        ("Emma", "fiction"),
    ]:
        body = {**DUNE_BODY, "label": label, "genre": genre}
        created = await client.post(shelf.path, json=body, headers=shelf.headers())
        assert created.status_code == 201, created.text
    return shelf


# TC-09a, TC-09c
async def test_a_contains_filter_lists_the_books_whose_text_holds_it(dunes: Shelf) -> None:
    page = Page.model_validate((await dunes.page_of("label~=DUNE")).json())
    assert sorted(i["label"] for i in page.items) == ["Children of Dune", "Dune"], (
        "a substring in any case lists both books"
    )
    assert page.total == 2, "and the total counts both"
    combined = Page.model_validate((await dunes.page_of("label~=dune&genre=fiction")).json())
    assert [i["label"] for i in combined.items] == ["Dune"], "a contains and an equality both hold"
    assert combined.total == 1, "and the total agrees"


# TC-09b, TC-09d
@pytest.mark.parametrize("query", ["published~=19", "label~=", "label~"])
async def test_a_contains_filter_that_cannot_hold_is_a_bad_query(dunes: Shelf, query: str) -> None:
    assert_problem(await dunes.page_of(query), 400, PROBLEM_BAD_QUERY_SLUG)


async def test_an_absent_filter_lists_the_books_with_no_value_and_counts_them(dunes: Shelf) -> None:
    withdrawn = await dunes.http.post(
        dunes.path,
        json={**DUNE_BODY, "label": "Dated", "published": "1965-08-01"},
        headers=dunes.headers(),
    )
    assert withdrawn.status_code == 201, withdrawn.text
    page = Page.model_validate((await dunes.page_of("absent=published&sort=label")).json())
    assert [i["label"] for i in page.items] == ["Children of Dune", "Dune", "Emma"], (
        "the three books with no publication date, not the dated one"
    )
    assert page.total == 3, "and the total counts them"
    both = Page.model_validate((await dunes.page_of("absent=published&genre=fiction")).json())
    assert sorted(i["label"] for i in both.items) == ["Dune", "Emma"], "absence and equality hold"
    assert both.total == 2, "and the total agrees"


# E11, E13, E16
@pytest.mark.parametrize("query", ["absent=nosuch", "absent=", "absent~=label", "absent=id"])
async def test_an_absent_filter_that_names_no_listable_slot_is_a_bad_query(
    dunes: Shelf, query: str
) -> None:
    assert_problem(await dunes.page_of(query), 400, PROBLEM_BAD_QUERY_SLUG)


async def test_an_offset_beyond_the_largest_whole_number_a_page_can_start_at_is_a_bad_query(
    dunes: Shelf,
) -> None:
    assert_problem(await dunes.page_of("offset=9223372036854775758"), 400, PROBLEM_BAD_QUERY_SLUG)


# TC-09e
async def test_the_tenant_listing_still_refuses_a_contains_filter(
    dunes: Shelf, client: httpx.AsyncClient
) -> None:
    response = await client.get("/libraries?label~=x", headers=dunes.headers())
    assert response.status_code == 400, "the tenant listing refuses every filter"
