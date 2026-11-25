# Acceptance: slot-uri-clash

Skipped by the developer, 2026-11-25 (TINY appetite, below LARGE). Reason: the end-to-end test
`test_two_slots_on_one_iri_are_named_with_their_modules_and_the_iri_and_nothing_is_written`
runs `rp-generate` on the planted fault and shows the full refusal (exit 1, both slots, both
modules, the IRI, nothing written). PR #376.
