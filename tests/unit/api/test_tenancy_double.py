"""The tenancy double of the api tests takes what ``Tenancy.tenant_session`` takes (review-floors PD-22)."""

import inspect

from rdf_persistence.tenancy.services.tenancy import Tenancy
from tests.unit.api.iri_policy_helpers import TenancyDouble


def shape(function) -> list[tuple[str, object, object]]:
    """Name, kind and default of each parameter, ``self`` included on both sides."""
    return [(p.name, p.kind, p.default) for p in inspect.signature(function).parameters.values()]


def test_the_tenancy_double_takes_what_tenant_session_takes():
    real, double = shape(Tenancy.tenant_session), shape(TenancyDouble.tenant_session)
    missing = [name for name, _, _ in real if name not in {n for n, _, _ in double}]
    assert not missing, f"the double lacks the parameter(s) {missing} of Tenancy.tenant_session"
    assert double == real, "the double's parameters (names, kinds, defaults) equal the real ones"
