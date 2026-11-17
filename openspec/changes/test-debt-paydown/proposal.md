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

1. **Stage 1, test structure:** the rule-5 monkeypatches replaced where a real seam exists (a
   public `Relay.paused()`, rdflib `Dataset` subclasses, injected generator steps, edited fixture
   files; two `test_receive` patches and the "no generate extra" test stay as recorded
   exceptions); the unit half of P-31; the remaining P-20 rows; the 79 cross-test-module imports
   moved to helper modules or conftests, then guarded; `event_bus_conformance` gains
   `poll_seconds` (it helps the Redis lane only); the review's under-the-floor items.
2. **Stage 2, production clean-ups that tests need:** the real-time waits removed without a new
   clock parameter (assert on the next visible event; `keep_alive=0` and `publish_timeout=0` where
   the code already takes them); the Fuseki `>= 500` branch removed; `auth.py`'s scheme check kept
   with the test it lacks (a JWT sent as `Basic`), its empty-token check removed; the
   `ToyService()` shape parsing cached per process (about 35 % of its 89 ms); the `rp-messages`
   spec corrected (an empty commit spends nothing, as the code documents).
3. **Stage 3, mutation:** `make mutation` re-run first (the list predates the final fixes); then a
   test for each behaviour-changing survivor of `domain/` (facts: 40 killable, 1 to timebox, 32
   equivalent with the reason recorded); the selection widened to the services layer's pure
   modules only if stage 3 finishes inside its appetite.

## Key decisions

- **DEC-1:** the `rp-messages` spec changes, not the code: `Transaction` documents "a `Served` is
  spent as the request is sent, so an empty block spends nothing", and
  `test_an_empty_commit_does_not_spend_the_command_for_the_real_one_after_it` asserts it. Source:
  the owner's "do what makes sense" (decision 15).
- **DEC-2:** one pull request; CI on the PR must be green before the merge (the grooming merged
  before CI and broke it). Source: lead, after the grooming.
- **DEC-3:** message-only mutants (an error message's text changed) are equivalent: rule 9 forbids
  asserting message text. Source: the grooming's mutation analysis.
- **DEC-4:** production changes are limited to what a test needs (an injected clock or interval, a
  redundant branch removed, a set-up cost cut) and keep every public behaviour.

- **Superseded in the PLAN** (logged, not a re-shape): the waits need no clock and move to stage 1,
  the services mutation widening is dropped, and `auth.py`'s empty-token check stays (a consumer's
  verifier may accept an empty token); see design.md PD-3, PD-4, PD-6, PD-13.

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
