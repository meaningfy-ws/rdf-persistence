"""The shared service view is never modified by a kit in use (test-memory-followups PD-3, DEC-2).

A fingerprint of the view (its ``modifications`` count and a hash of every module of its closure) and a
hash of every induced slot are taken before and after the toy service's whole scene; a kit that edited
the view it shares would change one of them for every other kit built from the file.
"""

import asyncio
import hashlib
import io
from collections.abc import AsyncIterator

import pytest
from linkml_runtime.dumpers import yaml_dumper
from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence.access.domain.generated.rp_access import Action
from rdf_persistence.provenance.domain.generated.rp_provenance import Replace
from rdf_persistence.schema.services.schema import clear_service_views, load_schema
from tests.events_follow import FOLLOW_TIMEOUT, listening, mount, opening, replace
from tests.scene import Scene
from tests.toy import TOY_SCHEMA
from tests.toy_service import DUNE_BODY, ToyService


def fingerprint(view: SchemaView) -> tuple[int, str]:
    """``view.modifications`` and a sha256 over the YAML of every module of the closure, in key order."""
    view.imports_closure()
    digest = hashlib.sha256()
    for key in sorted(view.schema_map):
        digest.update(key.encode())
        digest.update(yaml_dumper.dumps(view.schema_map[key]).encode())
    return view.modifications, digest.hexdigest()


def induced_slots_digest(view: SchemaView) -> str:
    """A sha256 over the YAML of every induced slot of every class, computed now (not cached)."""
    digest = hashlib.sha256()
    for name in sorted(view.all_classes()):
        for slot in view.class_induced_slots(name):
            digest.update(f"{name}.".encode())
            digest.update(yaml_dumper.dumps(slot).encode())
    return digest.hexdigest()


@pytest.fixture(autouse=True)
def _own_views() -> None:
    clear_service_views()
    yield
    clear_service_views()


@pytest.fixture
async def streams() -> AsyncIterator[set[asyncio.Task]]:
    opened: set[asyncio.Task] = set()
    yield opened
    for task in opened:
        if not task.done():
            task.cancel()
    await asyncio.gather(*opened, return_exceptions=True)


async def drive_the_scene(scene: Scene, streams: set[asyncio.Task]) -> None:
    """Create (the scene made a tenant and a book), read, list, replace, a transition, delete, dump, restore, hear an event."""
    kit, http = scene.service.kit, scene.http
    ada = scene.headers("ada")
    prefix = mount(scene.service, "/fast")
    await kit.relay.run_once()
    follower = opening(streams, scene, "rita", prefix, events=1)
    await listening(kit.hub)
    assert (await http.get(scene.book, headers=ada)).status_code == 200, "read"
    listed = await http.get(f"{scene.tenant}/books", headers=ada)
    assert listed.status_code == 200, "list"
    await replace(scene, scene.book, scene.book_etag, "Dune Messiah")  # replace, then the event
    [event] = (await asyncio.wait_for(follower, FOLLOW_TIMEOUT)).events
    assert Replace.model_validate_json(event.data).id == event.id, "the event decodes by its class"
    authorised = await kit.require(
        ada["Authorization"], scene.tenant.rsplit("/", 1)[1], Action.READ
    )
    async with kit.collaboration(authorised) as collaboration:
        stored = await http.get(scene.book, headers=ada)
        await collaboration.transition(
            scene.book_iri, "in_review", if_version=stored.headers["etag"].strip('"')
        )
    other = await http.post(f"{scene.tenant}/books", json=DUNE_BODY, headers=ada)
    assert other.status_code == 201, "create"
    deleted = await http.delete(
        other.headers["location"], headers={**ada, "If-Match": other.headers["etag"]}
    )
    assert deleted.status_code == 204, "delete"
    archive = io.BytesIO()
    await kit.dump_tenant(kit.tenant_iri(scene.tenant.rsplit("/", 1)[1]), archive)
    await kit.restore_tenant(io.BytesIO(archive.getvalue()), "https://example.org/people/bob")


async def test_a_kit_in_use_leaves_the_view_it_shares_as_it_found_it(
    service: ToyService, scene: Scene, streams: set[asyncio.Task]
) -> None:
    view = service.kit.view  # the service fixture ran the start-up migrations in its lifespan
    other = ToyService().kit.view
    assert other is view, "the kits of one file share a view (the guard guards a shared object)"
    before, slots_before = fingerprint(view), induced_slots_digest(view)

    await drive_the_scene(scene, streams)

    assert fingerprint(view) == before, "no kit modified a module of the shared view"
    assert induced_slots_digest(view) == slots_before, "no induced slot of the view was edited"


def test_the_fingerprint_sees_an_edit_of_a_module_and_of_an_induced_slot() -> None:
    view = load_schema(TOY_SCHEMA)
    before, slots_before = fingerprint(view), induced_slots_digest(view)
    assert fingerprint(load_schema(TOY_SCHEMA)) == before, "the same file fingerprints the same"

    view.get_class("Book").description = "edited"
    assert fingerprint(view) != before, "an edit to a module changes the fingerprint"

    slot = view.class_induced_slots("Book")[0]
    slot.description = "edited"
    assert induced_slots_digest(view) != slots_before, (
        "an edit to an induced slot changes its digest"
    )
