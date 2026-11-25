# Acceptance: activity-iri-policy (#197)

Verification is the agents' (below); validation is the developer's (last section).

## Gates (stage 1, before the PR)

On 87aad87e + the fix pass in flight (rebased on develop 5b58b624), before the fix pass's commit:

| Gate | Result |
|---|---|
| `make check-all` | passed: quality; unit 8488 passed, 4 xfailed (coverage 96.47 %, floor 80); feature 102 passed (70.67 %, floor 50); generator 1780 passed, 1 xfailed (96.95 %, floor 80) |
| `make test-containers` | passed: 370 passed on Fuseki, among them 1.7a's IT-A1 to IT-A3 |
| `make check-generated` | passed: generated output fresh and type-checked |

After the fix pass (30ec5ddd): POST-FIX-PENDING

## The issue's three acceptance items

| #197 acceptance | Shown by |
|---|---|
| 1. Default policy: the activity IRI is `urn:uuid:` and a UUID (unchanged) | `tests/feature/iri_policy.feature` "Without an activity template, an activity is a urn:uuid"; `test_iris_policy.py::test_under_the_default_policy_an_activity_is_the_urn_uuid`; `test_session_activity.py::test_without_a_template_the_activity_is_the_command_id` |
| 2. Under an activity template the IRI starts with base and tenant; transitions, comments and provenance reads still find it | `tests/feature/iri_policy.feature` "Under an activity template, every activity lives under its tenant" (move, comment, replace; transitions, comment provenance, provenance read, no `urn:uuid:`); Fuseki: `tests/integration/store/test_activity_iri_policy.py` IT-A1 to IT-A3 |
| 3. A restart under another template refuses to start, naming the field | `tests/feature/iri_policy.feature` "A restart under another activity template is refused"; `test_iri_policy_guard.py::test_a_changed_activity_template_refuses_start_up_naming_it` |

Template syntax as built: `{tenant}/activity/{id}` (or `{base}{tenant_id}/activity/{id}`), default
`urn:uuid:{id}` (PD-1), not the issue's sketch `{base}{tenant}/activity/{id}` / `{uuid}`.

## Spec scenarios

`rp-iri-policy`

| Scenario | Test |
|---|---|
| an application that sets nothing | existing living-spec tests (unchanged), plus `test_iri_policy_model.py::test_the_activity_template_defaults_to_a_urn_uuid_and_ends_in_its_id` |
| an activity under the default policy | `test_iris_policy.py::test_under_the_default_policy_an_activity_is_the_urn_uuid`, `::test_under_the_default_policy_an_activity_is_what_is_activity_id_accepts`; feature scenario 1 |
| a commit under an activity template | `test_session_activity.py::test_a_commit_under_an_activity_template_records_its_activity_under_the_tenant`, `::test_every_invalidation_of_a_placed_activity_names_it`, `::test_a_commit_without_a_command_records_an_activity_under_the_template`; IT-A1, IT-A2 |
| transitions and comments still find their activity | feature scenario 2 |
| resuming a stream under the template | `tests/unit/api/test_events_route.py::test_a_follower_resumes_after_an_activity_iri_of_the_policy`; IT-A3 |
| a changed activity template | `test_iri_policy_guard.py::test_a_changed_activity_template_refuses_start_up_naming_it`; feature scenario 3 |
| a policy recorded before the activity template | `test_iri_policy_effective.py::test_a_policy_recorded_before_the_activity_template_is_the_default`, `test_iri_policy_guard_adversarial.py::test_an_older_record_without_the_activity_template_is_the_default` |
| a restored tenant keeps its activities | `test_tenant_dump.py::test_a_restored_tenant_under_an_activity_template_owns_its_activities`, `test_tenant_dump_adversarial.py::test_a_dump_made_under_another_activity_template_is_refused` |
| a tenant-less activity template | `test_iri_policy_model.py::test_an_activity_template_without_the_tenant_or_the_closing_id_is_refused` |
| an activity template that a restore cannot move | `test_iris_activity_adversarial.py::test_an_activity_template_a_restore_could_not_move_or_that_collides_is_refused` (rows i, ii, iv) |
| a glued activity template | same test, rows iii |
| an aggregate path inside the activity template | `test_iris_policy.py::test_a_root_minted_inside_the_activity_template_is_refused`, `tests/unit/api/test_kit_activity_template.py` |
| a hand-made aggregate at an activity IRI | `test_session_activity.py::test_a_hand_made_aggregate_at_an_activity_iri_is_refused` |

`rp-messages`

| Scenario | Test |
|---|---|
| a generic replace, a refused commit, a commit of mixed changes | unchanged living-spec tests (`test_session_activity.py` tc23, tc27, tc26) |
| a command's activity under an activity template | `test_session_activity.py::test_a_commit_under_an_activity_template_records_its_activity_under_the_tenant`, `::test_session_activity_iri_is_what_the_commit_records`, `::test_session_activity_iri_refuses_a_foreign_activity` |

## Validation (the developer)

Demo offered: run the toy service under `{tenant}/activity/{id}`, commit a move with a comment,
and read the tenant's provenance graph (every activity under the tenant, no `urn:uuid:`); then
restart under the default template and see start-up refused naming `activity_template`.

Verdict: DEMO-PENDING
