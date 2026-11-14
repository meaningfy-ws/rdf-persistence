"""The kit's door to application data and the start-up that creates its database (app-level-data PD-8, PD-9, PD-10; TC-43 to TC-47).

``A`` is the application IRI, ``T`` the scene's tenant, ``Tpl`` a ``Template`` (application class), ``B`` a ``Book`` (tenant class).
"""

import pytest

from rdf_persistence import Action
from rdf_persistence.domain.exceptions import Forbidden, InvalidIri, InvalidToken
from rdf_persistence.domain.generated.rp_tenancy import TenantState
from rdf_persistence.domain.iris import application_database_name
from rdf_persistence.testkit import FakeStore
from tests.fixtures.library.generated.books import Book
from tests.fixtures.library.generated.templates import Template
from tests.toy import SETTINGS
from tests.toy_service import ToyService, principal_of
from tests.unit.entrypoints.scene import Scene

APP_DATABASE = application_database_name(SETTINGS.prefix)


def application_of(kit) -> str:
    return str(kit.iris.application)


def calls_to(store: FakeStore) -> dict[str, int]:
    return {operation: len(store.sent(operation)) for operation in sorted(FakeStore.OPERATIONS)}


# -- TC-43 to TC-45: require_application ----------------------------------------------------------


async def test_tc43_a_tenant_owner_without_a_global_role_is_forbidden_and_no_store_call_is_made(
    scene: Scene,
) -> None:
    store = scene.service.store
    before = calls_to(store)
    with pytest.raises(Forbidden):
        await scene.service.kit.require_application(
            scene.headers("ada")["Authorization"], Action.MODIFY
        )
    assert calls_to(store) == before, "the check reads no grant and calls no store"


async def test_tc44_a_caller_with_a_global_role_gets_the_application_as_target_and_no_grants(
    scene: Scene,
) -> None:
    kit = scene.service.kit
    header = scene.headers("eve", "app-editor")["Authorization"]
    access = await kit.require_application(header, Action.MODIFY)
    assert access.checked_target == application_of(kit), "the target is the application"
    assert access.caller_access.tenant == application_of(kit), "and so is its tenant"
    assert access.caller_access.state == TenantState.ACTIVE, "an application is always active"
    assert not access.caller_access.grants, "no grant is read"
    assert not access.caller_access.prohibitions, "no prohibition is read"
    assert access.principal == principal_of("eve"), "the caller, for a domain service"


@pytest.mark.parametrize(
    "header",
    [None, "Basic YWRhOnB3", "Bearer not-a-token"],
    ids=["no header", "not a bearer", "a refused token"],
)
async def test_tc45_a_request_without_a_valid_token_is_an_invalid_token(
    scene: Scene, header: str | None
) -> None:
    with pytest.raises(InvalidToken):
        await scene.service.kit.require_application(header, Action.READ)


async def test_an_application_session_of_the_kit_reads_the_application_database(
    scene: Scene,
) -> None:
    async with scene.service.kit.application_session(principal_of("eve")) as session:
        assert await session.find(Template) == [], "the application database starts empty"


# -- TC-46: application_iri -----------------------------------------------------------------------


async def test_tc46_an_application_class_gets_an_application_aggregate_iri(
    service: ToyService,
) -> None:
    kit = service.kit
    iri = kit.application_iri(Template)
    assert kit.iris.is_aggregate(application_of(kit), iri), "A accepts it as its aggregate"
    assert kit.application_iri(Template) != iri, "each call mints a new one"


async def test_tc46_a_tenant_class_is_refused(service: ToyService) -> None:
    with pytest.raises(InvalidIri, match="Book is not an application class"):
        service.kit.application_iri(Book)


# -- TC-47: the start-up creates the application database -----------------------------------------


async def test_tc47_the_lifespan_creates_the_application_database_and_a_second_start_changes_nothing(
    service: ToyService,
) -> None:
    store = service.store
    assert {"lib-system", APP_DATABASE} <= set(await store.list_datasets()), "both exist"
    first = sorted(await store.list_datasets())
    created = len(store.sent("create_dataset"))
    async with service.app.router.lifespan_context(service.app):
        pass
    assert sorted(await store.list_datasets()) == first, "the same databases"
    assert len(store.sent("create_dataset")) == created, "none was created again"
