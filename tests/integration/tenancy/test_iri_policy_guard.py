"""The policy guard against a real Fuseki: a restart with a changed policy fails."""

import pytest

from rdf_persistence.domain.exceptions import IriPolicyChanged
from rdf_persistence.domain.generated.service.rp_service import IdKind, IdSpec, IriPolicy
from rdf_persistence.services.iri_policy_guard import guard_iri_policy


async def test_a_restart_with_a_changed_policy_fails(tenancy, store, settings):
    first = settings.model_copy(
        update={"iri_policy": IriPolicy(object_id=IdSpec(kind=IdKind.RANDOM, length=13))}
    )
    await guard_iri_policy(store, tenancy, first)
    await guard_iri_policy(store, tenancy, first)
    changed = IriPolicy(object_id=IdSpec(kind=IdKind.RANDOM, length=12))
    with pytest.raises(IriPolicyChanged, match=r"object_id\.length"):
        await guard_iri_policy(store, tenancy, settings.model_copy(update={"iri_policy": changed}))
