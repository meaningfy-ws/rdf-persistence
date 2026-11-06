"""Scenarios 'a page of books' (rp-service-api) and 'an injection attempt' (rp-aggregate-store), against Fuseki."""

import pytest

from rdf_persistence import Page
from tests.integration.api.conftest import BOOK, TENANT_BODY
from tests.toy_service import ToyService

LABELS = ["Dune", "Emma", "Ulysses", "Candide", "Beloved"]
INJECTIONS = [
    '"} ; DROP ALL ; #',
    '" } UNION { GRAPH ?g { ?s ?p ?o } } #',
    '"^^<http://www.w3.org/2001/XMLSchema#string> } ; CLEAR ALL ; #',
    "\\",
    'Dune" . ?root ?p ?o . FILTER("',
]


async def library_of(toy: ToyService, http, who: str, labels: list[str]) -> str:
    """A tenant of ``who`` with one book per label; the path of its books."""
    made = await http.post("/libraries", json=TENANT_BODY, headers=toy.bearer(who))
    path = f"{made.headers['location']}/books"
    for label in labels:
        created = await http.post(path, json={**BOOK, "label": label}, headers=toy.bearer(who))
        assert created.status_code == 201, created.text
    return path


async def test_a_page_holds_the_third_and_fourth_books_by_iri_and_the_total(toy, client) -> None:
    path = await library_of(toy, client, "ada", LABELS)
    everything = (await client.get(path, headers=toy.bearer("ada"))).json()["items"]
    page = Page.model_validate(
        (await client.get(f"{path}?limit=2&offset=2", headers=toy.bearer("ada"))).json()
    )
    ids = [book["id"] for book in everything]
    assert ids == sorted(ids), "no sort key: IRI order"
    assert [book["id"] for book in page.items] == ids[2:4], "the third and fourth books"
    assert (page.total, page.limit, page.offset) == (5, 2, 2), "and the count of the whole listing"


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("sort=label", ["Beloved", "Candide", "Dune", "Emma", "Ulysses"]),
        ("sort=-label&limit=2&offset=1", ["Emma", "Dune"]),
        ("label=Emma", ["Emma"]),
        ("genre=fiction&label=Dune", ["Dune"]),
        ("genre=poetry", []),
    ],
)
async def test_sort_filters_and_paging_work_against_fuseki(toy, client, query, expected) -> None:
    path = await library_of(toy, client, "ada", LABELS)
    page = (await client.get(f"{path}?{query}", headers=toy.bearer("ada"))).json()
    assert [book["label"] for book in page["items"]] == expected


@pytest.mark.parametrize("value", INJECTIONS, ids=range(len(INJECTIONS)))
async def test_an_injection_through_a_filter_matches_nothing_and_changes_nothing(
    toy, client, store, prefix, value
) -> None:
    mine = await library_of(toy, client, "ada", LABELS)
    theirs = await library_of(toy, client, "bob", ["Secret"])
    datasets = sorted(name for name in await store.list_datasets() if name.startswith(prefix))
    response = await client.get(mine, params={"label": value}, headers=toy.bearer("ada"))
    assert response.status_code == 200, response.text
    assert response.json()["items"] == [], "no book matches, and no foreign data comes back"
    assert response.json()["total"] == 0
    after = await client.get(mine, headers=toy.bearer("ada"))
    other = await client.get(theirs, headers=toy.bearer("bob"))
    assert after.json()["total"] == 5, "every book is still there"
    assert other.json()["total"] == 1, "so is every book of the other tenant"
    assert sorted(n for n in await store.list_datasets() if n.startswith(prefix)) == datasets, (
        "and every database"
    )


async def test_an_injection_through_a_reference_filter_is_a_bad_query(toy, client) -> None:
    mine = await library_of(toy, client, "ada", ["Dune"])
    response = await client.get(
        f"{mine.removesuffix('books')}scans",
        params={"scan_of": "https://example.org/b> } ; DROP ALL ; #"},
        headers=toy.bearer("ada"),
    )
    assert response.status_code == 400, response.text
    assert (await client.get(mine, headers=toy.bearer("ada"))).json()["total"] == 1
