"""The service reports grants at start-up, right after the shared databases are migrated (grant-roles D-5)."""

import logging

from rdf_persistence.access.services.generated.rp_access_services import GrantSet
from rdf_persistence.core.domain.generated.rp_core import Principal
from rdf_persistence.testkit import FakeStore
from tests.toy_service import TENANT_BODY, ToyService

UNADMINISTERED = "no grant administers the tenant"


class OrderedStore(FakeStore):
    """A fake store that notes its calls, and the report's warning, in one list in the order they came."""

    def __init__(self) -> None:
        super().__init__()
        self.events: list[tuple[str, str]] = []

    async def query(self, dataset, sparql):
        self.events.append(("query", dataset))
        return await super().query(dataset, sparql)

    async def drop_dataset(self, name):
        self.events.append(("drop_dataset", name))
        await super().drop_dataset(name)


class Noted(logging.Handler):
    def __init__(self, events: list[tuple[str, str]]) -> None:
        super().__init__(logging.WARNING)
        self.events = events

    def emit(self, record: logging.LogRecord) -> None:
        if record.getMessage() == UNADMINISTERED:
            self.events.append(("report", UNADMINISTERED))


async def test_start_up_reports_the_grants_after_the_shared_databases_and_before_the_sweep() -> (
    None
):
    store = OrderedStore()
    first = ToyService(store)
    async with first.app.router.lifespan_context(first.app), first.client() as http:
        created = await http.post("/libraries", json=TENANT_BODY, headers=first.bearer("ada"))
    tenant = first.kit.tenant_iri(created.headers["location"].rsplit("/", 1)[-1])
    _, version = await first.kit.tenancy.get(tenant)
    await first.kit.tenancy.set_grants(tenant, GrantSet(grants=[]), version, Principal(id="x"))
    orphan = "lib-t-" + "a" * 32  # the sweep drops it: its drop marks where the sweep ran
    await store.create_dataset(orphan)
    store.events.clear()
    toy = ToyService(store)
    application = toy.kit.tenancy.application_database
    handler = Noted(store.events)
    logging.getLogger("rdf_persistence").addHandler(handler)
    try:
        async with toy.app.router.lifespan_context(toy.app):
            pass
    finally:
        logging.getLogger("rdf_persistence").removeHandler(handler)

    events = store.events
    reported = events.index(("report", UNADMINISTERED))
    last_application = max(i for i, e in enumerate(events) if e == ("query", application))
    swept = events.index(("drop_dataset", orphan))
    assert last_application < reported, "the report follows the migration of the shared databases"
    assert reported < swept, "the report comes before the sweep"
