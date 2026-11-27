# Clarity gate: typescript-toolkit-modules PLAN

EPIC readiness check (lightweight), 2026-11-27, planner: pass. Appetite, why, outline, DEC-1 to
DEC-6, rabbit-holes and no-gos are present; the owner answered one round (`inputs/qa.md`); four
planner's choices (P1 to P4) are recorded there for the owner to overrule.

Attack and gate: pending (a fresh reviewer, dispatched by the lead).

run 1, 2026-11-27, 8.7/10, fail

Rubric: actionability 9, specificity 9, consistency 8.5, structure 9, disambiguation 8, reference
clarity 8.5. Verified against code: nested folders (`_specifier`/relpath), stale removal
(`pipeline._remove_stale` per target manifest), target order (all staged before publish), the
toolkit's own `pyproject.toml` (no `typescript`), existing tests that write `pyproject.toml` (none
leaves two TypeScript entries without the domain entry), the toy trees (domain holds all eight
metamodel modules; value lacks `rp_collections`, so TC-2 holds). No blocking counterexample.

- RISK-2's mitigation is vacuous on the toy: the domain owner's closure already renders all eight
  shared modules, so `setdefault` never lets a metamodel-root render reach a committed file and TC-3
  proves nothing about it. `apply_defaults` runs `prefer_application_slots` on the consumer's view,
  so the two renders can differ. Fix (design.md TC-2): also assert that `_file(m)` for every `m` in
  `_shared_modules()` equals the toy domain tree's committed `rp_<x>.ts`.
- PD-3 does not say which render wins when the metamodel root and a served root both yield a
  module (`rp_core`, `rp_access`, `rp_tenancy` come from both). Fix: "metamodel modules first, then
  served modules by `setdefault`".
- PD-4 says "PD-2 guarantees one", but a `Run` built without `read_targets` (tests, `run_toy`
  with hand-made targets, e.g. `test_the_runs_own_package_is_never_an_owner`) can hold two
  TypeScript targets and no owner; behaviour (StopIteration?) is unstated. Fix: return `None` when
  no target sets the key, or raise `ConfigError`; add the row to the error matrix and TC-5.
- PD-5 tells owner from importer by `toolkit == folder` (path equality); two entries sharing one
  folder, or spellings `Path` does not normalise (`a/../a`), misclassify. Fix: decide the role from
  `run.target.toolkit_typescript`, pass `toolkit` only to importers.
- RISK-1 names only `tsc` breakage; on upgrade PD-2's refusal also stops every consumer test
  session (freshness plugin, `steps._toolkit_packages`/`_metamodel_root_names` call
  `read_targets`) until the key is set. Fix: say so in RISK-1 and the CHANGELOG migration note
  (PD-9).
- PD-8 says "task 1.1 checks it" (domain closure holds the whole shared set); task 1.1's Accept
  omits it, task 1.4 carries it. Fix: drop "task 1.1" from PD-8 or add the check to 1.1.
- Spec delta has no scenario for "key on an entry without `typescript`" though the requirement and
  TC-6 cover it. Fix: add the scenario in `specs/rp-generation/spec.md`.
- tasks.md cites PD ids, not `design.md#pd-n` anchors (item 12); same as the precedent, minor.
- Consumer note (D-12 handoff, not a PLAN defect): MWB2's `frontend/src/services/generated` still
  holds `fragment_checks.ts`, so MWB2 is not yet on #371; it imports `TenantSummary`,
  `InUseProblem` and others from importer folders, which this change breaks (RISK-1, as expected).

run 2, 2026-11-27, 8.9/10, pass (R-0005: 8.8 accepted; fold the new gap in before 1.3)

Rubric: actionability 9, specificity 9, consistency 8.5, structure 9, disambiguation 9, reference
clarity 8.5. Verified: `Run.target` is a `GenerationTarget` (flags-only runs default the new slot to
`False`); manifests are per target (`manifest_path` under the python folder); `_publish` deletes a
previous output not in *this target's* written set.

- RISK-2 / TC-2: closed (TC-2(b) compares `_file(m)` of every shared module and `rp_service.ts` with
  the committed domain tree). Residue: RISK-2 still says "a difference fails task 1.1"; 1.1 renders
  nothing, it is TC-2 in 1.3 and the byte check in 1.4.
- PD-3 precedence: closed (metamodel first, served by `setdefault`).
- PD-4 no owner: closed (`None`, error-matrix row, TC-5). TC-5 omits the hand-built "several owners"
  case PD-4 names; minor.
- PD-5 role by folder equality: closed (`owns_toolkit` from `run.target.toolkit_typescript`; alias
  `toolkit-typescript`, field `toolkit_typescript`, parameter `owns_toolkit` are consistent).
- RISK-1 test sessions: closed (RISK-1 and the PD-9 CHANGELOG note).
- PD-8 task 1.1: closed (now task 1.4).
- Spec scenario for key without `typescript`: closed.
- `design.md#pd-n` anchors: open, accepted as minor (precedent).
- NEW: the shared-folder row (PD-5, error matrix, TC-5) is not true on upgrade. Before the change
  the importer's manifest records `rp_core.ts` etc. in the shared folder; after it, the importer
  writes none, so `_publish` treats them as its stale outputs and `_remove_stale` deletes the
  owner's freshly published file (same hash) whenever the importer publishes after the owner. Fix:
  in PD-7, compute `kept` over every target's written files in the run (pass the union to
  `_publish`) and add the case to TC-7; or drop the row and refuse two TypeScript entries sharing
  one folder in PD-2.
