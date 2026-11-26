# Timing: the shared service view (task 1.2, RISK-3)

2026-11-26, the lead, through the queue, one process:
`TEST_QUEUE_LABEL=timing uv run python -m rdf_persistence.testkit.run_queue -- /usr/bin/time -v pytest tests/unit/api/test_allowed_actions_adversarial.py -n 0 --no-cov -p no:randomly -q`

| Side | Commit | Wall time | Maximum RSS |
|---|---|---|---|
| before (no `service_view`) | `8510ab6c` (stage, task 1.3 only) | 1:11.88 | 265,216 kB |
| after (`service_view`, tasks 1.1, 1.2 A) | stage head after 1.2 part A | 1:10.05 | 268,556 kB |

−2.5 % wall time, +1.3 % RSS: within noise, and far from RISK-3's 10 % threshold. As RISK-3
predicted, the plugin's per-test clearing of `SchemaView` caches leaves little to gain in a module
that builds one service; the gain is in suites that build many services from one file.

## The view-modification scan (task 1.2, before the change)

`ast-grep` for `$K.view.$M(...)`: nine matches, all reads (`get_class`, `get_uri`,
`class_induced_slots`). The only `add_slot`, `add_class` and `.slots.append` calls in the tests
(`tests/unit/persistence/test_listing.py:415`, `tests/generator/unit/test_conformance.py:218`)
already work on their own `load_schema`. No test needed switching.
