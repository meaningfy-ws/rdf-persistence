"""The release of assignees who lose read access, through the grants route (workflow-assignees D-6, T14)."""

import logging
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
import yaml
from rdflib import URIRef

from rdf_persistence import Action, Grant, GrantSet, InvalidBody
from rdf_persistence.access.domain.generated.rp_access import Prohibition
from rdf_persistence.collaboration.domain.generated.rp_workflow import Assignment
from rdf_persistence.collaboration.services.aggregate_validators import AggregateReader
from rdf_persistence.collaboration.services.workflows import load_workflow
from rdf_persistence.core.domain.media import JSON
from rdf_persistence.schema.services import vocabulary as v
from tests.scene import Scene
from tests.toy import REVIEW_WORKFLOW, caller, graph_of
from tests.toy_service import ADA, DUNE_BODY, RITA, ToyService, principal_of
from tests.unit.collaboration.assignees_world import assignees_of

MIA = "mia"
SHELF_BODY = {"label": "Shelf", "description": "A shelf.", "member_class": "Book"}
REFUSED_LABEL = "Refused"
ARMED: list[bool] = []  # the validator refuses only once the test has set the world up


def refuses_a_marked_book(old: Any, new: Any, who: Any, reader: AggregateReader) -> None:
    if ARMED and new.label == REFUSED_LABEL:
        raise InvalidBody("this book may not be stored")


def assignable_workflow(folder: Path) -> Path:
    """The review workflow, assignable, written into ``folder``: the toy roles define no ``reviewer``."""
    path = folder / "assignable.workflow.yaml"
    review = load_workflow(REVIEW_WORKFLOW).model_copy(update={"assignable": True})
    path.write_text(
        yaml.safe_dump(review.model_dump(mode="json", exclude_none=True)), encoding="utf-8"
    )
    return path


@asynccontextmanager
async def scene_with(folder: Path, *, validate: bool = False) -> AsyncIterator[Scene]:
    ARMED.clear()
    toy = ToyService(
        workflows=(assignable_workflow(folder),),
        aggregate_validators={"Book": [refuses_a_marked_book]} if validate else {},
    )
    async with toy.app.router.lifespan_context(toy.app), toy.client() as http:
        yield await Scene.set_up(toy, http)


def reader(scene: Scene, sub: str) -> Grant:
    return Grant(assignee=principal_of(sub), target=scene.tenant_iri, role="reader")


def librarian(scene: Scene) -> Grant:
    return Grant(assignee=principal_of(ADA), target=scene.tenant_iri, role="librarian")


async def put_grants(scene: Scene, grants: Sequence[Grant], *bans: Prohibition) -> Any:
    held = await scene.http.get(f"{scene.tenant}/grants", headers=scene.headers(ADA))
    response = await scene.http.put(
        f"{scene.tenant}/grants",
        content=GrantSet(grants=list(grants), prohibitions=list(bans) or None).model_dump_json(
            exclude_none=True
        ),
        headers=scene.headers(ADA, **{"If-Match": held.headers["etag"], "Content-Type": JSON}),
    )
    scene.access_etag = response.headers.get("etag", scene.access_etag)
    return response


async def a_book(scene: Scene, label: str = "Dune") -> str:
    made = await scene.http.post(
        f"{scene.tenant}/books", json={**DUNE_BODY, "label": label}, headers=scene.headers(ADA)
    )
    assert made.status_code == 201, made.text
    return made.json()["id"]


async def assigned(scene: Scene, iri: str, *subs: str) -> None:
    """Store ``iri`` assigned to ``subs`` as a past assignment left it (the guard allows exactly these)."""
    wanted = frozenset(principal_of(s) for s in subs)
    async with scene.service.kit.session(scene.tenant_iri, ADA) as session:
        graph, _, version = await session.get_graph(iri)
        triples = [t for t in graph if t[1] != v.WORKFLOW_ASSIGNEES]
        triples += [(URIRef(iri), v.WORKFLOW_ASSIGNEES, URIRef(p)) for p in sorted(wanted)]
        async with session.transaction() as transaction:
            transaction._allow_assignees(iri, wanted)
            await transaction.replace_graph(iri, triples, version)


async def assignees(scene: Scene, iri: str) -> frozenset[str]:
    async with scene.service.kit.session(scene.tenant_iri, ADA) as session:
        return await assignees_of(session, iri)


async def changes(scene: Scene, iri: str) -> list[Assignment]:
    headers = scene.headers(ADA)
    authorised = await scene.service.kit.require(
        headers["Authorization"], scene.tenant_iri.rsplit("/", 1)[1], Action.READ
    )
    async with scene.service.kit.collaboration(authorised) as collaboration:
        return await collaboration.assignments(iri)


def principals(*subs: str) -> frozenset[str]:
    return frozenset(principal_of(s) for s in subs)


def kept_by_an_aggregate_grant(scene: Scene, iri: str) -> list[Any]:
    return [Grant(assignee=principal_of(MIA), target=graph_of(iri), action=Action.READ)]


# (name, who stays assigned, what the new grants and prohibitions are)
LEAVES = [
    ("a member leaves", principals(RITA), "without-mia"),
    ("nobody leaves", principals(RITA, MIA), "same"),
    ("a prohibition takes the reading", principals(RITA), "ban-mia"),
    ("access kept by an aggregate grant", principals(RITA, MIA), "aggregate-grant"),
]


@pytest.mark.parametrize(("name", "stays", "change"), LEAVES, ids=[c[0] for c in LEAVES])
async def test_an_assignee_who_may_no_longer_read_is_released(
    tmp_path, name: str, stays: frozenset[str], change: str
) -> None:
    async with scene_with(tmp_path) as scene:
        book = await a_book(scene)
        everyone = [librarian(scene), reader(scene, RITA), reader(scene, MIA)]
        assert (await put_grants(scene, everyone)).status_code == 200
        await assigned(scene, book, RITA, MIA)
        bans: list[Prohibition] = []
        grants = {
            "without-mia": [librarian(scene), reader(scene, RITA)],
            "same": everyone,
            "ban-mia": everyone,
            "aggregate-grant": [
                librarian(scene),
                reader(scene, RITA),
                *kept_by_an_aggregate_grant(scene, book),
            ],
        }[change]
        if change == "ban-mia":
            bans = [
                Prohibition(assignee=principal_of(MIA), target=scene.tenant_iri, action=Action.READ)
            ]

        response = await put_grants(scene, grants, *bans)

        assert response.status_code == 200, response.text
        assert await assignees(scene, book) == stays, f"{name}: who is still assigned"
        released = principals(RITA, MIA) - stays
        records = await changes(scene, book)
        assert [set(r.released_principals or []) for r in records] == (
            [released] if released else []
        ), f"{name}: the Assignment lists who was released"
        assert [r.was_associated_with for r in records] == (
            [[principal_of(ADA)]] if released else []
        ), f"{name}: the administrator who changed the grants is the agent"


async def test_running_the_release_again_changes_nothing(tmp_path) -> None:
    async with scene_with(tmp_path) as scene:
        book = await a_book(scene)
        await put_grants(scene, [librarian(scene), reader(scene, RITA), reader(scene, MIA)])
        await assigned(scene, book, RITA, MIA)
        await put_grants(scene, [librarian(scene), reader(scene, RITA)])
        async with scene.service.kit.session(scene.tenant_iri, ADA) as session:
            before = (await session.get_graph(book))[2]
        count = len(await changes(scene, book))

        await scene.service.kit.release_assignees(
            scene.tenant_iri, caller(principal=principal_of(ADA))
        )

        async with scene.service.kit.session(scene.tenant_iri, ADA) as session:
            assert (await session.get_graph(book))[2] == before, (
                "the aggregate was not stored again"
            )
        assert len(await changes(scene, book)) == count, "no new Assignment"


async def test_a_failing_release_still_answers_200_with_the_new_grants(
    tmp_path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    async with scene_with(tmp_path) as scene:

        async def broken(tenant: str, caller: Any) -> None:
            raise RuntimeError("the store went away")

        monkeypatch.setattr(scene.service.kit, "release_assignees", broken)  # X3
        with caplog.at_level(logging.WARNING):
            response = await put_grants(scene, [librarian(scene)])
        assert response.status_code == 200, response.text
        held = await scene.http.get(f"{scene.tenant}/grants", headers=scene.headers(ADA))
        assert [g.assignee for g in GrantSet.model_validate(held.json()).grants or []] == [
            principal_of(ADA)
        ], "the grants changed"
        steps = [r.__dict__.get("rp.step") for r in caplog.records]
        assert steps == ["release-assignees-after-grants"], "one warning says the release failed"
        assert caplog.records[0].exc_info is not None, "with the error's traceback"


async def test_a_root_the_validator_refuses_does_not_stop_the_others(
    tmp_path, caplog: pytest.LogCaptureFixture
) -> None:
    async with scene_with(tmp_path, validate=True) as scene:
        refused, fine = await a_book(scene, REFUSED_LABEL), await a_book(scene, "Fine")
        everyone = [librarian(scene), reader(scene, RITA), reader(scene, MIA)]
        await put_grants(scene, everyone)
        for iri in (refused, fine):
            await assigned(scene, iri, RITA, MIA)
        ARMED.append(True)

        with caplog.at_level(logging.WARNING):
            response = await put_grants(scene, [librarian(scene), reader(scene, RITA)])

        assert response.status_code == 200, response.text
        assert await assignees(scene, fine) == principals(RITA), "the other root was released"
        assert await assignees(scene, refused) == principals(RITA, MIA), "the refused root stays"
        warned = [r for r in caplog.records if r.__dict__.get("rp.step") == "release-assignees"]
        assert [r.__dict__.get("rp.resource") for r in warned] == [refused], "the root is named"


async def test_a_root_of_no_workflow_class_is_left_alone(tmp_path) -> None:
    async with scene_with(tmp_path) as scene:
        made = await scene.http.post(
            f"{scene.tenant}/shelves", json=SHELF_BODY, headers=scene.headers(ADA)
        )
        shelf = made.json()["id"]
        await put_grants(scene, [librarian(scene), reader(scene, RITA), reader(scene, MIA)])
        await assigned(scene, shelf, RITA, MIA)

        response = await put_grants(scene, [librarian(scene), reader(scene, RITA)])

        assert response.status_code == 200, response.text
        assert await assignees(scene, shelf) == principals(RITA, MIA), "no workflow, no release"
