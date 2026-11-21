# Gates, stages 1 and 2 (D-1: one shared run)

Run by the lead on `change/test-debt-paydown-build` at the head before the review's fixes
(e27b1a47), 2026-11-21.

| Gate | Result | Time |
|---|---|---|
| `make check-all`, quality items | 30 passed, 0 failed | |
| `make check-all`, unit and feature | 7701 passed, 4 xfailed | 3 min 42 s |
| `make check-all`, generator e2e | 97 passed | 31 s |
| `make check-all`, generator unit | 1477 passed, 2 xfailed | 1 min 29 s |
| `make check-all`, total | exit 0 | 6 min 39 s |
| `make test-containers` | 344 passed, 1 xfailed, exit 0 | 11 min 38 s |

Collected `unit or feature`, not slow: 9033 before the review's fixes, 9034 after (one control test
added for `Relay.paused()`).

The review's fixes (6ba43589): `make test-fast` 9029 passed, 5 xfailed, and `make check-quality`
passed in the fixer's worktree; the gates run again after the rebase on `develop` (task 1.7).

## After the rebase on `develop` (37e886ca, with the review's fixes)

| Gate | Result | Time |
|---|---|---|
| `make check-all`, quality items | 32 passed, 0 failed | |
| `make check-all`, unit and feature | 7719 passed, 4 xfailed | 3 min 33 s |
| `make check-all`, generator e2e | 97 passed | 33 s |
| `make check-all`, generator unit | 1504 passed, 1 xfailed | 2 min 1 s |
| `make check-all`, total | exit 0 | 6 min 52 s |
| `make test-containers` | 351 passed, exit 0 | 7 min 24 s |

## Found outside this change

`tests/unit/core/test_sparql.py::test_any_string_literal_round_trips` fails on the Hypothesis
example `text='\x1f0000'`: rdflib's SPARQL parser reads the escape and the four digits after it as
one code point and raises `ValueError: Invalid unicode code point: 001f0000`. Neither the test nor
`rdf_persistence/core` is touched by this change; it is a defect in the literal escaping, for an
issue of its own (handover).

`tests/unit/api/test_events_route.py::test_a_reader_whose_queue_filled_resumes_and_gets_every_missed_activity_once`
(TC-36) failed once in `make check-all` after the rebase on `develop` (`0 of 3 events within
30.0 s`), then passed twelve runs of the events tests in a row in random order. Its body is
`develop`'s; this change only moved its helpers to `tests/events_follow.py`. A race under load in
the test's use of the hub's queues (`hub._max_queue`, `drained`), for an issue of its own
(handover).
