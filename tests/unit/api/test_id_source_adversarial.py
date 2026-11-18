"""The `id_source` of a service, attacked through the routes: clashing tenant and aggregate ids."""

import uuid

from tests.toy_service import DUNE_BODY, TENANT_BODY, ToyService


async def test_a_tenant_id_that_clashes_many_times_is_redrawn_until_a_fresh_one() -> None:
    first, fresh = str(uuid.uuid4()), str(uuid.uuid4())
    draws = iter([first] * 5 + [fresh])  # one for the first create, four clashes, then fresh
    toy = ToyService(id_source=lambda _spec: next(draws))
    async with toy.app.router.lifespan_context(toy.app), toy.client() as http:
        one = await http.post("/libraries", json=TENANT_BODY, headers=toy.bearer("ada"))
        two = await http.post("/libraries", json=TENANT_BODY, headers=toy.bearer("ada"))
    assert (one.status_code, two.status_code) == (201, 201), two.text
    assert two.headers["location"].endswith(f"/{fresh}"), "the clash was redrawn"


async def test_a_tenant_id_source_that_only_clashes_ends_in_a_problem_not_a_hang() -> None:
    # MAX_TENANT_CLASH_DRAWS (5) draws all clash: the service gives up with a 5xx, never loops
    same = str(uuid.uuid4())
    toy = ToyService(id_source=lambda _spec: same)
    async with toy.app.router.lifespan_context(toy.app), toy.client() as http:
        one = await http.post("/libraries", json=TENANT_BODY, headers=toy.bearer("ada"))
        two = await http.post("/libraries", json=TENANT_BODY, headers=toy.bearer("ada"))
        again = await http.get(one.headers["location"], headers=toy.bearer("ada"))
    assert one.status_code == 201, "the first create succeeded"
    assert two.status_code >= 400, "a second tenant cannot take the first one's id"
    assert again.status_code == 200, "and the first is unharmed"


async def test_an_aggregate_id_that_clashes_with_a_stored_one_is_not_a_server_error() -> None:
    """Shows today: only tenant ids are redrawn (PD-5); a second book given the first's id is a 5xx."""
    drawn: list[str] = []
    replay: list[str] = []

    def source(_spec) -> str:
        value = replay.pop(0) if replay else str(uuid.uuid4())
        drawn.append(value)
        return value

    toy = ToyService(id_source=source)
    async with toy.app.router.lifespan_context(toy.app), toy.client() as http:
        headers = toy.bearer("ada")
        made = await http.post("/libraries", json=TENANT_BODY, headers=headers)
        tenant = made.headers["location"]
        mark = len(drawn)
        one = await http.post(f"{tenant}/books", json=DUNE_BODY, headers=headers)
        replay.extend(drawn[mark : mark + 1])  # the second book's first draw is the first book's id
        two = await http.post(f"{tenant}/books", json=DUNE_BODY, headers=headers)
        again = await http.get(one.headers["location"], headers=headers)
    assert one.status_code == 201, "the first create succeeded"
    assert two.status_code < 500, f"a clashing aggregate id gave {two.status_code}: {two.text}"
    assert again.status_code == 200, "and the first book is unharmed"
