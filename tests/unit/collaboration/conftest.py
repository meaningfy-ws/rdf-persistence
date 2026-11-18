"""The ``collaboration`` fixture; the toy library's documents and session are in ``tests/unit/conftest.py``."""

from collections.abc import Callable

import pytest

from rdf_persistence import CallerAccess, VerifiedCaller, generated_models
from rdf_persistence.access.services.access import AccessRules, load_role_definitions
from rdf_persistence.collaboration.services.collaboration import Collaboration
from rdf_persistence.iris.services.iris import DEFAULT_IRIS
from rdf_persistence.persistence.services.listing import Listings
from rdf_persistence.persistence.services.session import Session
from rdf_persistence.schema.services.schema import load_schema
from tests.toy import MODULES, ROLES, TOY_SCHEMA, toy_mapper


@pytest.fixture
def collaboration(toy_session: Session) -> Callable[..., Collaboration]:
    """Builds a ``Collaboration`` the way ``ServiceKit.collaboration`` does, for a caller and its access."""
    view = load_schema(TOY_SCHEMA)
    rules = AccessRules(load_role_definitions(ROLES))

    def build(
        who: VerifiedCaller, access: CallerAccess, session: Session | None = None
    ) -> Collaboration:
        return Collaboration(
            session or toy_session,
            view=view,
            rules=rules,
            iris=DEFAULT_IRIS,
            mapper=toy_mapper(),
            models=generated_models(*MODULES),
            listings=Listings(view),
            caller=who,
            access=access,
        )

    return build
