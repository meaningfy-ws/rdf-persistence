# Acceptance — iri-policy (#26)

**Verdict: accepted** by the developer, 2026-11-08 ("looks fine to me"), after PRs #35 and #36
merged into `develop`.

The demo runs the consumer's policy from #26 (7-character tenant ids, 13-character object ids,
flat IRIs with the class as `{type}`, access record and principal under `{deployment}`) over the
in-memory fakes: the guard on first start, the IRIs minted, a restart with an equal policy, a
restart with a changed policy, and a policy whose graphs collide. The real restart against Fuseki
is the container test `tests/integration/tenancy/test_iri_policy_guard.py`.

## The script

```python
"""Acceptance demo for iri-policy (#26): the consumer's policy, over the in-memory fakes."""

import asyncio

from rdf_persistence.domain.exceptions import InvalidIri, IriPolicyChanged
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.service.rp_service import IdKind, IdSpec, IriPolicy, ServiceSettings
from rdf_persistence.domain.iris import Iris
from rdf_persistence.services.iri_policy_guard import guard_iri_policy
from rdf_persistence.services.tenancy import Tenancy
from rdf_persistence.testkit import FakeFileStore, FakeStore
from tests.fixtures.library.generated.library import Library
from tests.fixtures.library.generated.library_access import LibraryAccess
from tests.toy import ADA, library_slots, toy_mapper

FLAT = "{base}{tenant_id}/{type}/{id}"
POLICY = IriPolicy(
    tenant_template="{base}project/{tenant_id}",
    aggregate_template=FLAT, part_template=FLAT, loaded_graph_template=FLAT,
    access_template="{base}{deployment}/project/{tenant_id}",
    principal_template="{base}{deployment}/user/{sub}",
    tenant_id=IdSpec(kind=IdKind.RANDOM, length=7),
    object_id=IdSpec(kind=IdKind.RANDOM, length=13),
)
SETTINGS = ServiceSettings(
    base="http://mwb.meaningfy.ws/", prefix="mwb", tenant_segment="projects",
    creator_role="librarian", roles_claim="roles", deployment="dev", iri_policy=POLICY,
)


def show(label, value):
    print(f"  {label:<28} {value}")


async def main():
    store, iris = FakeStore(), Iris(SETTINGS, root_types=frozenset({"book"}), owned_types=frozenset({"chapter"}))
    tenancy = Tenancy(store, FakeFileStore(), SETTINGS, mapper=toy_mapper(),
                      root_class=Library, access_class=LibraryAccess, iris=iris)
    await tenancy.ensure_system_database()

    print("1. First start: the guard records the policy")
    await guard_iri_policy(store, tenancy, SETTINGS)
    show("started", "yes")

    print("\n2. IRIs minted under the consumer's policy")
    tenant = (await tenancy.create("Ghent", library_slots(), Principal(id=ADA))).id
    show("tenant", tenant)
    show("access record", iris.access(tenant))
    show("meta graph", iris.meta(tenant))
    show("registry graph", iris.registry(tenant))
    book = iris.mint_aggregate(tenant, "book", "books")
    show("a book (aggregate)", book)
    show("principal (sub=4711)", iris.principal("https://id.example.org", "4711"))

    print("\n3. Restart with the same policy, written differently (defaults spelled out)")
    same = SETTINGS.model_copy(update={"iri_policy": POLICY.model_copy(update={"meta_template": "{tenant}/meta"})})
    await guard_iri_policy(store, tenancy, same)
    show("started", "yes")

    print("\n4. Restart with a changed policy: refused, naming the fields")
    changed = SETTINGS.model_copy(update={
        "deployment": "prod",
        "iri_policy": POLICY.model_copy(update={"object_id": IdSpec(kind=IdKind.RANDOM, length=12)}),
    })
    try:
        await guard_iri_policy(store, tenancy, changed)
    except IriPolicyChanged as error:
        show("refused", error)

    print("\n5. A policy whose graphs collide is refused when it is built")
    try:
        Iris(SETTINGS.model_copy(update={"iri_policy": POLICY.model_copy(
            update={"meta_template": "{tenant}/x", "registry_template": "{tenant}/x"})}))
    except InvalidIri as error:
        show("refused", error)


asyncio.run(main())
```

## Its output

```
1. First start: the guard records the policy
  started                      yes

2. IRIs minted under the consumer's policy
  tenant                       http://mwb.meaningfy.ws/project/db2ymmx
  access record                http://mwb.meaningfy.ws/dev/project/db2ymmx
  meta graph                   http://mwb.meaningfy.ws/project/db2ymmx/meta
  registry graph               http://mwb.meaningfy.ws/project/db2ymmx/registry
  a book (aggregate)           http://mwb.meaningfy.ws/db2ymmx/book/k944dt08iae1f
  principal (sub=4711)         http://mwb.meaningfy.ws/dev/user/4711

3. Restart with the same policy, written differently (defaults spelled out)
  started                      yes

4. Restart with a changed policy: refused, naming the fields
  refused                      the recorded policy differs: the IRI policy cannot change once there is data; differing fields: access_template, principal_template, object_id.length

5. A policy whose graphs collide is refused when it is built
  refused                      the registry template mints the same IRI as the meta: 'http://mwb.meaningfy.ws/project/gua12yf/x'
```
