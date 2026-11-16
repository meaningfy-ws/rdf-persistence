# Slow markers to change (audit 2026-11-16, P-6)

Each test was timed alone (`pytest -p phase_times <ids>`, no xdist, idle machine): the slowest
case's set-up + call. Threshold: 2 s (`pytest.ini`).

## Add `@pytest.mark.slow` (18)

| Test | Seconds alone |
|---|---|
| `tests/unit/generation/test_lock_step.py::test_a_removed_slot_with_a_new_version_drafts_a_drop_and_prints_where` | 6.21 |
| `tests/unit/generation/test_lock_step.py::test_an_edited_draft_is_kept_byte_for_byte` | 6.22 |
| `tests/unit/generation/test_lock_step.py::test_an_unresolved_draft_succeeds_once_then_fails_the_next_run_and_the_check` | 4.31 |
| `tests/unit/generation/test_lock_step.py::test_a_slot_that_was_inlined_when_the_lock_was_written_is_not_migratable` | 2.63 |
| `tests/unit/testkit/test_adopt_step6.py::test_the_guides_checks_pass_on_the_toy_library` | 3.57 |
| `tests/unit/generation/test_lock_step.py::test_the_lock_is_a_manifest_output_and_a_second_run_changes_nothing` | 3.86 |
| `tests/unit/generation/test_lock_step.py::test_a_change_that_cannot_be_migrated_fails_with_any_version` | 3.60 |
| `tests/unit/generation/test_lock_step.py::test_safe_changes_with_a_new_version_draft_a_migration_with_no_steps` | 4.74 |
| `tests/unit/generation/test_lock_step.py::test_a_removed_slot_with_the_version_unchanged_fails_naming_it` | 2.32 |
| `tests/unit/services/test_session_activity_adversarial.py::test_a_huge_served_triple_list_commits_whole_or_not_at_all` | 2.54 |
| `tests/unit/generation/test_boundary_check.py::test_the_toy_generates_a_frame_for_each_activity_class` | 4.04 |
| `tests/unit/generation/test_lock_step.py::test_safe_changes_with_the_version_unchanged_rewrite_the_lock_only` | 2.66 |
| `tests/unit/generation/test_lock_step.py::test_a_version_the_chain_already_left_is_refused` | 3.05 |
| `tests/unit/generation/test_lock_step.py::test_a_raised_version_with_no_change_drafts_a_migration_with_no_steps` | 5.88 |
| `tests/unit/generation/test_lock_step.py::test_a_version_with_a_slash_is_written_with_an_underscore_in_the_file_name` | 2.56 |
| `tests/unit/entrypoints/test_stage4_adversarial.py::test_a_listed_action_is_allowed_and_an_unlisted_one_is_refused` | 5.01 |
| `tests/unit/entrypoints/test_listing_routes.py::test_a_bad_query_is_a_400_problem_and_changes_nothing` | 6.36 |
| `tests/unit/services/test_relay.py::test_tc16_the_loop_survives_a_failed_round_and_publishes_after_a_wake` | 2.08 |

## Remove `@pytest.mark.slow` (9)

| Test | Seconds alone |
|---|---|
| `tests/unit/adapters/test_fuseki_store.py::test_an_unreachable_store_is_unavailable` | 0.00 |
| `tests/unit/generation/test_freshness.py::test_stale_targets_lists_only_the_targets_with_problems` | 0.36 |
| `tests/unit/generation/test_freshness.py::test_without_a_command_the_hint_names_rp_generate` | 0.23 |
| `tests/unit/generation/test_roundtrip.py::test_the_testkit_and_the_round_trip_do_not_import_hypothesis` | 0.43 |
| `tests/unit/testkit/test_freshness_plugin.py::test_a_configuration_error_stops_the_session_without_a_hint` | 0.22 |
| `tests/unit/testkit/test_freshness_plugin.py::test_a_fresh_project_lets_the_tests_run` | 0.19 |
| `tests/unit/testkit/test_freshness_plugin.py::test_a_hand_edited_generated_file_stops_the_session_and_is_named` | 0.20 |
| `tests/unit/testkit/test_freshness_plugin.py::test_a_listed_project_without_targets_stops_the_session` | 0.20 |
| `tests/unit/testkit/test_freshness_plugin.py::test_a_non_string_command_stops_the_session_naming_the_toml_key` | 0.20 |
