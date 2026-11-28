"""Access on the cascade of a delete (dependent-aggregates DEC-2, PD-10, D-1; A-6).

An audit A1 is the whole, its result R1 and R1's finding F1 the parts (a finding refuses deletion while
another aggregate cites it). ``ada`` is the tenant's creator and reads everything unless a test bars her;
``dan`` holds the right to delete A1 and nothing on its parts.
"""

import asyncio
from collections.abc import AsyncIterator

import httpx
import pytest

from rdf_persistence import GrantSet
from rdf_persistence.access.domain.generated.rp_access import Action, Grant, Prohibition
from rdf_persistence.core.domain.exceptions import Refused
from rdf_persistence.iris.domain.layout import graph_iri
from rdf_persistence.provenance.domain.generated.rp_provenance import Remove
from tests.events_follow import (
    listening,
    mount,
    opening,
    reshape_grants,
    with_carol,
)
from tests.scene import Scene
from tests.toy_service import ToyService, principal_of

BODY = {"label": "Item", "description": "An item."}


def refuse_finding(old, who, reader) -> None:
    """A delete rule whose message names the finding it refuses."""
    raise Refused(f"the finding {old.id} is still open")


class Tree:
    """A tenant of ``ada`` holding A1, its result R1, R1's finding F1, and what the test adds."""

    def __init__(self, scene: Scene) -> None:
        self.scene, self.http = scene, scene.http
        self.a1 = self.r1 = self.f1 = ""

    async def set_up(self) -> "Tree":
        self.a1 = await self.created("audits")
        self.r1 = await self.created("audit-results", of_audit=self.a1)
        self.f1 = await self.created("audit-findings", of_result=self.r1)
        return self

    def url(self, iri: str, collection: str) -> str:
        return f"{self.scene.tenant}/{collection}/{iri.rsplit('/', 1)[1]}"

    async def created(self, collection: str, **slots: str) -> str:
        made = await self.http.post(
            f"{self.scene.tenant}/{collection}",
            json={**BODY, **slots},
            headers=self.scene.headers("ada"),
        )
        assert made.status_code == 201, made.text
        return made.json()["id"]

    async def delete(self, who: str, iri: str, collection: str) -> httpx.Response:
        url = self.url(iri, collection)
        etag = (await self.http.get(url, headers=self.scene.headers("ada"))).headers["etag"]
        return await self.http.delete(url, headers=self.scene.headers(who, **{"If-Match": etag}))

    async def exists(self, iri: str, collection: str) -> bool:
        """Whether ``rita``, a reader no test bars, finds it."""
        url = self.url(iri, collection)
        return (await self.http.get(url, headers=self.scene.headers("rita"))).status_code == 200

    async def cite(self, finding: str) -> str:
        """An audit that cites ``finding``, from outside A1's parts."""
        return await self.created("audits", cites_finding=finding)

    async def grant(self, *grants: Grant, bar: Prohibition | None = None) -> None:
        def edit(held: GrantSet) -> GrantSet:
            return GrantSet(
                grants=[*held.grants, *grants], prohibitions=[bar] if bar is not None else None
            )

        await reshape_grants(self.scene, edit)

    def bar_ada_from(self, iri: str) -> Prohibition:
        return Prohibition(
            assignee=principal_of("ada"), target=str(graph_iri(iri)), action=Action.READ
        )


@pytest.fixture
async def tree(scene: Scene) -> Tree:
    return await Tree(scene).set_up()


# --- the whole's delete right is enough (DEC-2) ----------------------------------------------------
async def test_a_caller_with_delete_on_the_whole_only_deletes_it_and_its_parts(tree: Tree) -> None:
    target = str(graph_iri(tree.a1))
    await tree.grant(Grant(assignee=principal_of("dan"), target=target, action=Action.DELETE))

    answer = await tree.delete("dan", tree.a1, "audits")

    assert answer.status_code == 204, answer.text
    gone = [
        await tree.exists(tree.a1, "audits"),
        await tree.exists(tree.r1, "audit-results"),
        await tree.exists(tree.f1, "audit-findings"),
    ]
    assert gone == [False] * 3, "the whole and both levels of parts are gone"


# --- InUse never names a part the caller may not read (PD-10) --------------------------------------
@pytest.mark.parametrize("barred", [True, False], ids=["unreadable part", "readable part"])
async def test_a_cited_part_is_never_named_in_the_in_use_answer(tree: Tree, barred: bool) -> None:
    citing = await tree.cite(tree.f1)
    if barred:
        await tree.grant(bar=tree.bar_ada_from(tree.f1))

    answer = await tree.delete("ada", tree.a1, "audits")

    assert answer.status_code == 409, answer.text
    assert answer.json()["type"].endswith("in-use"), "the answer is an in-use problem"
    assert tree.f1 not in answer.text, "the refused part is not named, readable or not"
    assert citing in answer.text, "the readable referrer is"
    assert await tree.exists(tree.f1, "audit-findings"), "nothing was removed"


# --- a delete rule's message never names a part the caller may not read (A-6) ----------------------
@pytest.fixture
async def ruled() -> AsyncIterator[Tree]:
    """A tree on a service whose delete rule refuses every finding with a message naming it."""
    toy = ToyService(delete_validators={"AuditFinding": [refuse_finding]})
    async with toy.app.router.lifespan_context(toy.app), toy.client() as http:
        yield await Tree(await Scene.set_up(toy, http)).set_up()


@pytest.mark.parametrize("barred", [True, False], ids=["unreadable part", "readable part"])
async def test_a_refusing_rule_names_its_part_only_when_readable(ruled: Tree, barred: bool) -> None:
    if barred:
        await ruled.grant(bar=ruled.bar_ada_from(ruled.f1))

    answer = await ruled.delete("ada", ruled.a1, "audits")

    assert answer.status_code == 409, answer.text
    detail = answer.json().get("detail", "")
    assert (ruled.f1 in detail) is (not barred), "the part is named exactly when it may be read"
    assert barred is False or "a dependent part" in detail, "an unreadable part is called so"
    assert barred is False or ruled.a1 in detail, "and the whole is named instead"
    assert await ruled.exists(ruled.a1, "audits"), "all or nothing: the whole stays"
    assert await ruled.exists(ruled.f1, "audit-findings"), "all or nothing: the part stays"


# --- a follower hears the invalidation of the parts it may read only (PD-9, PD-10) -----------------
@pytest.fixture
async def streams() -> AsyncIterator[set[asyncio.Task]]:
    opened: set[asyncio.Task] = set()
    yield opened
    for task in opened:
        if not task.done():
            task.cancel()
    await asyncio.gather(*opened, return_exceptions=True)


@pytest.mark.parametrize(
    "hidden", ["audit-results", None], ids=["unreadable part", "readable part"]
)
async def test_a_follower_hears_the_removal_without_the_parts_it_may_not_read(
    tree: Tree, streams: set[asyncio.Task], hidden: str | None
) -> None:
    mount(tree.scene.service, "/fast")
    await tree.scene.service.kit.relay.run_once()
    await reshape_grants(tree.scene, with_carol(hide=tree.r1 if hidden else None))
    carol = opening(streams, tree.scene, "carol", events=1)
    await listening(tree.scene.service.kit.hub)

    answer = await tree.delete("ada", tree.a1, "audits")
    await tree.scene.service.kit.relay.run_once()

    assert answer.status_code == 204, answer.text
    [event] = (await carol).events
    heard = {i.entity for i in Remove.model_validate_json(event.data).invalidations or []}
    assert tree.a1 in heard, "the whole's invalidation is heard"
    assert (tree.r1 in heard) is (hidden is None), "R1's is heard exactly when it may be read"
    assert tree.f1 in heard, "F1 is readable and heard"
