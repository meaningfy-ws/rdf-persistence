> Derives from: EPIC `iri-policy` (proposal.md), GitHub issue #26.

Each task: gitnexus impact on the symbols it touches first (stop on HIGH/CRITICAL and report),
test first, then `make test` and `make check-all`. Requirements cited are in
`specs/rp-iri-policy/spec.md`.

## Stage 1 — mint and check objects under a policy (PR 1)

### 1. Model

- [x] 1.1 `IdSpec`, `IriPolicy`, `ServiceSettings.iri_policy` and `.deployment` in
  `rdf_persistence/model/service/rp_service.yaml`; `rp_iri_type` in the `RpAnnotation` enum of
  `rdf_persistence/model/rp_core.yaml`, the `rp_path` description reworded, and the `listedIn`
  vocabulary term (PD-7); `make generate` (design PD-1, PD-2, PD-8).
  Tests: defaults equal today's shapes; requirement "Policies are checked when settings are made".
- [x] 1.2 Generation check for `rp_iri_type` (unique, not reserved) in
  `generation/checks/hard.py` (PD-8), with its own test schema.

### 2. Domain

- [ ] 2.1 `Iris` in `rdf_persistence/domain/iris.py` (PD-3 to PD-6): minting, matching, id drawing
  with an injectable id source, reserved words, resource names, `{type}` alternations from the
  schema, `tenant_of_access` (PD-10), `is_aggregate_graph` (PD-11); today's functions become shims on
  the default `Iris`; the constructor calls `check_iri_policy` (PD-1); an absent `IdSpec` is
  `uuid4`. Tests: requirements "Without a policy, IRIs are today's" (all of
  `tests/unit/domain/test_iris.py` unchanged), "Each kind of IRI follows its configured template"
  (the consumer's examples), "Ids are random, short when configured, and never reserved"
  (reserved id).

### 3. Services and entrypoints

- [ ] 3.1 Tenants: `services/tenancy.py` mints through `Iris`, re-draws on a clash (PD-5); resource
  names from the tenant id. Tests: "a tenant id clash" (access record, and orphan dataset), the
  consumer's tenant without its access record, which stage 1 leaves at the default
  `{tenant}/access`; the scenario is completed in 5.1.
- [ ] 3.2 Roots, parts, loaded graphs: `services/aggregates.py`, `services/documents.py`,
  `services/mapper.py` (`new_part`), `services/session.py` (`add` of a loaded graph) mint through
  `Iris` with the class's `rp_iri_type`. Tests: "a flat object", "the API path changes, the IRIs do
  not".
- [ ] 3.3 Checks and ownership: `session._graph`, `session._check_commit` (registry `ASK`),
  `access._validate_ends` (PD-11), the listing query and `items_of` (`listedIn`, delete `_owner`),
  the flat part rule in `services/documents.py` (`parse`) and `services/aggregates.py`
  (`create`, `replace` after `get_graph`), the nested rule kept for the default (PD-4, PD-7). Tests: "a hand-made IRI", "an aggregate
  IRI with a part's type", "a loaded graph of another aggregate", "a body that names another
  aggregate's part", "a listing of aggregates with flat parts", and the existing listing and
  document tests under both policies.
- [ ] 3.4 Wiring: `install_service` builds one `Iris` and hands it out (PD-3a); `Session` and
  `fake_session` (`testkit/fakes.py`) take an optional `Iris`; `entrypoints/kit.py` and
  `entrypoints/auth.py` map path ids through it.
  Tests: "a path id of the wrong form"; a feature test serving the toy library under the
  consumer's policy end to end with the fakes.

### 4. Stage 1 delivery

- [ ] 4.1 Container end-to-end test of the toy library under the consumer's policy
  (`make test-containers`). Docs: `howto/adopt.adoc` step 3 (`rp_path` is the API path only,
  `rp_iri_type`), a "Configure the IRI policy" section with the consumer's table, public API table
  in `architecture/index.adoc`, questions page entry. Gates: `make check-all`, `make check-docs`.
  Then the stage loop (deep test, five-lens review, fixes, verify) and PR 1 into `develop`.

## Stage 2 — tenant records, principals and the guard (PR 2)

- [ ] 5.1 Access, meta and registry templates in `services/tenancy.py`, `services/session.py`,
  `services/access.py`; `tenant_iri_of_access` callers in `services/tenancy.py` use
  `Iris.tenant_of_access` (PD-10); the `database_name` description reworded.
  Tests: the consumer's tenant scenario in full (access record with `{deployment}`).
- [ ] 5.2 Principal template in `adapters/jwks.py`: `JwksTokenVerifier` takes an optional `Iris`
  (PD-3a) and mints through `Iris.principal`. Tests: default
  `{issuer}/users/{sub}` unchanged; `{base}{deployment}/user/{sub}` with percent-encoding.
- [ ] 5.3 Policy guard at start-up (PD-9). Tests: requirement "The policy is fixed once a deployment
  has data" (both scenarios) with the fakes, one container test.
- [ ] 5.4 Docs for the stage (guard, access record split, principal), then the stage loop and PR 2.

## Roadmap

- [x] 1.1 · [x] 1.2 · [ ] 2.1 · [ ] 3.1 · [ ] 3.2 · [ ] 3.3 · [ ] 3.4 · [ ] 4.1 · [ ] 5.1 · [ ] 5.2 · [ ] 5.3 · [ ] 5.4

## Verification

Every scenario of `specs/rp-iri-policy/spec.md` has a test; `make check-all`, `make test-containers`
and `make check-docs` green per stage; `openspec validate iri-policy --strict` passes; issue #26
closed by PR 2.
