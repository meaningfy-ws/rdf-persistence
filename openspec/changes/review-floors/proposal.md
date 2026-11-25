<!-- Parents: the review findings left under the floor by seven delivered changes, filed as issues
     #252, #235, #215, #214, #192, #189 and #125 (inputs/seed.md, verbatim), and the owner's scope
     for this EPIC: behaviour-preserving tidy-ups first; every behaviour-changing item split out. -->

# EPIC: Pay the review floors that keep behaviour

**Golden-thread parents:** the "under the floor" and Delivery decisions of the archived changes
`2026-11-21-delete-refuses-referenced` (#252), `2026-11-21-nested-collections` (#235, D-3 to
D-5), `2026-11-20-testkit-event-stream` (#215, #214), `2026-11-19-domain-model-per-theme` (#192),
`2026-11-19-target-kind-from-the-model` (#189) and `2026-11-16-aggregate-events` (#125); the
follow-ups that `2026-11-21-test-debt-paydown` deferred (#272, #273) and that
`2026-11-21-aggregate-validators` found (#275), folded in by the owner on 2026-11-25 (DEC-6); the
capabilities `rp-generation` and `rp-testkit` (spec deltas of wording and of today's behaviour
only).

## Appetite

**MEDIUM.** About fifty small items across three areas, each one reused as is: no new concept,
no new capability. The re-triage of 2026-11-25 found none of them fixed since 2026-11-22. Three stages, one pull request each (`develop/agents.adoc`, *Merge and
release*).

## Why

Seven delivered changes left about seventy review findings under the floor, filed as seven
issues. They mix three kinds of work: tidy-ups that keep behaviour (structure, tests, docs), fixes
that change what a caller sees, and load work that waits for a consumer. While they sit together,
none closes, and the next change that touches the same code meets the same findings again. This
EPIC takes the first kind, all of it, and sends the rest to named homes, so each issue ends this
EPIC either closed or holding only behaviour-changing items. Three more issues hold test debt of
the same kind, deferred by `test-debt-paydown` (#272, #273) and found in `aggregate-validators`
(#275). They touch the same test helpers (`tests/toy.py`, the API test doubles), so the owner
folded them in (DEC-6), and all three close with this EPIC.

## Solution outline

1. **Triage, recorded:** every item of the ten issues has one class in `inputs/triage.md`:
   preserving (in scope), behaviour-changing (out, with a follow-up home), query-changing (out),
   rabbit-hole (out) or already done. It was re-checked on 2026-11-25: no item was fixed since.
2. **Stage 1, persistence, collaboration and the test helpers (#252, #235, #272 b/d/e/f, #275):** characterisation tests first (a
   `KeyConflict` wins over an `InUse`; the type read is skipped when no link names a removed root;
   a sub-collection held by two nesting parents is allowed); the referrer tests share their
   helpers; the referrer-naming code computes once and takes the types it needs; the import
   contract lists its two missing modules; `more_count` moves beside `hidden_count`; three
   docstrings and one slug description say what the code does; the write guard's collection check
   stops threading six arguments through three methods. The test helpers get one home: the toy's
   vocabulary, a `book_json()` builder and a fast-poll constant in `tests/toy.py` (#272 d, e, f),
   the toy composition root in `tests/` (#272 b), one tenancy double checked against the real
   signature (#275).
3. **Stage 2, the generator (#192, #189):** tests first (each theme's `domain/generated/` holds
   exactly its modules); one accessor for `TOOLKIT_ROOTS`, one predicate for "generated here",
   one home per repeated constant; the stored-file class found once per caller; the test-only
   vocabulary constants moved out of the library; the test assertions, the theme map and the
   config tests brought to `testing.adoc`; one spec scenario worded as its test runs it.
4. **Stage 3, events, testkit and docs (#215, #214, #125, #189, #272 a/c, #273):** the D-7 test and its
   scenario, the import check for the testkit root, `re.escape` on the URLs, a test that fails
   without `relay.wake()`, a Redis test of redelivery by `claim_idle` within one run; the event
   stream how-to states its outcomes; the getting-started tutorial and the route-shapes rule of
   `model.adoc` and `generate.adoc` match the code. The shapes are read, hashed and warmed by one
   function (#272 c); `testing.adoc` says how to plant a mutation in a generated file (#273); a
   tooling test fails on a patch of toolkit code with no `# X` marker (#272 a).

Success is measured by two facts: every existing test stays green with no edit to its assertions
(except the tests this EPIC moves or rewrites, each listed in `design.md` with the lane that runs
it), and `make check-generated` shows no change of meaning in a generated artefact.

## Key decisions

- **DEC-1:** an item is in scope only if no caller, consumer, store or generated artefact can see
  a difference in behaviour: a public signature, an outcome, an error's type or text, the queries
  sent, a key of `[tool.rp-generate]`, the set of files `rp-generate` writes. Documentation text
  (docstrings, slug descriptions, pages) and the module a slot is declared in are not behaviour.
  Source: the owner's scope for this EPIC. Rejected: taking the small behaviour fixes "while we
  are there" (they need their own spec deltas and review).
- **DEC-2:** a change that keeps outcomes but changes the queries sent to the store (#252 b, c;
  #235 C-1) is out. Its gain is one query or one session; its failure mode is a wrong refusal or
  a leaked referrer name. Rejected: taking them with a query-count test (a query count proves
  fewer queries, not the same outcome under every stored state).
- **DEC-3:** the proof of each preserving item is the existing tests staying green, plus a
  characterisation test written first where no test pins the behaviour the item touches
  (`design.md` names which). A characterisation test passes on today's code; it is shown to bite
  by a planted mutation, reverted, and recorded in the task's hand-off.
- **DEC-4:** each seed issue ends this EPIC either closed (nothing left but done items) or
  narrowed by a comment to its behaviour-changing items and their recommended home. No issue is
  closed with an item silently dropped.
- **DEC-5:** three stages, one PR each, merged by the merge rules in force at the time (P-0013,
  P-0021: on green CI, or, while the owner has GitHub CI suspended, on a passing local `make
  check-all` recorded in the PR); one L2+L3 pass per stage and the full review once at the end
  (P-0005).
- **DEC-6:** the owner folded in #272 (all six items), #273 and #275 on 2026-11-25
  (`inputs/qa.md`, round 2). Five of #272's items, #273 and #275 are preserving under DEC-1;
  272-c adds an internal function, `load_warm_shapes` in `api.services.shacl`, and the owner took
  it knowing so: it is the one exception to DEC-1, bounded by keeping it out of the public surface
  and every outcome unchanged (design.md PD-19). Rejected: leaving 272-c in #272 (the planner's
  recommendation).

## Rabbit-holes

- **The generator structure (#192 c, d):** declaring the theme-target kind in `rp_generation.yaml`
  and honouring `--project` look like tidy-ups but change a config key and the files written. Do
  not start them here, not even "the private half".
- **The referrer predicate (#252 b):** "does this class refuse deletion" must include
  descendants; getting it wrong leaks referrer names. Out (DEC-2).
- **Stopping a Redis container mid-test (#125 i3):** a restarted testcontainers broker gets a new
  mapped port. Out.
- **A toy subclass of a collection class (#235):** it changes the toy model and every golden.
  Out.
- **Rewording error messages** while touching their code (#252 message number, #189 S2, S3): out
  (DEC-1), even where the spec asks for it.

## No-gos

Each item below changes behaviour (DEC-1) or the queries sent (DEC-2), or is a rabbit-hole, and is
left for the home named; each is an OPEN question in `inputs/qa.md`.

- #252 a (`_types_of` of an untyped root), d (`Aggregates.remove` keyword-only), the `InUse`
  message's number → the follow-up EPIC `floor-behaviour-fixes` (OPEN-1).
- #189 S2 (the theme failure names the derived kind, as the spec already says), S3 (`, `
  separator); #192 a (the E-2 closure check) → `floor-behaviour-fixes` (OPEN-1).
- #252 b, c; #235 C-1 → stay in their issues until a profile shows their cost (OPEN-2).
- #235 the D-5 race and T-4, T-5, T-6 → a later EPIC on the nesting guards; #235 stays open
  (OPEN-3).
- #214 a public way to wait for a follower → its own SMALL EPIC; #214 stays open (OPEN-4).
- #189 the TypeScript re-emission of the toolkit modules → its own EPIC on the generator's
  TypeScript; a new issue split from #189 (OPEN-5).
- #192 c, d and the resolved-path comparison of g → a later EPIC on the generator's structure;
  #192 stays open (OPEN-6).
- #215 S4's runtime half (set the lifespan flag earlier) → not done; the docs half is taken
  (OPEN-7).
- #125 the load items, the Redis broker stop → #125 stays open as triaged (OPEN-8).
- A new conformance-kit case (consumers' adapters would newly fail): the `claim_idle` test is the
  toolkit's own Redis test.
- No change to a public name, signature or outcome; no new test library; no drop of a test except
  the one duplicate #192 names and PD-11's two.
- #371 and #372 (the generator's TypeScript copy of an imported module; the testkit refusing
  hand-written shapes fixtures): planned in `consumer-friction`, not here.

---

## What Changes

- Tests: characterisation tests (#252, #235, #192, #215, #125); shared test helpers; assertions
  brought to `testing.adoc`; one duplicate test dropped; six config tests use layered packages;
  the toy's vocabulary, `book_json()`, `FAST_POLL` and the composition root shared from `tests/`;
  one tenancy double; a guard on patch markers.
- Code (internal only): `shacl.py` and `documents.py` (`load_warm_shapes`), `referenced_removals.py`, `referrer_naming.py`, `openapi.py`,
  `write_guards.py`, `schema_structure.py` and its two callers, `vocabulary.py`, the generator's
  `TOOLKIT_ROOTS` readers, `pydantic_split.py`, `steps.py`, `config.py`, `boundary.py`.
- Model: `more_count` declared in `rp_collaboration_services.yaml`; the `in-use` slug description;
  regenerated with `make generate`.
- `.importlinter`: two modules added to `collaboration-layers`.
- Docs: `develop/testing.adoc`, `user-manual/test.adoc`, `tutorials/getting-started.adoc`, `user-manual/model.adoc`,
  `user-manual/generate.adoc`.
- Specs: `rp-generation` (one scenario's wording), `rp-testkit` (one scenario of today's
  behaviour).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rp-generation`: the scenario "a domain module in a technical target" says "a target", as its
  feature test runs it (#189 S1); the requirement is unchanged.
- `rp-testkit`: a scenario for D-7 (the lifespan's start-up is outside `timeout`), today's
  behaviour (#215 W2).

## Impact

No public API, outcome or generated meaning changes. Generated artefacts change only in the
module that declares `more_count` and in one description text. Consumers: none affected; the
follow-ups the owner accepted (OPEN-1 to OPEN-8) carry every behaviour change.
