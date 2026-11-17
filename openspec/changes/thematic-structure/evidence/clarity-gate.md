# Clarity gate: `thematic-structure` PLAN (design.md + tasks.md)

Full gate, 13 items, 6-criterion rubric. Scored cold by an attack-and-gate agent after the attack
fixes were applied. No shaper's self-score was recorded before this run.

## run 1, 2026-11-17, 9.0/10, pass

Attack findings folded into the PLAN before scoring (checked against the code with grimp and an
AST scan on 2026-11-17: the theme graph of PD-1 is acyclic, every hand-written module is placed):

- PD-2 placed settings in `adapters`, so `ToolkitSettings` (entrypoints) would import adapters,
  which `layers-across-themes` forbids. Rule refined (the lowest layer every user may import);
  `HttpSettings` → `core/services`, `JwksSettings`, `DirectorySettings` → `access/services`.
- PD-2 put `Page` in `tenancy`, but its `total` slot is the predicate `listing` (persistence) reads;
  moved to `persistence/services`. `LogContext` (otel-observability), `FusekiDataset`, the testkit
  group and `rp_wire`'s own `Any` were missing. Class and slot URIs kept (same `default_prefix`).
- PD-4: the model guard would have stopped seeing consumers' `RpModel` subclasses once `RpModel`
  moved (`FORBIDDEN_BASES` names the defining module); added PD-4 (a), TC-24, RISK-8. The guard
  had also been narrowed to `domain` only; its scope is restored.
- PD-4: the kind/folder check would fail stage 1 on the toolkit's own `technical/generated`
  targets; built in stage 1, wired in stage 7 (TC-72). Limited to the toolkit's run so no consumer
  breaks (RISK-9, open question).
- TC-06 could never pass (importing `rdf_persistence.core` runs the top package's eager imports);
  replaced by an AST check of the theme `__init__` files.
- TC-03 contradicted DEC-8 (`mint_aggregate_iri` changes object in stage 3); exception stated, in
  the spec delta too.
- PD-5: `tenant_resource_name` does not call `DEFAULT_IRIS`; the wrappers' users include
  integration, perf tests and `tests/toy_service.py`, now listed in task 3.1.
- PD-7: `_raise_for_status`/`_read_result` are module functions today; the `caplog` logger name in
  `test_fuseki_store.py` changes.
- The living rp-generation scenario "a hand-written domain class" names `rdf_persistence.domain`;
  a MODIFIED delta now covers it.

Gaps left (accepted under R-0005, not re-run):

- PD-2 and PD-3 rest on two sibling changes not yet merged (A-1, A-2); task 1.1 re-checks them.
  The proposal's A-1 still says four technical groups (the design now names six).
- TC-07's byte-identical TypeScript depends on the merge order of served schemas; the golden files
  decide, the mechanism is left to the implementer.
- Stages 5 and 6 carry few TCs of their own and rely on the per-stage TC-01/03/07/02 in
  Verification.

## run 2, 2026-11-17, 9.1/10, pass

Delta gate after the cross-change reconciliation (DEC-3, ASM-1..3, PD-1, PD-3..PD-6, tasks 1.1..1.3,
3.1, 5.1, 7.1, both spec deltas). Checked against the code: every hand-written module of
`domain`, `services`, `adapters`, `entrypoints` (62) is in PD-1's map; `pyproject.toml` has the
four targets TC-72 assumes; `guards.py` has `SCANNED_LAYERS`, `DEFAULT_ALLOW`, `FORBIDDEN_BASES`.
The MODIFIED requirements carry the texts of `technical-models` (technical models, target kind,
both earlier scenarios kept) and `generator-package` (layers, testkit and generator clauses kept).
Run 1's gap "A-1 says four groups" is closed (six groups, PD-1). Fixed in place: ASM-3 now names
the `telemetry` group and helper and `services/jsonld.py`; task 1.3 names the guard test's path
after `generator-package`. Left: the MODIFIED deltas modify requirements of unarchived changes,
so `technical-models` and `generator-package` must be archived first (archive order).
