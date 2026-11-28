# Clarity gate: aggregate-composition

run 1, 2026-11-28, 8.3/10, fail

Scope: the PLAN (`design.md` + `tasks.md`), read against `proposal.md` (DEC-4 re-shaped),
`inputs/qa.md`, `evidence/attack.md`, `specs/rp-uml-import/spec.md`, `features/*.feature`.
D-1..D-4 are taken as decided. Code claims spot-checked in this worktree and found true:
`links.py` `_is_owned`/`owned_pairs`/`_boundary_pairs`, `classes.py` `_check_root_paths` inside
`collect_elements`, the literal `no-note` at `classes.py:374`, `slots.py` `described` (l.362),
`qea.py` `LINK_KINDS`, `_Boundaries`, `RectTop`, `_outside_rows`, `checks/hard.py`
`ALLOWED_ANNOTATIONS`, `tags._ANNOTATION_NAMES` (every `RpAnnotation`), `convert._module_kinds`
needing the `Layout`, the report format `<kind>\t<element>\t<message>` (`write.py`), `cli.py`
`--out` required today, and every test file the tasks name.

## Checklist (13 items)

| # | Item | Score | Note |
|---|---|---|---|
| 1 | Actionable | 9 | each PD names module, function, record and finding |
| 2 | Current | 7 | D-4 not carried into PD-1, RISK-9, task 1.0 and the roadmap (G-2) |
| 3 | Single source | 7 | the empty-`SubType` rule is stated five ways, in conflict (G-1) |
| 4 | Decision, not wish | 8.5 | task 1.3 "or the test of `RpAnnotation` values"; RISK-9 "decided after that record" (G-1, G-9) |
| 5 | Prompt-ready | 9 | tasks carry tier, file, first failing test, accept line |
| 6 | No future state | 9 | |
| 7 | No fluff | 9.5 | the "Kept from the first draft" bullet is residue (G-9) |
| 8 | Type identified | 10 | both files headed as the PLAN halves |
| 9 | Anti-patterns placed | 10 | 9 rows, change-specific (LARGE minimum 5) |
| 10 | Test cases placed | 8 | the developer's EA probe (D-4, RISK-9) is a manual check with no `@manual` scenario (G-7) |
| 11 | Error handling placed | 9 | 48 rows; one row lacks its condition (G-9) |
| 12 | Deep links | 6 | tasks cite `PD-n` with no `design.md#pd-n` anchor; PDs have no anchors; `[D-4](design.md)` has none (G-3) |
| 13 | No duplication | 8 | PD-2 contradicts EPIC DEC-2 with no amendment logged (G-5) |

Worked examples: 2, below the LARGE minimum of 3 (G-6).

## Rubric

| Criterion | Weight | Score | Weighted |
|---|---|---|---|
| Actionability | 0.25 | 9.0 | 2.25 |
| Specificity | 0.20 | 8.3 | 1.66 |
| Consistency | 0.15 | 7.5 | 1.13 |
| Structure | 0.15 | 8.8 | 1.32 |
| Disambiguation | 0.15 | 8.7 | 1.31 |
| Reference clarity | 0.10 | 6.5 | 0.65 |
| **Total** | | | **8.3** |

Below the 8.8 the owner accepts: revise and re-score (run 2).

## Gaps

- **G-1** (PD-1, error matrix, RISK-9, D-4, tasks 1.0/1.4) — the empty-`SubType` rule
  contradicts itself. PD-1 and the error matrix make an empty `SubType` a `no_rule` problem; RISK-9
  says it is decided after the EA record; D-4 says "an empty `SubType` with a 2 follow PD-1" (so: a
  problem) while the only observed EA rows (composite associations) have `SubType` empty and D-4
  tells fixtures to "copy the observed column values", which belong to Associations, not
  Aggregations. If EA writes Aggregations like that, every composition is refused. **Fix:** decide
  once in PD-1: the end column holding 2 decides the whole; an empty `SubType` is accepted; the
  cross-check applies only when `SubType` is `Strong` or `Weak`; any other non-empty value is
  `no_rule`. Reword the error-matrix row and D-4, and state the exact `QeaBuilder.aggregation`
  columns (`Connector_Type`, `SubType`, `SourceIsAggregate`, `DestIsAggregate`) for both drawings.
- **G-2** (PD-1, RISK-9, task 1.0, roadmap) — D-4 superseded parts of them but they still say it:
  PD-1 "Task 1.0 verifies … before any fixture is written"; task 1.0 still has the developer draw
  the scratch `.qea` and settles PD-1 "from it"; the roadmap note says "1.0 needs the developer and
  gates 1.4"; RISK-9's mitigation is the pre-1.4 probe. **Fix:** task 1.0 = read Sparx's
  `t_connector` docs and record what is known in `evidence/ea-connectors.md`; move the developer
  probe to the acceptance task (stage 1 or 3.6) with its accept line; update PD-1, RISK-9 and the
  roadmap note.
- **G-3** (tasks.md throughout, design.md Decisions) — no deep links. **Fix:** give every PD,
  D-n and RISK an anchor (`<a id="pd-1"></a>` or a heading per decision) and cite
  `design.md#pd-n` in each task; link `features/<file>.feature` scenarios and
  `specs/rp-uml-import/spec.md#<requirement>` where a task appends them.
- **G-4** (PD-13, task 2.4, error-matrix preamble) — `CONVENTION_KINDS` is "the new presentation
  kinds plus …", not a list, yet 2.4 tests it holds "exactly the kinds of PD-13". Whether
  `deprecated_root` and `boundary_disagrees` fail `--check` is implied only by the error-matrix
  preamble. **Fix:** enumerate the frozenset: `deprecated_root`, `boundary_disagrees`,
  `composition_named`, `aggregates_diagram`, `composition_diagram`, `unprefixed_name`,
  `unused_enumeration`, `drawn_toolkit_parent`, `tenant_required_pointer`, `no_note`,
  `unspecified_multiplicity`, `implicit_meaning` (or as decided), and say in PD-14/migration that a
  model still drawing agreeing «root» fails `--check` until step 5.
- **G-5** (PD-2, Open Questions) — EPIC DEC-2 says "one with two candidates is a problem"; PD-2,
  the spec and composition.feature accept two candidates when the composition names a role (A-3).
  "No other row needed an EPIC change" is untrue. **Fix:** log a DEC-2 amendment in `inputs/qa.md`
  and `proposal.md` as for DEC-4 (or record it as D-5 for validation); while there, the EPIC's
  Impact line "new link kind" contradicts PD-1's rejected `UmlLinkKind.composition`.
- **G-6** (Algorithm, worked examples) — 2 examples, LARGE needs 3. **Fix:** add one showing the
  shared/recursive case end to end: `Book ◆ Section`, `Section ◆ Section`, `Journal ◆ Section`,
  a pointer `Reader.cites → Section`, with the `UmlPartOf`/`UmlReach` rows, the `root` lines, the
  pointer problem, and the `--check` stdout and exit code.
- **G-7** (D-4, RISK-9, features) — the developer's EA probe is a manual acceptance check with no
  `@manual` Gherkin. **Fix:** add a `@manual` scenario to `features/composition.feature` (draw one
  composition each way and one shared aggregation in EA; convert; expect the same whole and the
  shared refusal) and cite it from the acceptance task.
- **G-8** (PD-19, PD-19a, task 1.7) — `check_pointers(...)` has no signature and no module (PD-19
  lists it beside `conventions.py`, task 1.7 tests it in `test_uml_aggregates.py`);
  `convention_lines` takes `usages` (`slots.Usage`, not a generated record), which PD-19a's
  signature test must allow. **Fix:** give `check_pointers`'s module and full signature; state that
  `Usage` inputs are allowed by the signature test (only `Context` is forbidden).
- **G-9** (small, fold in) — task 1.3: drop "(or the test of `RpAnnotation` values)",
  `tests/unit/schema/test_schema_structure.py` exists; error-matrix row "Composition, two such
  associations" add "and no role on the composition"; PD-12: say an aggregates diagram is
  recognised by the suffix ` · aggregates` before the package-name prefix is checked; order the
  Decisions by id (PD-17 sits after PD-20) and fold "Kept from the first draft" into "Left open of
  #343"; list task 1.0 before 1.1.

---

run 2, 2026-11-28, 9.2/10, pass

Read only the gaps of run 1 and the sections they name.

| Criterion | Weight | Score | Weighted |
|---|---|---|---|
| Actionability | 0.25 | 9.3 | 2.33 |
| Specificity | 0.20 | 9.2 | 1.84 |
| Consistency | 0.15 | 8.8 | 1.32 |
| Structure | 0.15 | 9.2 | 1.38 |
| Disambiguation | 0.15 | 9.3 | 1.40 |
| Reference clarity | 0.10 | 9.3 | 0.93 |
| **Total** | | | **9.2** |

| Gap | Status | What remains |
|---|---|---|
| G-1 | closed | D-5 settles it: the end columns decide and `SubType` is not read. PD-1 gives the exact `QeaBuilder.aggregation` columns for both drawings and for shared. The error matrix and RISK-9 agree. |
| G-2 | closed, residue | Task 1.0 gates nothing, the probe is the `@manual` scenario of 1.12, and PD-1, RISK-9 and the roadmap are updated. Residue: D-4 still ends "Fixtures copy the observed column values", which contradicts its own earlier sentence "Fixtures use the columns PD-1 states". Delete the last one. |
| G-3 | closed | Every PD, RISK and D has an anchor; tasks cite `design.md#…` (31 links). |
| G-4 | closed | `CONVENTION_KINDS` is enumerated (eleven). `deprecated_root` is decided as informational, with the reason given (CI stays green through migration steps 1–4). |
| G-5 | closed, residue | D-6 records the amendment, `inputs/qa.md` logs it, Open Questions corrected, EPIC Impact line corrected. Residue: `proposal.md` DEC-2 (l.63) still says "and so is one with two candidates" with no amendment marker, unlike DEC-4. Annotate it. |
| G-6 | closed | Worked example 3: recursion, a shared part class under two tops, the pointer refusal, `UmlAggregates` rows, `--check` output and exit code. |
| G-7 | closed | `@manual` scenario "An EA-drawn composition reads the same either way" in `features/composition.feature`, run in task 1.12, excluded from 1.10. |
| G-8 | closed | The five pass signatures with module and types; `Usage` allowed, only `Context` forbidden; PD-19a's test matches. |
| G-9 | closed | Task 1.3 alternative dropped; error-matrix row reads "and no role on the composition"; PD-12 recognises an aggregates diagram by suffix first; PDs in order; "Kept from the first draft" gone; 1.0 listed before 1.1. |

The two residues are one-sentence edits; fold them in (R-0005), no re-run.

accepted: run 2 passes at 9.2; the two leftovers (G-2 D-4 sentence, G-5 DEC-2 marker) fixed by the lead, 2026-11-28, no re-run (R-0005).
