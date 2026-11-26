EPIC: activity-iri-policy (proposal.md, issue #197). Decisions: design.md PD-1 to PD-12, DEC-1 to DEC-6.

> Derives from: EPIC `activity-iri-policy`. One stage (SMALL), one pull request.

Every task: the failing test first, in the tier named; task gate `make test-changed
check-quality` (`make test-fast check-quality` where marked); commit body
`Refs: activity-iri-policy <task> <PD>`. Builders never commit; the lead does. The policy used in
the tests below is `P = {tenant}/activity/{id}` on the toy service settings, unless a row says
otherwise. No existing test is moved or rewritten; every new test runs in the lane of its folder
(`make test-unit-ci` shards in CI for `tests/unit/`, `make test-feature` for `tests/feature/`).

## 1. Stage 1: activities under the IRI policy

- [x] 1.1 Lead: check the deltas against the living specs on `develop`: the two MODIFIED
  requirements copy the living text and scenarios and change only the activity sentences.
  Accept: `openspec validate activity-iri-policy --strict` passes; a diff of each MODIFIED
  requirement against `openspec/specs/` shows only those changes.
- [x] 1.2 Unit, schema (PD-1). First, failing: `tests/unit/iris/test_iri_policy_model.py`
  `test_the_activity_template_defaults_to_a_urn_uuid_and_ends_in_its_id`: `IriPolicy()`'s
  `activity_template` is `urn:uuid:{id}`; `ServiceSettings` with activity templates
  `{tenant}/activity`, `{tenant}/{type}/{id}` and the tenant-less `{base}activity/{id}` (PD-12)
  are refused naming `activity_template`; `P` and
  `{base}{tenant_id}/activity/{id}` are accepted. And
  `tests/unit/iris/test_iri_policy_effective.py`
  `test_a_policy_recorded_before_the_activity_template_is_the_default`: a policy JSON without the
  slot, made effective, has `activity_template == "urn:uuid:{id}"` (fails first: no such field)
  and equals `effective_policy(None, settings)`. And in `tests/unit/iris/test_iris_policy.py`
  `test_the_default_activity_template_reserves_no_word` (PD-4): under 4-character tenant ids,
  `tenant("uuid")` is a tenant and `urn`, `uuid` are not in `_reserved`; it passes before the slot
  exists and fails as soon as the YAML adds it, so it is written first and proves PD-4 lands in this
  task, not later (the generated `IriPolicy` fills every default, `rp_iris_services.py:176`, so the
  default's words would join `_reserved` the moment the slot exists). Then the YAML, `make
  generate` and PD-4's skip in `_reserved`. Gate: `make test-fast check-quality`, `make
  check-generated`. Accept: the three pass; the regenerated files are in the same commit.
- [x] 1.3 Unit, `Iris` (PD-2, PD-3), after 1.2. First, failing:
  `tests/unit/iris/test_iris_policy.py`
  `test_an_activity_iri_follows_the_activity_template`: under `P`, `activity(t, U)` is
  `t + "/activity/" + U`; `is_activity(t, it)` is true, false for another tenant, false for
  `urn:uuid:U`, false for a non-canonical UUID; `activity_uuid` of both forms is `U`; under the
  default policy `activity(t, U)` is `urn:uuid:U` and `is_activity(t, x)` equals
  `is_activity_id(x)` for each `x` of: `urn:uuid:U`, `urn:uuid:` + `U` upper-cased, `urn:uuid:` +
  `U` without hyphens, `t/activity/U`, `t/books/U`, and `""`. Then a new `tests/unit/iris/test_iris_activity_adversarial.py`:
  refused rows, one per PD-3a refusal, each `InvalidIri` naming `activity_template`:
  `activity/{tenant_id}/{id}` (i, no scheme), `urn:x:{tenant_id}:{id}` (ii, outside the base),
  `{tenant}{id}` and `{base}{tenant_id}{id}` (iii, glued), and `{tenant}/{id}` beside aggregate
  template `{tenant}/{id}` under `uuid4` object ids, built as a bare `Iris(settings)` (iv);
  accepted rows: `{base}{tenant_id}/activity/{id}` under application template `{base}app`
  (`is_activity(app, app/activity/U)` is true and `is_aggregate(app, app/activity/U)` false), `P`,
  and the default under a tenant-id spec of 4 characters from `048u` built 50 times with
  `id_source` unset (never refused); before the glued rows, `_ID_GLUED_BEFORE`/`_AFTER` move from
  `tenant_move.py` to `iris/domain/layout.py` (PD-3a (iii)) with
  `tests/unit/tenancy/test_tenant_move.py` passing unchanged and `make check-architecture` green;
  `test_a_tenant_the_policy_cannot_parse_mints_an_activity_without_tenant_id` (PD-2:
  `activity(FAKE_TENANT, U)` is `urn:uuid:U` under the default and `FAKE_TENANT/activity/U` under
  `P`; under `{base}{tenant_id}/activity/{id}` it raises `InvalidIri`), and a commit through the
  testkit's `fake_session` under the default policy records `urn:uuid:` as today;
  `test_an_activity_iri_is_no_aggregate_or_loaded_graph` (PD-3b: under `P`, `is_aggregate(t,
  t/activity/U)` is false, `t/books/U` still true; `is_aggregate_graph(t, t/activity/U/graph)` is
  false; `aggregate_id_of(t/activity/U)` is `None`, `aggregate_id_of(t/books/U)` is `U`; under the
  default policy the three answer as today); `test_a_root_minted_inside_the_activity_template_is_refused`
  (PD-3c: roots `[("book", "activity")]` refused naming `book`, `[("book", "books")]` accepted,
  and accepted under random object ids). Then `root_paths(view)` in
  `tests/unit/schema/test_schema_structure.py` (the toy roots and their paths) and the kit call.
  Accept: all pass; each refusal row fails when its check is removed by hand.
- [x] 1.4 Unit, session (PD-5, PD-6), after 1.3. First, failing:
  `tests/unit/tenancy/test_session_activity.py`
  `test_a_commit_under_an_activity_template_records_its_activity_under_the_tenant`: on the fake
  store with `Iris` under `P`, a book committed serving `command(ShelveBooks, …)` (the toy command)
  records `t/activity/U` where `urn:uuid:U` is the command's id; no `urn:uuid:` IRI is in any graph
  of the tenant database; `on_commit` and `is_recorded` see the placed IRI; the command's own
  triples are about the placed IRI; every `Generation` and `Invalidation` of the record names the
  placed IRI as its activity (PD-5); a commit with no command records `t/activity/<uuid>`; a second
  commit of the same `Served` is refused as today. Then
  `test_session_activity_iri_is_what_the_commit_records` and
  `test_session_activity_iri_refuses_a_foreign_activity` (PD-6: under `P`, `Iris.activity_uuid`
  alone accepts `https://foreign.example/x/activity/U`, while `session.activity_iri` of it, and of
  another tenant's placed IRI, raises `ValueError`) and
  `test_without_a_template_the_activity_is_the_command_id` (G-2) and
  `test_a_hand_made_aggregate_at_an_activity_iri_is_refused` (`InvalidIri`, nothing written). Gate: `make test-fast
  check-quality` (`completed()` changes). Accept: all pass; every existing test in
  `tests/unit/tenancy/` and `tests/unit/persistence/` passes unchanged; `ast-grep` for
  `$X.activity.id` in `rdf_persistence/persistence/` finds no read of the served id after
  `Transaction.__init__` other than the placement (RISK-1).
- [x] 1.5 Unit, events (PD-7), after 1.3. First, failing: `tests/unit/api/test_events_route.py`
  `test_a_follower_resumes_after_an_activity_iri_of_the_policy`: on the toy service under `P`, a
  follower with `Last-Event-ID` the placed IRI of an earlier commit receives the two later events
  once; with `urn:uuid:<that U>` it is reset. Accept: passes; `tests/unit/events/` passes unchanged.
- [x] 1.6 Unit, tenancy (PD-8, DEC-3), after 1.2; parallel to 1.4. First, failing:
  `tests/unit/tenancy/test_iri_policy_guard.py`
  `test_a_changed_activity_template_refuses_start_up_naming_it`: started under the default, then
  under `P` → `IriPolicyChanged` naming `activity_template`. Then in
  `tests/unit/tenancy/test_iri_policy_guard_adversarial.py`
  `test_an_older_record_without_the_activity_template_is_the_default` (a policy recorded
  without the slot lets the default start, and refuses a start under `P` naming
  `activity_template`; the second half fails first, because today no field differs); in
  `tests/unit/tenancy/test_tenant_dump_adversarial.py`
  `test_a_dump_made_under_another_activity_template_is_refused`; in
  `tests/unit/tenancy/test_tenant_dump.py`
  `test_a_restored_tenant_under_an_activity_template_owns_its_activities` (after 1.4: dump under
  `P`, restore to a new id, every activity is `<new tenant>/activity/<same U>`). Accept: all pass;
  the comment in `tenant_dump.py` names both templates.
- [x] 1.7 Feature (issue acceptance), after 1.4 and 1.5: three scenarios in
  `tests/feature/iri_policy.feature`, steps in `tests/feature/test_iri_policy.py`: the default
  policy's activity is `urn:uuid:` and a UUID; under `P` a transition with a comment, a comment and a
  replace each record an activity under the tenant, and the transition list, the comment's thread
  and the provenance read find them; a restart under another activity template fails naming it.
  Signed off 2026-11-25 as `features/iri_policy.feature` in this change: append those three
  scenarios verbatim (no wording change without a new sign-off), with their steps, in one commit. Lane: `make test-feature`.
  Accept: the three pass.
- [x] 1.7a Integration (RISK-1), after 1.4: a new `tests/integration/store/test_activity_iri_policy.py`
  on Fuseki under `P`: IT-A1 a served commit records `t/activity/U` and `is_recorded` finds it;
  IT-A2 a second commit of a command with the same UUID is refused by the store's taken-IRI guard
  and writes nothing; IT-A3 `relayed_since(<placed IRI of the first>)` returns the later activity.
  Written by the builder, run by the lead in `make test-containers`. Accept: the three pass on
  Fuseki.
- [x] 1.8 Docs (PD-9): `user-manual/iri-policy.adoc`, `howto/event-driven.adoc`,
  `partials/reference/public-api.adoc`, and the docstrings of `Served` (its stale `urn:uuid:`
  restore rationale), `Mapper.served` and `messagebus.command`. No new page. Accept: `make check-docs` passes; no page
  says an activity IRI is always `urn:uuid:`.
- [ ] 1.9 Lead: `make check-all`, `make test-containers`, `make check-generated`; one review pass
  (SMALL); each spec scenario and the issue's three acceptance items shown in
  `evidence/acceptance.md`; the consumer told the change id (D-12).

## Roadmap

- [x] 1.1 · [x] 1.2 · [x] 1.3 · [x] 1.6 · [x] 1.4 · [x] 1.5 · [x] 1.7a · [x] 1.7 · [x] 1.8 · [ ] 1.9
  (1.6's first three tests need only 1.2; its restore test needs 1.4; 1.4 and 1.5 may run in
  parallel after 1.3.)

## Verification

`make check-all` and `make test-containers` green; `openspec validate activity-iri-policy
--strict`; the clarity gate logged in `evidence/clarity-gate.md`. `make test-containers` runs
1.7a under the policy and the existing Fuseki activity tests on the default policy.
