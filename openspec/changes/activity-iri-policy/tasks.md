EPIC: activity-iri-policy (proposal.md, issue #197). Decisions: design.md PD-1 to PD-12, DEC-1 to DEC-6.

> Derives from: EPIC `activity-iri-policy`. One stage (SMALL), one pull request.

Every task: the failing test first, in the tier named; task gate `make test-changed
check-quality` (`make test-fast check-quality` where marked); commit body
`Refs: activity-iri-policy <task> <PD>`. Builders never commit; the lead does. The policy used in
the tests below is `P = {tenant}/activity/{id}` on the toy service settings, unless a row says
otherwise. No existing test is moved or rewritten; every new test runs in the lane of its folder
(`make test-unit-ci` shards in CI for `tests/unit/`, `make test-feature` for `tests/feature/`).

## 1. Stage 1: activities under the IRI policy

- [ ] 1.1 Lead: check the deltas against the living specs on `develop`: the two MODIFIED
  requirements copy the living text and scenarios and change only the activity sentences.
  Accept: `openspec validate activity-iri-policy --strict` passes; a diff of each MODIFIED
  requirement against `openspec/specs/` shows only those changes.
- [ ] 1.2 Unit, schema (PD-1). First, failing: `tests/unit/iris/test_iri_policy_model.py`
  `test_the_activity_template_defaults_to_a_urn_uuid_and_ends_in_its_id`: `IriPolicy()`'s
  `activity_template` is `urn:uuid:{id}`; `ServiceSettings` with activity templates
  `{tenant}/activity`, `{tenant}/{type}/{id}` and the tenant-less `{base}activity/{id}` (PD-12)
  are refused naming `activity_template`; `P` and
  `{base}{tenant_id}/activity/{id}` are accepted. And
  `tests/unit/iris/test_iri_policy_effective.py`
  `test_a_policy_recorded_before_the_activity_template_is_the_default`: a policy JSON without the
  slot, made effective, equals `effective_policy(None, settings)`. Then the YAML and
  `make generate`. Gate: `make test-fast check-quality`, `make check-generated`. Accept: both pass;
  the regenerated files are in the same commit.
- [ ] 1.3 Unit, `Iris` (PD-2 to PD-4), after 1.2. First, failing:
  `tests/unit/iris/test_iris_policy.py`
  `test_an_activity_iri_follows_the_activity_template`: under `P`, `activity(t, U)` is
  `t + "/activity/" + U`; `is_activity(t, it)` is true, false for another tenant, false for
  `urn:uuid:U`, false for a non-canonical UUID; `activity_uuid` of both forms is `U`; under the
  default policy `activity(t, U)` is `urn:uuid:U` and `is_activity` agrees with `is_activity_id`
  on the error-matrix inputs. Then a new `tests/unit/iris/test_iris_activity_adversarial.py`:
  refused rows, one per PD-3a refusal, each `InvalidIri` naming `activity_template`:
  `urn:x:{tenant_id}:{id}` (tenant id outside the base), `activity/{tenant_id}/{id}` (no scheme);
  accepted rows: `{base}{tenant_id}/activity/{id}` under application template `{base}app`
  (`app/activity/U` is the application's activity), and `P`;
  `test_a_tenant_the_policy_cannot_parse_mints_an_activity_without_tenant_id` (PD-2:
  `activity(FAKE_TENANT, U)` is `urn:uuid:U` under the default and `FAKE_TENANT/activity/U` under
  `P`; under `{base}{tenant_id}/activity/{id}` it raises `InvalidIri`), and a commit through the
  testkit's `fake_session` under the default policy records `urn:uuid:` as today;
  `test_an_activity_iri_is_no_aggregate_or_loaded_graph` (PD-3b: under `P`, `is_aggregate(t,
  t/activity/U)` is false, `t/books/U` still true); `test_a_root_minted_inside_the_activity_template_is_refused`
  (PD-3c: roots `[("book", "activity")]` refused naming `book`, `[("book", "books")]` accepted,
  and accepted under random object ids); and
  `test_the_default_activity_template_reserves_no_word`: under 4-character tenant ids,
  `tenant("uuid")` is a tenant (PD-4). Then `root_paths(view)` in
  `tests/unit/schema/test_schema_structure.py` (the toy roots and their paths) and the kit call.
  Accept: all pass; each refusal row fails when its check is removed by hand.
- [ ] 1.4 Unit, session (PD-5, PD-6), after 1.3. First, failing:
  `tests/unit/tenancy/test_session_activity.py`
  `test_a_commit_under_an_activity_template_records_its_activity_under_the_tenant`: on the fake
  store with `Iris` under `P`, a book committed serving `command(ShelveBooks, …)` (the toy command)
  records `t/activity/U` where `urn:uuid:U` is the command's id; no `urn:uuid:` IRI is in any graph
  of the tenant database; `on_commit` and `is_recorded` see the placed IRI; the command's own
  triples are about the placed IRI; every `Generation` and `Invalidation` of the record names the
  placed IRI as its activity (PD-5); a commit with no command records `t/activity/<uuid>`; a second
  commit of the same `Served` is refused as today. Then
  `test_session_activity_iri_is_what_the_commit_records` and
  `test_without_a_template_the_activity_is_the_command_id` (G-2) and
  `test_a_hand_made_aggregate_at_an_activity_iri_is_refused` (`InvalidIri`, nothing written). Gate: `make test-fast
  check-quality` (`completed()` changes). Accept: all pass; every existing test in
  `tests/unit/tenancy/` and `tests/unit/persistence/` passes unchanged; `ast-grep` for
  `$X.activity.id` in `rdf_persistence/persistence/` finds no read of the served id after
  `Transaction.__init__` other than the placement (RISK-1).
- [ ] 1.5 Unit, events (PD-7), after 1.3. First, failing: `tests/unit/api/test_events_route.py`
  `test_a_follower_resumes_after_an_activity_iri_of_the_policy`: on the toy service under `P`, a
  follower with `Last-Event-ID` the placed IRI of an earlier commit receives the two later events
  once; with `urn:uuid:<that U>` it is reset. Accept: passes; `tests/unit/events/` passes unchanged.
- [ ] 1.6 Unit, tenancy (PD-8, DEC-3), after 1.2; parallel to 1.4. First, failing:
  `tests/unit/tenancy/test_iri_policy_guard.py`
  `test_a_changed_activity_template_refuses_start_up_naming_it`: started under the default, then
  under `P` → `IriPolicyChanged` naming `activity_template`. Then in
  `tests/unit/tenancy/test_iri_policy_guard_adversarial.py`
  `test_an_older_record_without_the_activity_template_is_the_default`; in
  `tests/unit/tenancy/test_tenant_dump_adversarial.py`
  `test_a_dump_made_under_another_activity_template_is_refused`; in
  `tests/unit/tenancy/test_tenant_dump.py`
  `test_a_restored_tenant_under_an_activity_template_owns_its_activities` (after 1.4: dump under
  `P`, restore to a new id, every activity is `<new tenant>/activity/<same U>`). Accept: all pass;
  the comment in `tenant_dump.py` names both templates.
- [ ] 1.7 Feature (issue acceptance), after 1.4 and 1.5: three scenarios in
  `tests/feature/iri_policy.feature`, steps in `tests/feature/test_iri_policy.py`: the default
  policy's activity is `urn:uuid:` and a UUID; under `P` a transition with a comment, a comment and a
  replace each record an activity under the tenant, and the transition list, the comment's thread
  and the provenance read find them; a restart under another activity template fails naming it.
  The developer signs off the scenarios before the steps are written. Lane: `make test-feature`.
  Accept: the three pass.
- [ ] 1.7a Integration (RISK-1), after 1.4: a new `tests/integration/store/test_activity_iri_policy.py`
  on Fuseki under `P`: IT-A1 a served commit records `t/activity/U` and `is_recorded` finds it;
  IT-A2 a second commit of a command with the same UUID is refused by the store's taken-IRI guard
  and writes nothing; IT-A3 `relayed_since(<placed IRI of the first>)` returns the later activity.
  Written by the builder, run by the lead in `make test-containers`. Accept: the three pass on
  Fuseki.
- [ ] 1.8 Docs (PD-9): `user-manual/iri-policy.adoc`, `howto/event-driven.adoc`,
  `partials/reference/public-api.adoc`, and the docstrings of `Served` (its stale `urn:uuid:`
  restore rationale), `Mapper.served` and `messagebus.command`. No new page. Accept: `make check-docs` passes; no page
  says an activity IRI is always `urn:uuid:`.
- [ ] 1.9 Lead: `make check-all`, `make test-containers`, `make check-generated`; one review pass
  (SMALL); each spec scenario and the issue's three acceptance items shown in
  `evidence/acceptance.md`; the consumer told the change id (D-12).

## Roadmap

- [ ] 1.1 · [ ] 1.2 · [ ] 1.3 · [ ] 1.6 · [ ] 1.4 · [ ] 1.5 · [ ] 1.7a · [ ] 1.7 · [ ] 1.8 · [ ] 1.9
  (1.6's first three tests need only 1.2; its restore test needs 1.4; 1.4 and 1.5 may run in
  parallel after 1.3.)

## Verification

`make check-all` and `make test-containers` green; `openspec validate activity-iri-policy
--strict`; the clarity gate logged in `evidence/clarity-gate.md`. `make test-containers` runs
1.7a under the policy and the existing Fuseki activity tests on the default policy.
