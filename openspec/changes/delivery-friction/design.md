<!-- Parent: EPIC delivery-friction (proposal.md); seeds and answers: inputs/seed.md. -->

# Design: delivery-friction

Seven independent concerns, one stage, one PR. Each section names the decision (PD-n), the files,
and how it is proven. The developer's answers (seed, 2026-11-08) fixed every option; nothing below
is open.

## PD-1 The Fuseki image comes from the Actions cache (Q-1 a)

- `make fuseki-image`: if `temp/fuseki-image.tar` exists, `docker load` it; otherwise
  `mkdir -p temp`, `docker compose -f rdf_persistence/testkit/containers/compose.yaml build fuseki`
  and `docker save` the image into the file. The tag is not repeated in the Makefile: it is read
  from compose (`docker compose -f … config --images fuseki`), so `compose.yaml` stays its one
  source.
- The `fuseki` fixture (`testkit/containers/fixtures.py`) no longer passes `build=True`: compose
  builds the image only when the tag is missing, so a loaded image is used as is. A local edit of
  `fuseki/` without a new tag then needs `docker image rm` of the tag in `compose.yaml`; the
  vendored files are unmodified upstream, so this is rare (comment at the fixture).
- `ci.yaml`, `containers` job: `actions/cache@v4` on `temp/fuseki-image.tar`, key
  `fuseki-${{ hashFiles('rdf_persistence/testkit/containers/fuseki/**', 'rdf_persistence/testkit/containers/compose.yaml') }}`,
  then `make fuseki-image`, before `make test-containers`.
- A PR can read only its own caches and those of its base branch, and the container job runs on
  PRs only. A small job `fuseki-image` with `if: github.event_name == 'push'` (same cache step and
  target) fills `develop`'s cache, so a new PR starts with a hit.
- Free: the Actions cache costs nothing (10 GB per repository, LRU after 7 days unused). If it ever
  stops being free, the developer's fallback stands: drop the container job and run it locally.
- Proof, local: with the tar present, `make fuseki-image` runs only `docker load`, and
  `make test-containers` starts Fuseki without a build step (no `download.sh` line), so Maven
  Central is never reached. Proof, CI: the PR's second run logs a cache hit and no `download.sh`
  line. Both go in the PR description.

## PD-1b No containers in CI; one parallel job per make group (developer, 2026-11-08)

Decided after the PR was opened, superseding PD-1's CI part. CI on GitHub runs no container, e2e or
Fuseki work: the `containers` job, the Fuseki cache action and the push-only warm-up job are
removed; `make test-containers` (and `make fuseki-image`, `make test-e2e`) run locally. The checks
split into parallel jobs, each one make group that also runs alone:

| CI job | Make target | Runs |
|---|---|---|
| style | `check-style` | `format-check`, `lint`, `clean-code` |
| types | `check-types` | `typecheck`, `typecheck-generated`, `typecheck-ts` |
| architecture | `check-architecture` | import-linter |
| spec, docs and generated code | `check-spec-docs`, `check-generation` | `check-spec`, `check-docs`; `check-freshness`, `check-generated` |
| unit | `test-unit` | unit tests, `-n auto`, the 80 % coverage floor, SonarCloud |
| feature | `test-feature` | BDD feature tests, `-n auto`, a 50 % coverage floor |

Each test job has its own floor (developer): unit 80 %, feature 50 %. Measured 2026-11-08, the
unit tests alone cover 94 %, the feature tests alone 59 %. `make test` keeps the combined 80 %. `check-quality` is now the groups plus `check-freshness`, so it gains
`clean-code` and `typecheck-ts`; `check-all` = `check-quality` + `test` as before. `ci-quick`,
`ci-full` and `changes-code` (used only by the removed job) are deleted. A shared composite action
`.github/actions/setup` holds the Python, uv and `make install` steps every job repeats.

## PD-2 The listing test compares multivalued values in any order (Q-2 a)

`test_an_item_is_what_a_read_of_the_same_book_returns` compares the two documents after a local
`_unordered` helper in the test: dicts map to dicts of `_unordered` values, lists to their
`_unordered` items sorted by `json.dumps(item, sort_keys=True)` (lists may hold nested dicts, so a
plain `sorted` would raise `TypeError`), anything else to itself. The API promises no order for a
multivalued slot; the test no longer does either. No production change.

## PD-3 Timing budgets leave the default lanes (Q-3, deferred)

`tests/unit/services/test_session_performance.py` moves to `tests/perf/` (with an empty
`tests/perf/__init__.py`, like the other test directories); `tests/conftest.py` gains the row
`DirectoryMarkers("perf/", ("perf",))`, `tests/unit/test_markers.py` gains the case
`("perf", {"perf"})`, `pytest.ini` registers `perf: wall-clock budgets; run alone with make
test-perf`, and `make test-perf` runs `uv run pytest $(TEST_PATH)/perf -m perf` (no coverage, no
xdist: a budget is measured alone). `make test` selects `unit or feature`, so the budget no longer gates
`check-all` or CI. The budget value is not changed (the developer decides it later). The 2 s check
in `tests/integration/store/test_session.py` stays: the container lane runs serially, against a
real store, and has not failed.

## PD-4 Formatting is gated (Q-4 a)

`make format-check` runs `ruff format --check` over the package, `tests` and `docs/tools`, and joins
`check-quality`; `make format` covers the same paths. One commit formats the tree.

## PD-5 `probe_timeout` on both waiting helpers (Q-5 a)

Optional keyword `probe_timeout: float | None = None`. Unset: no change. Set: a call that has not
returned within it counts as "not ready yet" (like a `retry_on` error) and the wait goes on to the
overall `timeout`, which raises `TimeoutError` naming `what`.

- Async: the call runs inside `async with asyncio.timeout(probe_timeout) as bound:`; the call is
  cancelled when the bound fires. On `TimeoutError`, `bound.expired()` tells the two cases apart:
  true means the bound fired (not ready); false means the probe raised `TimeoutError` itself, which
  then follows `retry_on` like any other error.
- Sync: the call runs in a daemon `threading.Thread` whose target stores either the return value or
  the raised exception in a one-element box; the helper joins it for `probe_timeout`. Still alive:
  not ready. Finished with an exception: re-raised in the caller's thread, so `retry_on` errors count
  as not ready and any other error propagates, exactly as without the bound. A Python thread cannot
  be stopped, so a hung call's thread is left behind until the process ends (a code comment says
  so); daemon, so it never blocks exit.
- Tests: the three `rp-testkit` scenarios (a probe blocking on an `Event` never set; a slow call
  then an answer; a non-retry error inside the bounded call propagates), for both helpers.

## PD-6 The adoption guide, steps 4 to 7 (Q-6)

Fix only what the cold reader named (seed): the required `[tool.rp-generate]` keys, what paths are
relative to, whether the `package` folder must exist, one freshness command used consistently with
a link from step 4 to step 6, and "your regenerate target" instead of a fixed `make generate`. Then
a fresh cold reader, given only the page, follows steps 4 to 7; a guess it reports is fixed.

## PD-7 The testing checklist names only exported helpers

`docs/tools/check_docs.py` (stdlib only, run with `python3 -I`) reads `__all__` from
`rdf_persistence/testkit/__init__.py` with `ast` and reports every `testkit.<name>` in
`develop/testing.adoc` that is not in it. A name is the first segment only
(`testkit\.(\w+)`); a segment that is a submodule of the testkit (a `.py` file or package
under `rdf_persistence/testkit/`, e.g. `testkit.containers.fixtures`) is accepted as a module
path. Unit test in `tests/unit/test_check_docs.py` plants a
page naming `testkit.some_helper`.

## PD-8 `make test` runs in parallel (Q-7 a)

`pytest-xdist` joins the dev dependencies; `make test` adds `-n auto` (pytest-cov combines the
workers' coverage, so the 80 % floor holds). The other lanes stay serial: the container lane shares
compose projects and the per-lane targets are for quick local runs. Tests that write to shared
paths, found by the first parallel run, get `tmp_path`.

Order independence (the seed's scenario "passes in random order"): xdist changes which worker runs
a test, not the order inside a worker, so it is proven once, not gated: one run of the unit and
feature lane with `uv run --with pytest-randomly pytest tests --ignore=tests/integration
--ignore=tests/e2e --ignore=tests/perf -m "unit or feature" -p randomly`, and one with
`-p randomly --randomly-seed=<another>`; both green, the seeds recorded in the PR. No
new dependency is added; a test that fails there is made deterministic (DEC-2).

## Delivery notes

- **PD-6a (lead, 2026-11-08) The cold reader's guesses are all fixed, in steps 2 and 4 to 7.** After
  PD-6's edits, the first cold read of `howto/adopt.adoc` still named 20 guesses: 9 in steps 4 and
  7, 11 in steps 5 and 6 that predate this EPIC. The seed's scenario is "a cold reader follows steps
  4 to 7 without a guess", so all 20 are fixed. Each fix states a fact checked in the code; guess 11
  adds the layer folders to the step 2 layout. A second fresh cold reader confirms.
- **PD-6b (developer, 2026-11-08) When the guide is done.** A second cold read named 20 new
  guesses (2 blocking, 18 minor): each pass adds detail and the next reader finds more, so "no
  guess" never ends. The developer chose: the guide is done when a fresh reader reports **no
  blocking guess and no contradiction**; the remaining minor guesses are recorded in
  `evidence/cold-reads.md`, not fixed. Fixed from the second read: both blocking guesses (the
  pytest `pythonpath` a consumer needs; what a model change does to stored data — there is no
  migration, `questions.adoc` lists it as deferred), the four contradictions, and six cheap ones.
  Also fixed: step 1's `[project]` lacked `name`, so `uv sync` failed. Found and filed, not fixed
  here: the file guard's `*.context.jsonld` misses `context.jsonld` (issue #38).
- **PD-8a (lead) What broke in parallel.** No test shared a path. xdist aborted on parameters built
  from `uuid4()` at import (different ids per worker), now fixed literals or explicit ids. The
  random-order run (seed 124119802) found one golden test comparing a folder that other tests
  import from; it now generates into its own `tmp_path`. Seed 20261108 passed.
- **Task 3.1 was done by the lead** without a builder: a three-line Makefile change and a
  mechanical format.

## Review

Five lenses on `41c9b15..c6994ff` (2026-11-08): no P0; one P1 (L2), three P2, the rest P3.
`make check-architecture` and `make test` (3346, 94.32 %) green under review.

Accepted (the lead's decisions; R-n):

- **R-1 (L2 P1) No wall-clock asserts in the unit lane.** The two "probe never returns" tests assert
  `elapsed < timeout + 0.5` and sleep for real, which DEC-2 and rule 11 forbid. They take an
  injected `monotonic` and `sleep` and assert the `TimeoutError` message and the call count; the
  short real waits inside `probe_timeout` (`join`, `asyncio.timeout`) stay, unasserted.
- **R-2 (L2 P2, L3 P3-1, L5 P3-2) One Fuseki-image step, saved even when tests fail.**
  `actions/cache@v4` saves only when the job succeeds, so a PR that misses the cache and then fails
  a test downloads from Maven Central again on every re-run; and the cache step and key were copied
  into two jobs. A composite action `.github/actions/fuseki-image` holds `actions/cache/restore`,
  `make fuseki-image` and `actions/cache/save` (on a miss); both jobs call it, so the key lives once.
- **R-3 (L4 P2, L1 P3-4) At most one hung sync probe.** `_call_bounded` started a new thread per
  poll, so a hanging endpoint left up to ~150 threads. A call still running from the previous poll
  is joined again instead of starting a new one. The docstring says probes should be read-only,
  since a late call may still finish.
- **R-4 (L1 P3-3) `probe_timeout <= 0` is a `ValueError`,** with a test: zero makes every call "not
  ready" and the wait ends in a misleading timeout.
- **R-5 (L1 P3-1) `make fuseki-image` fails when the build fails:** the build branch is joined with
  `&&`, so an old image of the same tag is not saved after a failed build.
- **R-6 (L1 P3-2, L4 P3-4, L3 note) A local tar is rebuilt when its inputs change.** The tar is a
  make file target that depends on `fuseki/` and `compose.yaml`; `make fuseki-image` loads it. In CI
  the restored tar is newer than the checkout, so it is loaded; locally an edit of `fuseki/`
  rebuilds. The fixture's comment says to run `make fuseki-image` after such an edit.
- **R-7 (L5 P2) One list of Python paths.** `PYTHON_PATHS` (package, `tests`, `docs/tools`) feeds
  `format`, `format-check`, `lint` and `lint-fix`; `docs/tools` was format-checked but not linted.
- **R-8 (L4 P3-4, L5 P3-3) The Fuseki Makefile variables** sit in the top block on `$(REPO_ROOT)`;
  `mkdir -p $(dir …)`; the help text does not spell the path again.
- **R-9 (L4 P3-3, L5 P3-4) `check_docs.py`:** the testkit path is computed once and passed in; the
  message uses `rel(page)`; a testkit without `__all__` is reported as such, not as every name
  "not exported".
- **R-10 (L4 P3-2) The upper-case UUID parameters carry an id** saying what they stand for.
- **R-11 (L4 P3-5) `box` is named `outcome`.**
- **R-12 (L3 note) `_running`'s `build` parameter is deleted:** no caller passes it any more.

As built, three points differ from the wording above:

- **R-6a The restored tar is touched on a cache hit.** R-6 assumed the restored tar is newer than
  the checkout; `actions/cache` keeps the saved mtime, so `make` would rebuild on every hit. The
  composite action runs `touch` on the tar on a hit, safe because the key hashes exactly the tar's
  inputs. It is the one inline command in CI outside `make` (the D12 thin-workflow rule), kept
  there because it exists only for the cache.
- **R-6b `.DELETE_ON_ERROR:`** in the Makefile, so a failed build or save never leaves a tar that
  looks up to date. It applies to every file target (all others are phony).
- **R-11a** The outcome slot is `_outcome`, an attribute of the new `_BoundedCall` (R-3).

Rejected:

- **L3 P3-2 (automate the thin-workflow rule):** true, but older than this change and outside its
  shape; a candidate for a later change.
- **L3 P3-1's "derive the key from `FUSEKI_COMPOSE`":** after R-2 the key is written once, next to
  the step that uses it; deriving it through make adds a step for no gain.
- **L2 P3, L1 and L4 blast-radius notes:** informational; `probe_timeout=None` keeps the old path
  (tested, 100 % coverage of `bootstrap.py`).

## Clarity gate

A fresh agent scored the first PLAN 8/10 on 2026-11-08 (gaps: the random-order proof, PD-2's
nested lists, PD-5's error path, the perf lane wiring, a rabbit-hole contradicting PD-8, the Fuseki
tag in two places, the local Maven proof, PD-7's submodule paths, the durations table, the
formatting proof). All are closed above and in tasks.md; the same agent re-scored the PLAN 9/10 (every criterion 9). The open point that
remains: PD-8's list of tests to fix is known only after the first parallel run.
