"""The helpers the tenancy tests share: a tenancy over the fakes that draws chosen ids, and the activity plumbing.

The tenant, tenant-store, redraw and relay tests use them, so they sit beside the tenancy tests
(a helper used by more than one module of a theme goes beside them).
"""

from types import SimpleNamespace
from uuid import UUID

from rdf_persistence.iris.domain.layout import system_database_name
from rdf_persistence.iris.services.iris import Iris
from rdf_persistence.schema.services import vocabulary as v
from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence.schema.services.schema_structure import iri_types
from rdf_persistence.tenancy.services.tenancy import Tenancy
from rdf_persistence.testkit import FakeFileStore, FakeStore
from tests.dump_helpers import LIBRARY_SCHEMA
from tests.fixtures.library.domain.generated.library import Library
from tests.fixtures.library.domain.generated.library_access import LibraryAccess
from tests.tenancy_world import CREATOR
from tests.toy import SETTINGS, TOY_SCHEMA, library_slots, toy_mapper, toy_rules
from tests.unit.activity_helpers import B1, book

SYSTEM = system_database_name(SETTINGS.prefix)
PREFIX = "lib-t-"
CLIENT_A = "client-a"
IDS = [str(UUID(int=n)) for n in (1, 2, 3)]
TYPES = iri_types(load_schema(TOY_SCHEMA))
PLUMBING = (v.PENDING_SINCE, v.RELAYED_AT, v.PUBLICATION_FAILED)


def drawing(*ids: str):
    """An id source that answers ``ids`` in turn and fails if asked for more."""
    drawn = iter(ids)
    return lambda spec: next(drawn)


def tenancy_drawing(store, files, *ids: str) -> Tenancy:
    return Tenancy(
        store,
        files,
        SETTINGS,
        mapper=toy_mapper(),
        root_class=Library,
        access_class=LibraryAccess,
        rules=toy_rules(),
        iris=Iris(SETTINGS, id_source=drawing(*ids)),
    )


def wired(d: FakeStore, files: FakeFileStore, *ids: str, **stores: FakeStore) -> Tenancy:
    """A tenancy on ``d`` with ``stores`` beside it; ``ids`` are the tenant ids it draws, in turn."""
    iris = Iris(SETTINGS, *TYPES, id_source=drawing(*ids))
    return Tenancy(
        d,
        files,
        SETTINGS,
        mapper=toy_mapper(),
        root_class=Library,
        access_class=LibraryAccess,
        rules=toy_rules(),
        iris=iris,
        stamps=[(LIBRARY_SCHEMA, "1")],
        stores=stores,
    )


def cold(world: SimpleNamespace, **stores: FakeStore) -> Tenancy:
    """Another instance over the same stores: it has read nothing yet."""
    return wired(world.d, world.files, **stores)


def operations(store: FakeStore) -> int:
    return sum(len(store.sent(operation)) for operation in FakeStore.OPERATIONS)


def tenant_databases(store: FakeStore) -> list[str]:
    return [name for name in store._datasets if name.startswith(PREFIX)]


async def made_on(world: SimpleNamespace, store: str | None = None) -> str:
    kwargs = {} if store is None else {"store": store}
    return (await world.tenancy.create("Ghent", library_slots(), CREATOR, **kwargs)).id


async def three_commits(session) -> None:
    version = await session.add_graph(B1, book(B1))
    version = await session.replace_graph(B1, book(B1), version)
    await session.remove(B1, version)
