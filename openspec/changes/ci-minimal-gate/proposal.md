<!-- Parents: the developer's request of 2026-11-28 ("if the 10k tests are running in the CI, it is
     a disaster"; "keep the full unit tests and the slow and lengthy tests to be executed only
     locally"); capability rp-developer-checks. -->

# EPIC: A minimal CI gate per PR, the full suite nightly

**Golden-thread parents:** capability `rp-developer-checks` (its requirement "CI runs the static
checks and the tests in parallel jobs, without containers", which this change supersedes);
`2026-11-08-delivery-friction` (D12, "green locally means green in CI"); the developer's request
of 2026-11-28.

## Appetite

**SMALL.** Two workflow files, the tests that read them, three docs paragraphs and one spec delta.
No code in `rdf_persistence/` or `rdf_persistence_generation/` changes, no make target changes.

## Why

The last green CI run (2026-11-27, run 46081982968) ran about 10,400 tests on every PR and again on
the merge commit in `develop`: ~8,475 unit tests in 8 shards (3:42 to 5:42 each), 1,838 generator
tests on one runner (14:32) and 102 feature tests (1:51). It took about 15 minutes of wall clock
and 65 to 70 runner minutes per run, twice per change. The lead already runs `make check-all`, the
same tests with the slow ones included, before every PR (`AGENTS.md`), so CI repeats work the PR
has already proven.

## Solution outline

1. **The PR gate** (`ci.yaml`, on pull requests into `develop` only) runs the checks a reviewer
   cannot see in a diff, plus the specified behaviour: `check-style`, `check-types`,
   `check-architecture`, `check-spec-docs` with `check-generation`, and `test-feature` (the BDD
   scenarios, 50 % floor). About 3 minutes of wall clock.
2. **The nightly run** (`nightly.yaml`, on a schedule and by hand) runs the full unit lane in its 8
   shards with the combined 80 % floor, the generator's tests and the SonarCloud scan, on
   `develop`. It catches what a local run missed: a skipped `make check-all`, two PRs that break
   only together, a test that passes only on one machine.
3. **Locally**, unchanged: `make check-all` before every PR runs every unit, feature and generator
   test, slow ones included, with their floors; `make test-containers` when adapters change.

## Decisions

- **DEC-1** CI runs on pull requests only; the push to `develop` triggers nothing in `ci.yaml`. The
  PR already ran the gate on the same tree, and the nightly run covers the merged state.
- **DEC-2** The PR gate keeps the feature tests and drops the unit and generator tests. The feature
  tests are the spec scenarios; the unit and generator suites are the developer's local gate.
- **DEC-3** The nightly run keeps today's jobs unchanged (shards, coverage combine, generator,
  Sonar), moved, not rewritten. Sonar analyses `develop`, its main branch, once a day.
- **DEC-4** This supersedes D12 in one direction: green locally still implies green in CI, but
  green in CI no longer implies the unit and generator suites pass; the nightly run and the local
  `make check-all` carry that.
- **DEC-5** The README badge shows the nightly run, the one that runs on `develop`.

## Rabbit holes

- Path filters that run the generator tests only when the generator changes: not now; the nightly
  run covers it. Revisit if a generator break reaches `develop` twice.
- Proving the local `make check-all` ran (a stamp, a PR checkbox): not now.

## No-gos

- No change to a make target, a test, a marker or a coverage floor of the local lanes.
- No container, e2e or Fuseki work in either workflow.
- No change to `release.yaml` or `docs.yaml`.
