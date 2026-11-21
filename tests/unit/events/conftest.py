"""The relay tests' world: two tenants of the toy library and the application database, over the fakes."""

from types import SimpleNamespace

import pytest

from rdf_persistence import generated_models
from rdf_persistence.events.services.relay import Relay
from rdf_persistence.iris.services.iris import Iris
from rdf_persistence.testkit import InMemoryBroker, InMemoryEventBus
from tests.relay_helpers import CONTEXT, DEPLOYMENT, VIEW
from tests.tenancy_world import CREATOR, make_world
from tests.toy import MODULES, SETTINGS, library_slots, toy_mapper


@pytest.fixture
async def world() -> SimpleNamespace:
    made = await make_world(Iris(SETTINGS), SETTINGS)
    made.second = (await made.tenancy.create("Bruges", library_slots(), CREATOR)).id
    made.app_iri = str(made.iris.application)
    await made.tenancy.ensure_application_database()
    made.broker = InMemoryBroker()
    made.bus = InMemoryEventBus(made.broker)
    made.relay = lambda bus="default", hub=None, **kw: Relay(
        made.tenancy,
        VIEW,
        generated_models(*MODULES),
        toy_mapper(),
        made.bus if bus == "default" else bus,
        hub,
        deployment=DEPLOYMENT,
        context=CONTEXT,
        **kw,
    )
    await made.relay(None).run_once()  # the roots the tenants were created with are not under test
    return made
