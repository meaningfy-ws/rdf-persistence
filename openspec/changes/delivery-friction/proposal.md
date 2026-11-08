<!-- Parents: the implementation session for #24, #25, #26 (2026-11-08): CI runs of PRs #27, #28,
     #31, #32; review and cold-reader findings not taken in testkit-wait-until and
     generation-fix-hint (their design.md, "Review fixes"). Seeds: inputs/seed.md. -->

# EPIC: Remove the friction met while delivering #24, #25 and #26

> Candidate EPIC, shaped 2026-11-08 from what one delivery session ran into. Not planned: the PLAN
> (design.md, tasks.md) waits for the developer's answers in inputs/seed.md.

**Golden-thread parent:** the stage loop's gates (`develop/agents.adoc`, "The gates") and the
adoption guide (`howto/adopt.adoc`), which this session found leaky in the places listed below.

## Appetite

**SMALL**, one stage. Six independent concerns, each a few lines of CI, Makefile, test or doc; no
new concept and no change to the toolkit's API, except one optional argument (Q-5).

## Why

Each item below cost a re-run, a guess or a wrong signal during one session:

1. **CI downloads Fuseki from Maven Central on every run.** PR #27's container job failed on HTTP 429
   from `repo1.maven.org` while building the Fuseki image (`fuseki/Dockerfile:54`); nothing in the PR
   caused it.
2. **Two tests fail without a change.**
   `test_listing_routes.py::test_an_item_is_what_a_read_of_the_same_book_returns` failed once in a
   full `make check-all` (authors `['Joyce', 'Herbert']` against `['Herbert', 'Joyce']`) and passes
   alone and under 12 hash seeds, so the order depends on what ran before. The timing budgets in
   `test_session_performance.py::test_replace_stays_within_the_budget` failed three times while
   other test runs shared the machine.
3. **Formatting is not gated.** `make check-all` runs `ruff check` but not `ruff format --check`;
   `develop` already holds an unformatted `docs/tools/check_docs.py`.
4. **The adoption guide leaves a newcomer guessing** (cold reader of step 4, 2026-11-08): which
   `[tool.rp-generate]` keys are required, what paths are relative to, whether the `package` folder
   must exist, whether to use `make check-generated` or `rp-generate --check` (step 4 defines one,
   step 6 uses the other), and steps 4 and 7 name `make generate` as if the target name were fixed.
5. **A probe that never returns hangs the waiting helpers.** `wait_until` and `wait_until_async`
   check the deadline only between calls (review of `testkit-wait-until`, L1).
6. **Nothing checks that the testing checklist names public helpers.** Rule 11 named
   `testkit.wait_until` while the testkit did not export it (issue #24); no check would catch the
   next one (review of `testkit-wait-until`, L2).

## Solution outline

One stage, one PR: the container job reuses a cached Fuseki image or jar; the two tests become
deterministic (the listing compares authors as a set or sorts them where the API promises no order;
the budget tests run where their budget means something); `make check-quality` gains
`ruff format --check` and `develop` is formatted once; step 4 to 7 of `adopt.adoc` answer the
reader's questions; the waiting helpers can bound one probe call; `make check-docs` checks every
`testkit.<name>` that `develop/testing.adoc` names against `rdf_persistence.testkit.__all__`.

## Key decisions

- **DEC-1**: Checks run through `make`, and CI calls only `make` targets (D12). Source: `AGENTS.md`,
  `.github/workflows/ci.yaml`. Rejected: inline tool commands in the workflow.
- **DEC-2**: A flaky test is made deterministic or moved, never retried until green. Source: the
  testing checklist (FIRST, repeatable). Rejected: `pytest-rerunfailures`.
- **DEC-3**: The listing's item and the read of one aggregate keep returning the same framed
  document; this EPIC only stops the test depending on an order the API does not promise. Source:
  the test's own message ("framed the same way"). Whether the API should promise an order is
  question Q-2.

## Rabbit-holes

- Speeding up the suite. `test-profiling` owns that; this EPIC only removes false failures.
- Rewriting the adoption guide. Only the gaps the cold reader named, in steps 4 to 7.
- A general retry policy for GitHub-side failures (HTTP 504 on setup). Re-running the job is enough.

## No-gos

- Parallel test execution, coverage changes or a CI dashboard (`test-profiling`).
- Changing the default timeout or poll interval of the waiting helpers.
- New runtime dependencies of the package.

---

## What Changes

- `.github/workflows/ci.yaml`, possibly `rdf_persistence/testkit/containers/`: a cached Fuseki
  image or jar (Q-1).
- `tests/unit/entrypoints/test_listing_routes.py` (or the listing, Q-2) and
  `tests/unit/services/test_session_performance.py` (Q-3).
- `Makefile`: `ruff format --check` in `check-quality`; one formatting commit.
- `docs/modules/ROOT/pages/howto/adopt.adoc` steps 4 to 7.
- `rdf_persistence/testkit/bootstrap.py`: an optional per-call bound (Q-5).
- `docs/tools/check_docs.py`: the public-helper check for `develop/testing.adoc`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rp-developer-checks`: the checks give the same answer on every run, and gate formatting.

## Impact

- CI and developer tooling, the adoption guide, one optional testkit argument.
- No change to the toolkit's runtime API or its dependencies.
