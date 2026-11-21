<!-- Parents: the archived change 2026-11-16-test-suite-grooming (its design.md *Debt*, the final
     review's "under the floor" items, inputs/decisions-to-validate.md items 15-17) and the owner's
     answers of 2026-11-17. -->

# EPIC: Pay the test debt the grooming left, and kill the domain's surviving mutants

**Golden-thread parent:** `openspec/changes/archive/2026-11-16-test-suite-grooming/` (design.md
*Debt*, the final review's under-the-floor findings, decisions 15-17) and the owner's answers:
"15. not sure; do what makes sense", "16. fix the debt, do what is right", "17. do what is right;
what was done was done, now build on top of this knowledge".

## Appetite

**LARGE.** Three stages in one pull request (as D-1 of the grooming), CI green on the PR before the
merge.

## Why

The grooming recorded what it could not finish: monkeypatches of toolkit code with no fitting fake,
waits on real time where the code takes no clock, merges and moves outside its folders, two
redundant production branches mutation found, the unexplained cost of `ToyService()`, the
cross-test-module imports that predate it, and 73 behaviour-changing mutants of `domain/` that no
domain test kills. The `rp-messages` spec also contradicts the code on empty commits.

## Solution outline

(Reconciled with the re-plan of 2026-11-21; design.md has the detail.)

1. **Stage 1, test structure:** the root-level unit tests moved to `tests/unit/tooling/` and
   `tests/unit/package/`; the 113 cross-test-module imports moved to helper modules or conftests,
   then guarded; monkeypatches of toolkit code replaced where a real seam exists (rdflib `Dataset`
   subclasses, injected generator steps, edited fixture data, settings) and every other one put in
   one of five recorded exception classes; the short waits (0.001 s keep-alive, 0.01 s publish
   timeout); #215 S1-S3; the unit half of P-31; the remaining P-20 rows; the review's
   under-the-floor items.
2. **Stage 2, production seams that tests need:** a public `Relay.paused()` (and its two users);
   the store's redundant `>= 500` branch removed; `auth.py`'s scheme and empty-token checks kept,
   with the tests they lack; the `ToyService()` shapes parsed once per content and warmed once per
   process (at least 25 % of its ≈ 242 ms); `event_bus_conformance` gains `poll_seconds`; the
   `rp-messages` spec corrected (an empty commit spends nothing, as the code documents).
3. **Stage 3, mutation:** `make mutation` re-run first on today's selection (the `domain` of every
   theme, the iris policy, the tenant move); a test for each behaviour-changing survivor; the rest
   recorded as equivalent with their reasons. The selection is not widened.

## Key decisions

- **DEC-1:** the `rp-messages` spec changes, not the code: `Transaction` documents "a `Served` is
  spent as the request is sent, so an empty block spends nothing", and
  `test_an_empty_commit_does_not_spend_the_command_for_the_real_one_after_it` asserts it. Source:
  the owner's "do what makes sense" (decision 15).
- **DEC-2:** one pull request; CI on the PR must be green before the merge (the grooming merged
  before CI and broke it). Source: lead, after the grooming.
- **DEC-3:** message-only mutants (an error message's text changed) are equivalent: rule 9 forbids
  asserting message text. Source: the grooming's mutation analysis. (2026-11-21: "rule 9" is a
  stale citation; the reason stands: a message's wording is not behaviour a caller relies on.)
- **DEC-4:** production changes are limited to what a test needs (an injected clock or interval, a
  redundant branch removed, a set-up cost cut) and keep every public behaviour.

- **Superseded in the PLAN** (logged, not a re-shape): the waits need no clock and move to stage 1,
  the services mutation widening is dropped, and `auth.py`'s empty-token check stays (a consumer's
  verifier may accept an empty token); see design.md PD-3, PD-4, PD-6, PD-13.
- **Re-planned 2026-11-21** (logged, not a re-shape; the bet holds): the PLAN was rebased on the
  thematic layout. The owner's answers (`inputs/qa.md`) add PD-16 (#215 S1-S3) and PD-17 (triage of
  every monkeypatch of toolkit code), extend PD-7 (warm once per shapes), keep PD-11's moves and
  keep DEC-2 over P-0013's per-stage PRs. The counts above (79 imports, 40 killable, 89 ms) are the
  first PLAN's; design.md has today's.

## Rabbit-holes

- A full mutation run of `services/` (hundreds of modules' worth of mutants): only its pure helper
  modules, and only if time allows.
- Rewriting the adversarial files.

## No-gos

- No change to a public API's behaviour; additions only where a test needs a seam.
- No new test library.
- No drop of a test without a survivor (the grooming's class-3 rules hold).

## Capabilities

- `rp-messages` (modified): an empty commit spends nothing.
- `rp-testkit` (modified): `poll_seconds` on the event-bus conformance kit.
- `rp-events` (modified, to confirm in the PLAN): a public `Relay.paused()` for tests that need
  commits to stay pending.
- `rp-developer-checks` (modified): a change outside a theme selects `tests/unit/package/`.
