<!-- SECONDARY INPUT: preserved, never groomed. The EPIC (../proposal.md) is the shaped truth. -->

# Seed: delivery friction (2026-11-08)

## Seed text

The developer, 2026-11-08: "why don't you shape a new epic change for all those gaps you
discovered?" The gaps, as met in the implementation session for #24, #25 and #26:

- PR #27, container job: `curl: (22) The requested URL returned error: 429` fetching
  `jena-fuseki-server-5.6.0.jar` from Maven Central.
- `make check-all` in the `generation-fix-hint` worktree: 1 failed,
  `test_an_item_is_what_a_read_of_the_same_book_returns`, `{'authors': ['Joyce', 'Herbert']} !=
  {'authors': ['Herbert', 'Joyce']}`; passes alone (6 runs) and with `PYTHONHASHSEED` 1 to 12.
- Three runs under load: `test_replace_stays_within_the_budget[drops it-50 aggregate, 2000 loaded]`
  failed; passed alone.
- `uv run ruff format --check` on `develop`: `Would reformat: docs/tools/check_docs.py`.
- Cold reader of `howto/adopt.adoc` step 4 (PR #32): required keys, relative paths, the package
  folder, `check-generated` against `rp-generate --check`, the fixed name `make generate`, no link
  from step 4 to the freshness checks of step 6. The `regenerate-command` part was fixed in #32.
- Not taken in `testkit-wait-until` (design.md, Review fixes): bounding a probe that never returns
  (L1); a docs check that rule 11 names only exported helpers (L2).
- Not taken in `generation-fix-hint`: one constant for the program name `rp-generate` (L5); left
  out of this EPIC as too small to carry, recorded here.

## Open questions for the developer

1. **How does CI stop depending on Maven Central?**
   - (a) cache the built Fuseki image between runs (`docker save` into the Actions cache, keyed on
     the Dockerfile and `JENA_VERSION`). **Recommended:** no new registry, the key changes only when
     Fuseki does.
   - (b) publish the image to GHCR from a small workflow and pull it: fastest, one more thing to
     release.
   - (c) cache only the jar and copy it in (the Dockerfile's documented alternative to downloading).
2. **The listing order test.**
   - (a) compare multivalued slots as sets in the test. **Recommended:** the API promises no order
     for a multivalued slot today; the test should not either.
   - (b) make the framed output sort multivalued literals, so reads and listings always agree: a
     behaviour change for consumers.
3. **The timing-budget tests.**
   - (a) mark them `perf` and run them only in a lane on a quiet machine (CI's container job or a
     `make test-perf`). **Recommended:** a budget only means something without contention.
   - (b) widen the budgets: hides real regressions.
   - (c) keep them and accept rare failures: contradicts DEC-2.
4. **Formatting:** (a) `ruff format --check` inside `make check-quality`, plus one commit formatting
   the tree. **Recommended.** (b) a pre-commit hook only: not enforced in CI.
5. **A probe that never returns.**
   - (a) an optional `probe_timeout` argument on both helpers, default none, so nothing changes for
     today's callers. **Recommended.**
   - (b) always bound each call by the time left: changes behaviour for every caller.
   - (c) document the limit only.
6. **The adoption guide:** fix only what the cold reader named, in steps 4 to 7, and run a cold
   reader again on the result. **Recommended**, versus a rewrite of the page.

## Test scenarios the EPIC must prove

- The full suite passes in random order (`-p randomly` or reversed order) and under machine load.
- A container job with Maven Central blocked starts Fuseki.
- `make check-all` fails on an unformatted file.
- `make check-docs` fails when rule 11 names an unexported helper.
- With `probe_timeout`, a probe that never returns ends in `TimeoutError` naming `what`.
- A cold reader follows steps 4 to 7 without a guess.
