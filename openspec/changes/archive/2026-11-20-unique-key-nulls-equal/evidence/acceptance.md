# Acceptance: unique-key-nulls-equal

**Demo skipped** by the developer, 2026-11-20. Reason: SMALL appetite; IT-NE-1 and IT-NE-2 run
issue #202's acceptance on Fuseki and are green in `make test-containers` (318 passed, PR #211).

## Issue #202 acceptance

| Acceptance | Shown by |
|---|---|
| Two concurrent creates of "Dune" with no subtitle: exactly one succeeds, the other raises `KeyConflict` | `tests/integration/store/test_unique_keys.py::test_it_ne_1_of_two_concurrent_adds_of_dune_without_subtitle_exactly_one_is_stored` (Fuseki, 20 rounds) |
| "Dune" with no subtitle stored, "Dune" / "Messiah" accepted | `tests/unit/persistence/test_session_unique_keys.py::test_ex2_a_present_value_differs_from_an_absence` |
| A key without the option behaves as before | `test_a_key_without_the_option_claims_nothing_for_an_absent_slot`, `test_g4_the_text_of_a_key_without_the_option_is_unchanged` |

## New or changed scenarios (signed off before build)

| Scenario | Test |
|---|---|
| S1 absent keys never conflict (GIVEN changed) | `test_tc17_books_without_isbn_never_clash`, unchanged and green |
| S2 concurrent creates with the slot absent | IT-NE-1 (Fuseki); `test_ex1_an_absence_another_root_shares_is_a_key_conflict` (fake store) |
| S3 a present value differs | `test_ex2_a_present_value_differs_from_an_absence` |
| S4 an empty value is not an absence | `test_ex3_an_empty_value_is_not_an_absence`, `test_an_absence_is_not_an_empty_value_either_way` |
| S5 a key without the option behaves as before | `test_a_key_without_the_option_claims_nothing_for_an_absent_slot` |
| S6 duplicates that share an absence | `test_the_report_names_the_shared_absence_by_the_marker_text`; IT-NE-2 (Fuseki, with a part, D-5) |
| G1 absent values counted at tenant scope | `tests/generator/unit/test_hard_check.py::test_counting_absent_values_as_equal_needs_the_tenant_scope[false-at-tenant]` |
| G2 an unsupported scope | same table, `[false-at-another-scope]` |
