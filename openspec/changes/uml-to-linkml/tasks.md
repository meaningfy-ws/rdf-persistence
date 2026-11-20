EPIC: uml-to-linkml (proposal.md), issue #196. Decisions: design.md PD-1 to PD-34, DEC-1 to DEC-6.

> Derives from: EPIC `uml-to-linkml` ([proposal.md](proposal.md)); design [design.md](design.md).

Every task: tests first (the failing test named in the task is written and seen red before the
code); tier and file as in [design.md#test-specifications](design.md#test-specifications); task gate
`make test-changed check-quality` (`make test-fast check-quality` for 1.7, which touches a library
fixture); commit body `Refs: uml-to-linkml <task> <PD>`. Builders never commit; the lead does. A
schema change and its regenerated code go in one commit (`make generate`, then the lead's
`make check-generated`). Fixtures use the generic `lib:` library model only.

## 1. Stage 1: the reader and the plain UML rules (R-1..R-13, R-19)

- [x] 1.1 Records (PD-2): add the `Uml*` classes, `UmlSettings`, `ReportLine` and the enums
  `UmlRule`, `UmlLinkKind`, `ReportKind` to `rdf_persistence_generation/model/rp_generation.yaml`
  (title, description, IRI per element, `meaning` per value); `make generate`. Failing test first:
  `tests/generator/unit/test_uml_records.py` asserts every `UmlRule` value names its R-n in its
  description (`no_rule` and `activity_root` excepted) and that the set of `UmlRule` values equals
  the 24 values listed in design.md PD-2, written out in the test. Accept: test green; `make check-quality` green.
- [ ] 1.2 Fixture builder (PD-24), after 1.1: `tests/generator/uml_qea.py` with `EA_COLUMNS`, the
  DDL and the builder API. Failing test first: TC-12 and a round trip (build, reopen read-only,
  count rows). Accept: TC-12 green; no `.qea` file under `tests/`.
- [ ] 1.3 Reader (PD-3, PD-4), after 1.2: `rdf_persistence_generation/uml/qea.py`. Failing tests
  first: TC-1, TC-2, TC-3 and the matrix's exit-2 rows for the file, tables, columns and
  `--package`. Accept: those green; `make check-architecture` green with `uml` added to the
  contract `works-without-the-generate-extra` (`.importlinter`).
- [ ] 1.4 Naming (PD-6, PD-10 keys, PD-12 plural), in parallel with 1.3:
  `rdf_persistence_generation/uml/naming.py`. Failing test first: TC-4. Accept: TC-4 green.
- [ ] 1.5 Plain rules (PD-5, PD-7..PD-13, PD-15, PD-16 single-package part), after 1.3 and 1.4:
  `classes.py`, `slots.py`, `convert.py`. Failing tests first: the rows of TC-5 for R-1..R-13 and
  R-19, each with its failure branch, and TC-9's same-package half. Accept: those rows green;
  `test_every_uml_rule_has_a_row` lists only stage-2 rules as missing (marked `xfail(strict=True)`
  with "stage 2" until 2.6).
- [ ] 1.6 Writer and command (PD-22, PD-23, PD-1), after 1.5: `write.py`, `cli.py`, the console
  script in `pyproject.toml`, `uml_` added to the `-k` of `make refresh-golden`, the stage-1
  golden under `tests/generator/fixtures/uml/golden/`. Failing tests first: TC-10, TC-11,
  IT-1 (lint and boundary steps). Accept: green; `uv run rp-uml2linkml --help` exits 0.
- [x] 1.7 SPIKE-1 (DEC-4), independent of 1.1..1.6 (disjoint files), run beside 1.3..1.5, in this
  order: (a) write the S-2 row in `test_hard_check.py`,
  `tests/unit/services/test_activity_root.py` (S-3..S-5) and
  `tests/unit/entrypoints/test_activity_root_routes.py` (S-6), importing `Review` from the toy's
  generated package; run them and see them fail (S-2 on the missing class, S-3..S-6 on the
  `ImportError`); (b) add `Review` to `tests/fixtures/library/books_activities.yaml`; (c)
  `make generate` and the refreshes of RISK-7; (d) run the tests again: no file under
  `rdf_persistence/` may change to make them pass. Accept: the verdict (pass or the
  first failing S-id) in `evidence/spike-dec4.md`; no file under `rdf_persistence/` changed; on
  fail, the toy change reverted and the tests kept as `xfail(strict=True)` with the reason.
- [ ] 1.8 SPIKE-2 (PD-14), after 1.6: `tests/generator/integration/test_uml_cycle.py` (IT-2).
  Accept: the verdict in `evidence/spike-cycles.md`.
- [ ] 1.9 Lead: both verdicts and the PD-14 choice in design.md `## Delivery decisions`; stage
  gates `make check-all` and `make test-containers`; one L2+L3 pass; fixes; the stage PR, merged
  on green CI.

## 2. Stage 2: the toolkit-aware rules (R-15, R-18, R-20..R-29)

- [ ] 2.1 Lead: freeze the rule table (DEC-5): rules R-30… received since the PLAN appended with
  source and stage, or sent to a follow-up issue; the freeze date written under the table; any new
  rule's `UmlRule` value added (with 1.1's test updated).
- [ ] 2.2 Toolkit index (PD-17, PD-18, PD-20 lookups): `uml/toolkit.py`; `_segment_pattern`
  renamed `segment_pattern` in `checks/hard.py` and its callers. Failing test first:
  `tests/generator/unit/test_uml_toolkit.py`: class annotations = the seven of F-1;
  `prov:Activity` → `Activity`, non-mixin; `skos:prefLabel` → `label`; `dcterms:identifier` not
  offered (it is `id`); `started_at_time` toolkit-filled. Accept: green; `make check-architecture`
  green (else the matrix's fallback module).
- [ ] 2.3 Mixins (PD-17, R-25..R-28) and the DEC-4 branch, after 2.2 and 1.9. Failing tests first:
  the TC-5 rows for R-25..R-28, the PD-17 conflict rows, and the `activity_root` row (active only
  if SPIKE-1 failed). Accept: green.
- [ ] 2.4 Toolkit slots (PD-18, R-15, R-22), after 2.2: failing test first TC-6. Accept: green.
- [ ] 2.5 Tagged values and keys (PD-20, PD-21, R-20, R-21), after 2.2: failing tests first TC-7,
  TC-8. Accept: green.
- [ ] 2.6 Tenant root, abstract roots, cross-package slots, left-out links (PD-19, PD-16 R-24,
  PD-15 R-29, PD-14 as decided in 1.9), after 2.3..2.5: failing tests first the TC-5 rows for
  R-18, R-23, R-24, R-29 and TC-9's cross-package half; the stage-2 golden (the fixture of the
  design's worked example); IT-1 with all four steps; IT-3 (`uml_import.feature`, the spec
  delta's scenarios, the activity-root one as amended for PD-26). Accept: all green;
  `test_every_uml_rule_has_a_row` without `xfail`.
- [ ] 2.7 Docs (PD-25), in parallel with 2.6: the how-to page, `nav.adoc`, `questions.adoc`,
  the `architecture/generation.adoc` line, `specs/rp-generation/spec.md` (MODIFIED delta).
  Accept: `make check-docs` green; `openspec validate uml-to-linkml --strict` green.
- [ ] 2.8 Lead: full gates; the appetite's full review (P-0005); fixes; acceptance demo: the
  converter on the consumer's real `.qea`, read-only, output in `temp/` and never committed,
  showing exit code, problem count by rule and report count by kind; PR, CI green, merge; owner's
  acceptance; archive.

## Roadmap

1.1 → 1.2 → (1.3 ∥ 1.4 ∥ 1.7) → 1.5 → 1.6 → 1.8 → 1.9 → 2.1 → 2.2 → (2.3 ∥ 2.4 ∥ 2.5) →
(2.6 ∥ 2.7) → 2.8

## Verification

`make check-all`, `make test-containers` and `make test-generator` pass; the golden test is
byte-identical on a second run; `openspec validate uml-to-linkml --strict` passes; the PLAN's
clarity gate is logged in `evidence/clarity-gate.md`.
