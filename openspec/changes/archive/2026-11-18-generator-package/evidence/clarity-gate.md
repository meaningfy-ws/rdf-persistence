# Clarity gate: generator-package (design.md + tasks.md)

No shaper self-score was recorded here; the runs below are the first gate, by a cold reader after
the attack (epic-planning step 7).

Attack fixes applied before run 1: PD-1 follows `technical-models` PD-11 (package
`rdf_persistence.testkit.generated`; only `ExecResult`, `FusekiServer`, `GarageServer` left to
move); PD-5 names the nine real call sites and an ast-grep test for `roots=`; PD-6 reads
`python_package` from the imported `SchemaDefinition` and covers `rp_generation.yaml` and the
`testkit` group; PD-9 `TOOL_USERS` for the eight library tests that use the generator as a tool,
the shape test's `generation` parameter split out, e2e row stamped `STORE, FILES, IDENTITY`;
PD-10 the stale paths (`Makefile:93,96`, `ruff.toml:61`, `.pre-commit-config.yaml:24`) and a
closing grep; PD-13 the three containers; task 2.2 path of `test_testkit_lazy_import.py`;
TC-44, TC-45, TC-48 made exact; RISK-8, RISK-9; the BREAKING import path in proposal What Changes.

## run 1, 2026-11-17, 8.9/10, pass

Rubric: actionability 9, specificity 9, consistency 8, structure 9, disambiguation 9,
reference clarity 9. Pass under R-0005 (≥ 8.8); not re-run.

Gaps (left open, for the developer):

- Consistency: proposal DEC-4 places the testkit records in
  `rdf_persistence/technical/generated/testkit/`; design PD-1 follows `technical-models` DEC-2
  (`rdf_persistence/testkit/generated/`). A DEC may not be changed by the gate; the developer
  confirms PD-1 or overrules it.
- Task 1.1 depends on what `technical-models` actually merges (its record list omits three
  records its own TC-50 needs moved). Bounded by RISK-8 and TC-01/TC-02, which are stated over
  the imports, not a fixed list.

## run 2, 2026-11-17, 9.2/10, pass

Re-run after the cross-change reconciliation. Rubric: actionability 9, specificity 9,
consistency 9, structure 9, disambiguation 9, reference clarity 10. Both run 1 gaps closed:
DEC-4 now names `rdf_persistence/testkit/generated/` as PD-1 does; the ten records and the
`ConstraintCase`/`ConstraintKind` exception match `technical-models` task 4.1, TC-50, TC-51 and
the imports in `rdf_persistence/testkit/` on 48f80c6. The "Layers import downward only" delta
chains from `technical-models`' text, changing only the `generation` clause. Fixed in the run:
TC-01 excluded `roundtrip.py` and `strategies.py` too, unlike PD-1, TC-50 and the task 1.2
contract (they import the generator only through `conformance`); PD-1 said "imports
`rp_generation`" where TC-01 tests every import from `rdf_persistence.generation`.
