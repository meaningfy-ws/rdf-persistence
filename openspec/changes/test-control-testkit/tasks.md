EPIC: test-control-testkit (proposal.md). Decisions: DEC-1 to DEC-10 (proposal), PD-1 to PD-15 (design.md).

> Derives from: EPIC `test-control-testkit`. Issue #403 and its OPEN-2.

Every task: test-first (the red test named, run and seen failing before the fix); task gate
`make test-changed check-quality`; commit body `Refs: test-control-testkit <task> <PD>`
(`Closes #403` on stage 1's last commit, the six findings being fixed there). Builders never
commit; the lead does and ticks this file. Branch per stage off `develop`:
`change/test-control-testkit-s<n>`, one PR each (DEC-9).

## 1. Stage 1: the six fixes, in place (#403)

- [x] 1.1 **#403-1, #403-5** (PD-5, PD-9), unit, `tests/changed.py`. Red: TC-1, TC-5 in
  `tests/unit/tooling/test_changed.py`. Then: hints before reasons in `main()`; `UsageError` from
  `_workers()`, caught first in `main()`, exit 2. Accept: both green, the rest of the file
  unchanged.
- [x] 1.2 **#403-3** (design.md PD-7, TC-3), unit, `tests/testmon_data.py`. Red: TC-3's
  three `seed` tests. Then the `seed -- <command…>` subcommand (clean, child pytest, `swap`).
  Accept: green; `swap` and `check` behave as before; `tests/queue.py` unchanged.
- [x] 1.3 **#403-2, #403-3, #403-4** (PD-6, PD-7, PD-8), Makefile + `test_lanes.py`. Red: TC-2,
  TC-3's lane test, TC-4. Then the recipes. Accept: `test_lanes.py` green;
  `make -n test-seed` shows the queued `seed --` line (worked example 1); `test-changed` exports
  `UV_NO_SYNC`; `CI=1 make -n lint 2>&1` prints no `uv`.
- [x] 1.4 **#403-6** (PD-10), docs + spec wording. `develop/testing.adoc#test-control`: per user;
  the seed cycle under the queue; no sync; the hints on fallback; the `PYTEST_CHANGED_N` rule.
  Accept: `make check-docs` green.
- [x] 1.5 **Lead**: `make check-all`; `make test-seed` then `make test-changed` on the branch
  (TC-13); review (one L1+L2 / L3+L4+L5 pair, P-0006); fix pass; PR; after the merge, post the
  stage-1 diff on MWB2 #129 (RISK-1).

## 2. Stage 2: the queue and the selection data move to the testkit

- [x] 2.1 **Model** (PD-2, DEC-8). `rp_testkit.yaml`: the enum `SelectionDataOutcome`, and,
  for stage 3, `ChangedSelection`, `ChangedTestsInvocation`, `ChangedTestsPlan` and
  `ChangedTestsLayout`, every multivalued slot `required: true`. The lead runs `make generate`.
  Accept: `make check-generated` green; model guard tests green.
- [x] 2.2 **Move** (PD-1, PD-11, PD-2's list of permitted body edits). `git mv` the two modules
  and their tests; change only what PD-2's list permits; point the Makefile, `tests/changed.py`
  and `test_lanes.py` at the new paths. Red: none (DEC-7: moved tests are the proof); the lead
  checks `git diff -M` against PD-2's list. Accept: moved tests green; `make test-changed` runs.
- [x] 2.3 **Module-name proof** (PD-12 a), TC-8 for `run_queue` and `selection_data`; the lead's
  wheel listing (PD-12 b).
- [x] 2.4 **Guard** (PD-13), TC-9: the `ast` import test. Accept: green;
  `make check-architecture` green.
- [x] 2.5 **Public surface + docs** (PD-14, PD-15 for the two modules): `make refresh-snapshot`
  (lead), the user-manual section (queue and seed part), `questions.adoc`, CHANGELOG.
  Accept: `make check-docs` green.
- [x] 2.6 **Lead**: as 1.5 (no MWB2 post).

## 3. Stage 3: the changed-tests planner moves to the testkit

- [ ] 3.1 **Generic planner** (PD-3, PD-9), `rdf_persistence/testkit/changed_tests.py`. Red:
  TC-11, with the generic cases of `test_changed.py` re-pointed at a fake classifier and layout
  (git, plan, exit codes, lock, fallback, hints). Then the module, from `tests/changed.py`'s
  generic functions, with the generated types. Accept: green; RISK-3's equal-output test is
  green.
- [ ] 3.2 **Our classifier** (PD-4). Reduce `tests/changed.py` to the classifier and `LAYOUT`;
  `tests/unit/tooling/test_changed.py` keeps only the layout cases (TC-12), unchanged in what they
  assert. Accept: TC-12 green; the `THEMES` and `IGNORES` importers unchanged and green.
- [ ] 3.3 **Module-name proof** for `changed_tests` (TC-8, PD-12), and the `ast` import test
  covers it (TC-9).
- [ ] 3.4 **Docs** (PD-15): the user manual's minimal classifier example; `testing.adoc` names the
  module; `make refresh-snapshot` (lead). Accept: `make check-docs` green.
- [ ] 3.5 **Lead**: as 1.5; after the release that carries it, the adoption comment on MWB2 #129
  (DEC-10).

## 4. Close

- [ ] 4.1 Lead: reconcile `proposal.md` with what was delivered; tick the roadmap; archive.

## Roadmap

- [x] 1.1 · [x] 1.2 · [x] 1.3 · [x] 1.4 · [x] 1.5
- [x] 2.1 · [x] 2.2 · [x] 2.3 · [x] 2.4 · [x] 2.5 · [x] 2.6
- [ ] 3.1 · [ ] 3.2 · [ ] 3.3 · [ ] 3.4 · [ ] 3.5
- [ ] 4.1

## Verification

`make check-all` green at each stage end; `make test-seed` then `make test-changed` on each
stage branch; `openspec validate test-control-testkit` green.
