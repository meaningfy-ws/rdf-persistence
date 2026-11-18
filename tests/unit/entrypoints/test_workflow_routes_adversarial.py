"""The generic routes against the workflow (rp-workflow): they cannot set a state, make a transition or read one."""

import pytest
from rdflib import Graph, URIRef

from rdf_persistence import Action
from rdf_persistence.access.services.generated.rp_access_services import CallerAccess
from rdf_persistence.core.domain.generated.rp_access import Grant
from rdf_persistence.core.domain.generated.rp_tenancy import TenantState
from rdf_persistence.iris.services.generated.rp_iris_services import IriPolicy
from rdf_persistence.schema.services import vocabulary as v
from rdf_persistence.services.collaboration import Collaboration
from rdf_persistence.testkit import assert_isomorphic
from tests.toy import caller
from tests.toy_service import DUNE_BODY, ToyService, assert_problem, principal_of
from tests.unit.entrypoints.scene import PROBLEMS, Scene, problem_of
from tests.unit.services.collaboration_data import ACCEPTED, DRAFT, IN_REVIEW


@pytest.fixture
async def toy():
    service = ToyService()
    async with service.app.router.lifespan_context(service.app), service.client() as http:
        yield await Scene.set_up(service, http)


# Class: a state the generic put may not set. A near-miss IRI is refused 403 by the guard; a bare name
# is a relative IRI, which the one JSON-LD path refuses first (PD-6, D-10).
API_STATES = [
    ("accepted", 422, "invalid-body"),
    (DRAFT.replace("https:", "http:"), 403, "forbidden"),
]


@pytest.mark.parametrize(("state", "status", "problem"), API_STATES)
async def test_the_generic_put_cannot_set_a_state(toy, state, status, problem):
    scene = toy
    response = await scene.http.put(
        scene.book,
        json={**DUNE_BODY, "workflow_status": state},
        headers=scene.headers("ada", **{"If-Match": scene.book_etag}),
    )
    assert_problem(response, status, problem)
    stored = await scene.http.get(scene.book, headers=scene.headers("ada"))
    assert (stored.json()["workflow_status"], stored.headers["etag"]) == (DRAFT, scene.book_etag), (
        "the book is in draft and unchanged"
    )


# Class: a type the generic put cannot change; one per refusal ("cannot be typed", "has no field").
@pytest.mark.parametrize("extra", [{"type": "Shelf"}, {"rdf:type": "x"}])
async def test_the_generic_put_cannot_change_the_type_of_a_book(toy, extra):
    scene = toy
    response = await scene.http.put(
        scene.book,
        json={**DUNE_BODY, "workflow_status": ACCEPTED, **extra},
        headers=scene.headers("ada", **{"If-Match": scene.book_etag}),
    )
    assert_problem(response, 422, "invalid-body")
    stored = await scene.http.get(scene.book, headers=scene.headers("ada"))
    assert stored.json()["workflow_status"] == DRAFT, "the book is in draft"


async def test_the_generic_put_of_a_body_read_before_a_transition_is_a_409(toy):
    scene = toy
    tenant_id = scene.tenant.rsplit("/", 1)[1]
    authorised = await scene.service.kit.require(
        scene.headers("ada")["Authorization"], tenant_id, Action.READ
    )
    async with scene.service.kit.collaboration(authorised) as collaboration:
        await collaboration.transition(
            scene.book_iri, "in_review", if_version=scene.book_etag.strip('"')
        )
    response = await scene.http.put(
        scene.book,
        json={**DUNE_BODY, "workflow_status": DRAFT},
        headers=scene.headers("ada", **{"If-Match": scene.book_etag}),
    )
    assert_problem(response, 409, "conflict")
    stored = await scene.http.get(scene.book, headers=scene.headers("ada"))
    assert stored.json()["workflow_status"] == IN_REVIEW, "the book is where the transition left it"


async def test_the_generic_post_cannot_create_a_book_with_two_states(toy):
    scene = toy
    listed = f"{scene.tenant}/books"
    total = (await scene.http.get(listed, headers=scene.headers("ada"))).json()["total"]
    response = await scene.http.post(
        listed,
        json={**DUNE_BODY, "workflow_status": [DRAFT, ACCEPTED]},
        headers=scene.headers("ada"),
    )
    assert_problem(response, 422, "invalid-body")
    after = (await scene.http.get(listed, headers=scene.headers("ada"))).json()["total"]
    assert after == total, "nothing was stored"


@pytest.mark.parametrize("policy", ["default", "flat"])
async def test_no_generic_route_reads_replaces_or_deletes_a_transition(policy):
    flat = IriPolicy(aggregate_template="{tenant}/{id}") if policy == "flat" else None
    service = ToyService(iri_policy=flat)
    async with service.app.router.lifespan_context(service.app), service.client() as http:
        scene = await Scene.set_up(service, http)
        record, stored = await a_record(service, scene)
        headers = {**scene.headers("ada"), "If-Match": '"any"'}
        responses = [
            await http.get(f"{scene.tenant}/{path}/{record}", headers=scene.headers("ada"))
            for path in ("books", "shelves", "rp-transitions")
        ]
        responses += [
            await http.put(f"{scene.tenant}/books/{record}", json=DUNE_BODY, headers=headers),
            await http.delete(f"{scene.tenant}/books/{record}", headers=headers),
        ]
        answers = [(r.status_code, problem_of(r).type) for r in responses]
        assert answers == [(404, f"{PROBLEMS}not-found")] * 5, f"every route answers 404: {answers}"
        async with service.kit.session(scene.tenant_iri, principal_of("ada")) as session:
            kept = await session.activities(v.TRANSITION, v.USED, URIRef(scene.book_iri))
        assert_isomorphic(kept[scene.record_iri], stored)


async def a_record(service: ToyService, scene: Scene) -> tuple[str, Graph]:
    """One move of the scene's book made the way the kit makes it: ``(the transition's id in a path, its stored graph)``."""
    kit, who = service.kit, principal_of("ada")
    grant = Grant(assignee=who, target=scene.tenant_iri, role="librarian")
    access = CallerAccess(tenant=scene.tenant_iri, state=TenantState.ACTIVE, grants=[grant])
    async with kit.session(scene.tenant_iri, who) as session:
        moves = Collaboration(
            session,
            view=kit.view,
            rules=kit.rules,
            iris=kit.iris,
            mapper=kit.mapper,
            models=kit.models,
            listings=kit.listings,
            workflows=kit.workflows,
            caller=caller(principal=who),
            access=access,
        )
        await moves.transition(
            scene.book_iri, "in_review", if_version=(await session.get_graph(scene.book_iri))[2]
        )
        [record] = await moves.transitions(scene.book_iri)
        scene.record_iri = record.id
        stored = (await session.activities(v.TRANSITION, v.USED, URIRef(scene.book_iri)))[record.id]
        return record.id.removeprefix("urn:uuid:"), stored


async def test_the_generic_delete_of_a_book_keeps_its_transitions_and_removes_its_comments(toy):
    scene = toy
    await a_record(scene.service, scene)
    gone = await scene.http.delete(
        scene.book,
        headers=scene.headers(
            "ada",
            **{
                "If-Match": (
                    await scene.http.get(scene.book, headers=scene.headers("ada"))
                ).headers["etag"]
            },
        ),
    )
    assert gone.status_code == 204, gone.text
    async with scene.service.kit.session(scene.tenant_iri, principal_of("ada")) as session:
        kept = await session.activities(v.TRANSITION, v.USED, URIRef(scene.book_iri))
        assert list(kept) == [scene.record_iri], "the transition is kept"
        assert await session.graphs_with(v.HAS_TARGET, URIRef(scene.book_iri)) == {}, "no comment"
