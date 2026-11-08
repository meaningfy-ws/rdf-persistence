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

## Review

To be filled by the stage: five lenses (MEDIUM), findings accepted or rejected with a reason, then
the fresh checker.

## Clarity gate

A fresh agent scored the first PLAN 8/10 on 2026-11-08 (gaps: the random-order proof, PD-2's
nested lists, PD-5's error path, the perf lane wiring, a rabbit-hole contradicting PD-8, the Fuseki
tag in two places, the local Maven proof, PD-7's submodule paths, the durations table, the
formatting proof). All are closed above and in tasks.md; the same agent re-scored the PLAN 9/10 (every criterion 9). The open point that
remains: PD-8's list of tests to fix is known only after the first parallel run.
