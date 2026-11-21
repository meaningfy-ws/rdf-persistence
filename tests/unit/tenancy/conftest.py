"""The fixtures that several tests of the tenancy theme share."""

from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from rdf_persistence.iris.services.iris import Iris
from rdf_persistence.migrations.services.migrations import Chain, SchemaChain
from rdf_persistence.tenancy.services.tenancy import Tenancy
from tests.dump_helpers import (
    BOOK_DESCRIPTION,
    CITY,
    LIBRARY_SCHEMA,
    OLD_CITY,
    OLD_DESCRIPTION,
    STAMPS,
    TOOLKIT_SCHEMA,
    TOOLKIT_VERSION,
    iris_of,
    make_world,
    move_predicate,
    populated,
)
from tests.fixtures.library.domain.generated.library import Library
from tests.fixtures.library.domain.generated.library_access import LibraryAccess
from tests.migration_helpers import (
    ISBN,
    LIB,
    MID_ISBN,
    OLD_ISBN,
    RP,
    chain_of,
    migration,
    rename,
)
from tests.tenancy_world import HOUR, book
from tests.tenancy_world import make_world as sweep_world
from tests.toy import SETTINGS, toy_mapper


@pytest.fixture
async def world() -> SimpleNamespace:
    """The worked example: B+G1 committed, G2 old and uncommitted, G3 young, S+k1, k2 old, k3 young."""
    made = await sweep_world(Iris(SETTINGS), SETTINGS)
    made.book, made.scan = book(made, 1), book(made, 2, "scans")
    made.g1 = await made.load(made.book, 3 * HOUR)
    await made.commit(made.book, [made.g1])
    made.g2 = await made.load(made.book, 2 * HOUR)
    made.g3 = await made.load(made.book, timedelta(minutes=5))
    await made.commit(made.scan, keys=["k1"])
    await made.blob("k1", 3 * HOUR)
    await made.blob("k2", 3 * HOUR)
    await made.blob("k3", timedelta(minutes=1))
    return made


@pytest.fixture
def lib_chain(tmp_path: Path) -> Chain:
    """``[1, 2]``: version 2 moves the ISBN from its old predicate to the book's."""
    step = migration(LIB, "1", "2", rename(OLD_ISBN, ISBN))
    return chain_of(tmp_path / "lib", LIB, step, current="2")


@pytest.fixture
def three(tmp_path: Path) -> Chain:
    """``[1, 2, 3]``: the ISBN goes old, then middle, then the book's predicate."""
    steps = (
        migration(LIB, "1", "2", rename(OLD_ISBN, MID_ISBN)),
        migration(LIB, "2", "3", rename(MID_ISBN, ISBN)),
    )
    return chain_of(tmp_path / "three", LIB, *steps, current="3")


@pytest.fixture
def toolkit_chain(tmp_path: Path) -> Chain:
    return chain_of(tmp_path / "rp", RP, current="1")


@pytest.fixture
async def stamped() -> SimpleNamespace:
    return await populated(await make_world(iris_of(SETTINGS), SETTINGS, stamps=STAMPS))


@pytest.fixture
def chains(tmp_path: Path) -> list[SchemaChain]:
    """The toolkit's chain ``[1]`` and the library's ``[1, 2]``: ``1__2`` moves a book's description and the root's city."""
    steps = [
        rename(OLD_DESCRIPTION, BOOK_DESCRIPTION),
        rename(OLD_CITY, CITY),
    ]
    return [
        (TOOLKIT_SCHEMA, chain_of(tmp_path / "rp", TOOLKIT_SCHEMA, current=TOOLKIT_VERSION)),
        (
            LIBRARY_SCHEMA,
            chain_of(
                tmp_path / "lib",
                LIBRARY_SCHEMA,
                migration(LIBRARY_SCHEMA, "1", "2", *steps),
                current="2",
            ),
        ),
    ]


@pytest.fixture
async def aged() -> SimpleNamespace:
    """A tenant stamped ``1`` whose book and root hold their description and city as version 1 stored them."""
    world = await populated(
        await make_world(
            iris_of(SETTINGS),
            SETTINGS,
            stamps=((TOOLKIT_SCHEMA, TOOLKIT_VERSION), (LIBRARY_SCHEMA, "1")),
        )
    )
    await move_predicate(world, world.book, BOOK_DESCRIPTION, OLD_DESCRIPTION)
    await move_predicate(world, world.tenant, CITY, OLD_CITY)
    world.running = Tenancy(
        world.store, world.files, SETTINGS, mapper=toy_mapper(), root_class=Library,
        access_class=LibraryAccess, iris=world.iris, stamps=STAMPS,
    )  # fmt: skip
    return world
