## 252
`review-floors` (PRs PRLIST) delivered this issue's behaviour-preserving items: e (`more_count` beside `hidden_count`), f (import contract), g1, g2, g4, h1, h2, h3 (docstrings and the slug text), i1, i2 (shared test helpers), j1, j2 (characterisation tests).

What stays here (the owner's answers to OPEN-1/OPEN-2 in `openspec/changes/review-floors/inputs/qa.md`):
- a (`_types_of` of an untyped root), d (`Aggregates.remove(readable)` keyword-only), g3 (the `InUse` message's number): behaviour changes, for a follow-up `floor-behaviour-fixes` EPIC.
- b (generic DELETE opens a collaboration for every class), c (diagnosis reads every row): query-changing, until a profile shows their cost.

## 235
`review-floors` (PRs PRLIST) delivered m1 and m2 (the collection check takes one value; `_exact_heads` is a module function), and o2 (a test that a sub-collection held by two nesting parents is allowed), plus five adversarial probes of the refactor.

What stays here:
- k (the D-5 race) and l (T-4, T-5, T-6, still strict xfails): a later EPIC on the nesting guards (OPEN-3).
- n (C-1, one `graphs_with` per replace): query-changing (OPEN-2).
- o1 (a subclass of a collection class nested in its parent): needs a toy model change (rabbit-hole).

## 215
Closed by `review-floors` (PRs PRLIST):
- W2b: the slow-lifespan test, with the `rp-testkit` scenario for start-up.
- W5: the testkit root's lazy-import check.
- S4a: the several-streams note in `test.adoc`.
- S5: `re.escape`.

W2a and S1-S3 were already done (test-debt-paydown PD-16). S4b (set the lifespan flag earlier) is not done, by the owner's answer to OPEN-7: the docs note covers it.

## 214
`review-floors` (PRs PRLIST) documented today's outcomes of `open_event_stream` in `user-manual/test.adoc` (214-g). The public way to wait for a follower (214-f) stays here, for its own SMALL EPIC (OPEN-4).

## 192
`review-floors` (PRs PRLIST) delivered:
- b: the stored-file class computed once per caller.
- e: `toolkit_roots()` as the one reader, with a guard test.
- f: one `is_generated_with` predicate.
- g: one home per constant (names only).
- h: the test-only vocabulary moved to `tests/schema_helpers.py`.
- i: assertions split, with messages.
- j2: the theme map on the generator side, `tests/generator/theme_map.py`. The two library-side places keep their own reading, because the library/generator test guard forbids the import (D-5).
- k: each theme's `domain/generated/` is pinned.
- m: the repeat of `themes-ordered` is dropped.

j1 and l were already done.

What stays here:
- a: the E-2 closure check, a behaviour change (OPEN-1).
- c: the theme-target flag and the partial artefacts (OPEN-6).
- d: honouring `--project` (OPEN-6).
- g: the resolved-path comparison (OPEN-6).

## 189
`review-floors` (PRs PRLIST) delivered:
- p: the redundant `TargetKind()` is removed.
- q: the spec scenario's wording.
- r: one assertion per step.
- s: layered packages in the config tests.
- t: the getting-started cold read.
- u: the route-shapes rule and the OpenAPI source, in `model.adoc` and `generate.adoc`.

What stays here: n (the theme failure names the derived kind) and o (the `, ` separator), for the `floor-behaviour-fixes` EPIC (OPEN-1). The TypeScript re-emission (v) is split into NEWISSUE (OPEN-5).

## 125
`review-floors` (PRs PRLIST) delivered:
- i1: a test that fails without `relay.wake()`.
- i2: a Redis test of redelivery by `claim_idle` within one run.

h6 and j were already done.

#125 stays open, as triaged on 2026-11-16, for h1-h5 (outage backoff, resume paging, stream caps, hub offered after publish, shutdown). It also holds i3 (stopping the Redis broker mid-test), which is a rabbit-hole: a restarted testcontainers broker gets a new mapped port, so the bus under test cannot reconnect (OPEN-8).

## 272
Closed by `review-floors` (PRs PRLIST):
- a: `tests/unit/tooling/test_patch_markers.py`, with the four unmarked patches marked; one tripwire became a pass-through spy, so its `# X2` fits rule 3 as written (D-9).
- b: `tests/library_app.py`.
- c: `load_warm_shapes`.
- d: `book_json()`.
- e: `FAST_POLL`.
- f: the toy vocabulary in `tests/toy.py`.

## 273
Closed by `review-floors` (PRs PRLIST): `develop/testing.adoc` rule 3 now says a planted mutation in a generated file needs `-p no:rdf_persistence_generation.testkit.freshness`.

## 275
Closed by `review-floors` (PR PRS1): one `TenancyDouble` in `tests/unit/api/iri_policy_helpers.py`. `test_tenancy_double.py` fails, naming the parameter, when `Tenancy.tenant_session` gains a keyword the double lacks.
