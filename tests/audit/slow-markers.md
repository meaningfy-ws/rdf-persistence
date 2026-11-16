# Slow markers (task 1.10, PD-6)

Each test was timed alone on 2026-11-16 after the grooming of the test files (task 4.1):
`uv run pytest -p no:xdist -p no:randomly --durations=0 <id>`, the slowest case's set-up + call.
A further full run of the unit and feature tiers (`-m "(unit or feature) and not slow"`, serial)
listed every test of 2 s or more, and each was re-timed alone. Threshold: 2 s (`pytest.ini`);
a marked test is unmarked below 0.5 s; the range 0.5 to 2 s keeps whatever it has.

The first test of a process pays about 0.7 s of one-off set-up, which is part of "alone" here. That
is why the freshness tests, timed 0.2 to 0.4 s in the first audit, now read 0.75 to 0.95 s and keep
their marker.

The "2026-11-16 audit" column is the figure of the first audit, where the test had one. Tests moved
or renamed by task 4.1 are located by function name.

## Marker added (17)

| Test | Seconds alone | Action | 2026-11-16 audit |
|---|---|---|---|
| `tests/unit/generation/test_lock_step.py::test_a_removed_slot_with_a_new_version_drafts_a_drop_and_prints_where` | 7.63 | add | 6.21 |
| `tests/unit/generation/test_lock_step.py::test_an_edited_draft_is_kept_byte_for_byte` | 6.95 | add | 6.22 |
| `tests/unit/generation/test_lock_step.py::test_an_unresolved_draft_succeeds_once_then_fails_the_next_run_and_the_check` | 5.68 | add | 4.31 |
| `tests/unit/generation/test_lock_step.py::test_a_version_the_chain_already_left_is_refused` | 5.03 | add | 3.05 |
| `tests/unit/generation/test_lock_step.py::test_safe_changes_with_the_version_unchanged_rewrite_the_lock_only` | 4.27 | add | 2.66 |
| `tests/unit/generation/test_lock_step.py::test_the_lock_is_a_manifest_output_and_a_second_run_changes_nothing` | 4.24 | add | 3.86 |
| `tests/unit/generation/test_lock_step.py::test_safe_changes_with_a_new_version_draft_a_migration_with_no_steps` | 4.23 | add | 4.74 |
| `tests/unit/generation/test_lock_step.py::test_a_raised_version_with_no_change_drafts_a_migration_with_no_steps` | 4.17 | add | 5.88 |
| `tests/unit/generation/test_lock_step.py::test_a_version_with_a_slash_is_written_with_an_underscore_in_the_file_name` | 4.16 | add | 2.56 |
| `tests/unit/generation/test_lock_step.py::test_a_removed_slot_with_the_version_unchanged_fails_naming_it` | 3.93 | add | 2.32 |
| `tests/unit/generation/test_lock_step.py::test_a_change_that_cannot_be_migrated_fails_with_any_version` | 3.19 | add | 3.60 |
| `tests/unit/generation/test_lock_step.py::test_a_slot_that_was_inlined_when_the_lock_was_written_is_not_migratable` | 3.18 | add | 2.63 |
| `tests/unit/testkit/test_adopt_step6.py::test_the_guides_checks_pass_on_the_toy_library` | 4.05 | add | 3.57 |
| `tests/unit/entrypoints/test_router.py::test_each_route_asks_for_its_action` | 4.18 | add | none |
| `tests/unit/entrypoints/test_service_written.py::test_a_session_adds_replaces_and_removes_a_shed_each_with_a_new_version` | 2.77 | add | none |
| `tests/unit/services/test_session_activity_adversarial.py::test_a_huge_served_triple_list_commits_whole_or_not_at_all` | 2.74 | add | 2.54 |
| `tests/unit/generation/test_boundary_check.py::test_the_toy_generates_a_frame_for_each_activity_class` | 2.08 | add | 4.04 |

## Marker removed (1)

| Test | Seconds alone | Action | 2026-11-16 audit |
|---|---|---|---|
| `tests/unit/test_packaging.py::test_the_wheel_ships_the_py_typed_marker` | 0.07 | remove | none |

## Listed by the first audit and left as they are (11)

| Test | Seconds alone | Action | 2026-11-16 audit |
|---|---|---|---|
| `tests/unit/entrypoints/test_allowed_actions_adversarial.py::test_a_listed_action_is_allowed_and_an_unlisted_one_is_refused` | 1.04 (54 cases) | none, below 2 s | 5.01 |
| `tests/unit/entrypoints/test_listing_routes_read.py::TestReadOnlyListing::test_a_bad_query_is_a_400_problem_and_changes_nothing` | 0.69 | none, below 2 s | 6.36 |
| `tests/unit/services/test_relay.py::test_tc16_the_loop_survives_a_failed_round_and_publishes_after_a_wake` | 0.25 | none, below 2 s | 2.08 |
| `tests/unit/adapters/test_fuseki_store.py::test_an_unreachable_store_is_unavailable` | 0.00 | none, not marked | 0.00 |
| `tests/unit/generation/test_freshness.py::test_stale_targets_lists_only_the_targets_with_problems` | 0.93 | keep the marker (0.5 to 2 s) | 0.36 |
| `tests/unit/generation/test_freshness.py::test_without_a_command_the_hint_names_rp_generate` | 0.80 | keep the marker | 0.23 |
| `tests/unit/generation/test_roundtrip.py::test_the_testkit_and_the_round_trip_do_not_import_hypothesis` | 0.50 (0.48 to 0.50 in three runs) | keep the marker | 0.43 |
| `tests/unit/testkit/test_freshness_plugin.py::test_a_configuration_error_beside_a_fresh_project_stops_the_session_without_a_hint` (renamed) | 0.94 | keep the marker | 0.22 |
| `tests/unit/testkit/test_freshness_plugin.py::test_a_fresh_project_lets_the_tests_run` | 0.79 | keep the marker | 0.19 |
| `tests/unit/testkit/test_freshness_plugin.py::test_a_hand_edited_generated_file_stops_the_session_and_is_named` | 0.82 | keep the marker | 0.20 |
| `tests/unit/testkit/test_freshness_plugin.py::test_a_listed_project_without_targets_stops_the_session` | 0.80 | keep the marker | 0.20 |
| `tests/unit/testkit/test_freshness_plugin.py::test_a_non_string_command_stops_the_session_naming_the_toml_key` | 0.79 | keep the marker | 0.20 |

## Tests of 2 s or more in the serial full run that were not slow alone (no action)

Their cost in the serial run was a first-use fixture or a loaded machine; alone they are fast.
Examples: `test_schema_structure.py::test_a_predicate_reads_its_annotation_from_the_metamodel`
(14.95 s in the run, 0.09 s alone), `test_tenancy.py::test_a_validator_that_returns_an_awaitable_is_a_bug_without_a_warning`
(11.85 s, 0.22 s), `test_collaboration_collections_adversarial.py::test_an_if_version_that_is_not_the_version_is_a_conflict_and_deletes_nothing`
(9.95 s, 0.25 s). The two just under the threshold alone are
`test_markers.py::test_a_test_past_its_timeout_fails_naming_itself_and_the_next_test_runs` (1.93 s)
and `test_relay_adversarial.py::test_a_long_backlog_goes_out_in_one_round_in_store_order_each_once`
(1.82 s).

## Marked tests of the unit and feature tiers re-timed alone

All 44 marked functions there were re-timed; none other than the one above is below 0.5 s. Those
from 0.5 to 2 s keep their marker.
