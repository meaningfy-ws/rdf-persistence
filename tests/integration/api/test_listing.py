"""Scenarios 'a page of books' (rp-service-api) and 'an injection attempt' (rp-aggregate-store), against Fuseki."""

import pytest
from rdflib import Dataset, URIRef

from rdf_persistence import Page
from tests.toy_service import DUNE_BODY, TENANT_BODY, ToyService, assert_problem

LABELS = ["Dune", "Emma", "Ulysses", "Candide", "Beloved"]
INJECTIONS = [
    '"} ; DROP ALL ; #',
    "\\",
]


async def library_of(toy: ToyService, http, who: str, labels: list[str]) -> str:
    """A tenant of ``who`` with one book per label; the path of its books."""
    made = await http.post("/libraries", json=TENANT_BODY, headers=toy.bearer(who))
    path = f"{made.headers['location']}/books"
    for label in labels:
        created = await http.post(path, json={**DUNE_BODY, "label": label}, headers=toy.bearer(who))
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
        ("label~=DUNE", ["Dune"]),
        ("label~=u&sort=label", ["Dune", "Ulysses"]),
        ("label~=u&sort=label&limit=1&offset=1", ["Ulysses"]),
    ],
)
async def test_sort_filters_and_paging_work_against_fuseki(toy, client, query, expected) -> None:
    path = await library_of(toy, client, "ada", LABELS)
    page = (await client.get(f"{path}?{query}", headers=toy.bearer("ada"))).json()
    assert [book["label"] for book in page["items"]] == expected, (
        "the page holds the expected labels in order"
    )


async def test_the_total_of_a_contains_page_counts_every_match_not_the_page(toy, client) -> None:
    path = await library_of(toy, client, "ada", LABELS)
    page = (
        await client.get(f"{path}?label~=u&sort=label&limit=1&offset=1", headers=toy.bearer("ada"))
    ).json()
    assert [book["label"] for book in page["items"]] == ["Ulysses"], "the second match"
    assert page["total"] == 2, "the total counts both matches, not the one on the page"


async def test_a_book_with_two_matching_values_is_listed_once_so_the_page_after_the_matches_is_empty(
    toy, client
) -> None:
    made = await client.post("/libraries", json=TENANT_BODY, headers=toy.bearer("ada"))
    path = f"{made.headers['location']}/books"
    for label, authors in [
        ("Dune", ["Herbert"]),
        ("Emma", ["Austen"]),
        ("Ulysses", ["Joyce", "Herbert"]),
    ]:
        created = await client.post(
            path, json={**DUNE_BODY, "label": label, "authors": authors}, headers=toy.bearer("ada")
        )
        assert created.status_code == 201, created.text
    page = (await client.get(f"{path}?authors~=e&offset=3", headers=toy.bearer("ada"))).json()
    assert page["items"] == [], "three books match; a join would list the fourth row, Ulysses again"
    assert page["total"] == 3, "and the total counts each book once"


@pytest.mark.parametrize("slot", ["label", "label~"])
@pytest.mark.parametrize("value", INJECTIONS, ids=range(len(INJECTIONS)))
async def test_an_injection_through_a_filter_matches_nothing_and_changes_nothing(
    toy, client, store, prefix, slot, value
) -> None:
    mine = await library_of(toy, client, "ada", LABELS)
    theirs = await library_of(toy, client, "bob", ["Secret"])
    datasets = sorted(name for name in await store.list_datasets() if name.startswith(prefix))
    response = await client.get(mine, params={slot: value}, headers=toy.bearer("ada"))
    assert response.status_code == 200, response.text
    assert response.json()["items"] == [], "no book matches, and no foreign data comes back"
    assert response.json()["total"] == 0, "an injected filter matches nothing"
    after = await client.get(mine, headers=toy.bearer("ada"))
    other = await client.get(theirs, headers=toy.bearer("bob"))
    assert after.json()["total"] == 5, "every book is still there"
    assert other.json()["total"] == 1, "so is every book of the other tenant"
    assert sorted(n for n in await store.list_datasets() if n.startswith(prefix)) == datasets, (
        "and every database"
    )


async def tenant_quads(store, prefix: str) -> tuple[str, Dataset]:
    """The tenant database of the test (the one holding books) and its quads."""
    for name in sorted(n for n in await store.list_datasets() if n.startswith(prefix)):
        quads = Dataset().parse(data=await store.export_quads(name), format="nquads")
        if any(str(o) == "Dune" for _, _, o, _ in quads.quads()):
            return name, quads
    raise AssertionError("no database of the test holds a book")


@pytest.mark.parametrize("other", ["a sibling book's graph", "a fresh graph"])
async def test_a_value_in_another_graph_does_not_make_an_aggregate_match(
    toy, client, store, prefix, other
) -> None:
    path = await library_of(toy, client, "ada", LABELS)
    database, quads = await tenant_quads(store, prefix)
    dune, label, dune_graph = next((s, p, g) for s, p, o, g in quads.quads() if str(o) == "Dune")
    elsewhere = (
        next(g for _, _, o, g in quads.quads() if str(o) == "Emma")
        if other == "a sibling book's graph"
        else URIRef("https://example.org/graphs/elsewhere")
    )
    assert elsewhere != dune_graph, "the stray triple goes to a graph that is not Dune's"
    await store.update(
        database,
        f'INSERT DATA {{ GRAPH <{elsewhere}> {{ <{dune}> <{label}> "Zebra" }} }}',
    )
    stray = (await client.get(path, params={"label~": "zebra"}, headers=toy.bearer("ada"))).json()
    assert stray["items"] == [], "Fuseki looks for the text in the aggregate's own graph only"
    assert stray["total"] == 0, "and counts no aggregate for the stray triple"
    real = (await client.get(path, params={"label~": "dun"}, headers=toy.bearer("ada"))).json()
    assert [book["label"] for book in real["items"]] == ["Dune"], "the real label still matches"


async def test_an_injection_through_a_reference_filter_is_a_bad_query(toy, client) -> None:
    mine = await library_of(toy, client, "ada", ["Dune"])
    response = await client.get(
        f"{mine.removesuffix('books')}scans",
        params={"scan_of": "https://example.org/b> } ; DROP ALL ; #"},
        headers=toy.bearer("ada"),
    )
    assert_problem(response, 400, "bad-query")
    assert (await client.get(mine, headers=toy.bearer("ada"))).json()["total"] == 1, (
        "the injected reference filter changed nothing"
    )
