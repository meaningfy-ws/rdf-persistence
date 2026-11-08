<!-- Parent: EPIC delivery-friction (proposal.md); seeds and answers: inputs/seed.md. -->

# Design: delivery-friction

Seven independent concerns, one stage, one PR. Each section names the decision (PD-n), the files,
and how it is proven. The developer's answers (seed, 2026-11-08) fixed every option; nothing below
is open.

## PD-1 The Fuseki image comes from the Actions cache (Q-1 a)

- `make fuseki-image`: if `temp/fuseki-image.tar` exists, `docker load` it; otherwise
  `docker compose build fuseki` from `rdf_persistence/testkit/containers/compose.yaml` and
  `docker save` the tag `rdf-persistence-test/fuseki:5.6.0` into the file.
- The `fuseki` fixture (`testkit/containers/fixtures.py`) no longer passes `build=True`: compose
  builds the image only when the tag is missing, so a loaded image is used as is. A local edit of
  `fuseki/` without a new tag then needs `docker image rm rdf-persistence-test/fuseki:5.6.0`; the
  vendored files are unmodified upstream, so this is rare (comment at the fixture).
- `ci.yaml`, `containers` job: `actions/cache@v4` on `temp/fuseki-image.tar`, key
  `fuseki-${{ hashFiles('rdf_persistence/testkit/containers/fuseki/**', 'rdf_persistence/testkit/containers/compose.yaml') }}`,
  then `make fuseki-image`, before `make test-containers`.
- A PR can read only its own caches and those of its base branch, and the container job runs on
  PRs only. A small job `fuseki-image` on push to `develop` (same cache step and target) fills
  `develop`'s cache, so a new PR starts with a hit.
- Free: the Actions cache costs nothing (10 GB per repository, LRU after 7 days unused). If it ever
  stops being free, the developer's fallback stands: drop the container job and run it locally.
- Proof: the second CI run of the PR logs a cache hit and no `download.sh` line.

## PD-2 The listing test compares multivalued values in any order (Q-2 a)

`test_an_item_is_what_a_read_of_the_same_book_returns` compares the two documents after sorting
every list value (a local `_unordered` helper in the test). The API promises no order for a
multivalued slot; the test no longer does either. No production change.

## PD-3 Timing budgets leave the default lanes (Q-3, deferred)

`tests/unit/services/test_session_performance.py` moves to `tests/perf/`; `tests/conftest.py`
gains the row `DirectoryMarkers("perf/", ("perf",))`, `pytest.ini` registers `perf`, and
`make test-perf` runs it. `make test` selects `unit or feature`, so the budget no longer gates
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

- Async: `asyncio.wait_for(probe(), probe_timeout)`; the call is cancelled.
- Sync: the call runs in a daemon thread joined for `probe_timeout`. A Python thread cannot be
  stopped, so a hung call's thread is left behind until the process ends (a code comment says so);
  daemon, so it never blocks exit.
- Tests: the two `rp-testkit` scenarios, with a probe that blocks on an `Event` never set.

## PD-6 The adoption guide, steps 4 to 7 (Q-6)

Fix only what the cold reader named (seed): the required `[tool.rp-generate]` keys, what paths are
relative to, whether the `package` folder must exist, one freshness command used consistently with
a link from step 4 to step 6, and "your regenerate target" instead of a fixed `make generate`. Then
a fresh cold reader, given only the page, follows steps 4 to 7; a guess it reports is fixed.

## PD-7 The testing checklist names only exported helpers

`docs/tools/check_docs.py` (stdlib only, run with `python3 -I`) reads `__all__` from
`rdf_persistence/testkit/__init__.py` with `ast` and reports every `testkit.<name>` in
`develop/testing.adoc` that is not in it. Unit test in `tests/unit/test_check_docs.py` plants a
page naming `testkit.some_helper`.

## PD-8 `make test` runs in parallel (Q-7 a)

`pytest-xdist` joins the dev dependencies; `make test` adds `-n auto` (pytest-cov combines the
workers' coverage, so the 80 % floor holds). The other lanes stay serial: the container lane shares
compose projects and the per-lane targets are for quick local runs. Tests that write to shared
paths, found by the first parallel run, get `tmp_path`.

## Review

To be filled by the stage: five lenses (MEDIUM), findings accepted or rejected with a reason, then
the fresh checker.

## Clarity gate

Scored 9/10 by the lead on 2026-11-08: every concern has one decision, its files and its proof;
the only judgement left open by the developer (the timing budget) is named as out of scope. The
missing point: PD-8's list of tests to fix is known only after the first parallel run.
