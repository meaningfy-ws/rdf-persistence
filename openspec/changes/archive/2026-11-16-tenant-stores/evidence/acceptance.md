# Acceptance: tenant-stores

**Verdict:** accepted by the developer on 2026-11-16 ("I accept the demo").

**What was shown:** the final report of the epic session (session I): the two merged pull requests
(#122 the routing of each tenant to the store its access record names, the sweep and migrations on
every wired store; #123 the service kit with several stores, `kit.store_of`, the second Fuseki in
the testkit, the feature and the docs), the challenge each stage passed, and the test status on
the final head (7159 tests passed at 95.68% coverage; 262 container tests passed; CI green on
develop after the merge).

**Demo:** `tests/feature/tenant_stores.feature`: a tenant created on a second store, routed there,
dumped, restored onto another store and swept on both stores.

**Left open at acceptance:** resolve the store inside `tenant_dump.dump` and
`tenant_sweep.sweep_tenant`; a shared `toy_tenancy` test helper; the routing in a class of its
own. None blocks a consumer.
