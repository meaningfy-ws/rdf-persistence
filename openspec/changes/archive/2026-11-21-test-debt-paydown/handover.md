# Handover: test-debt-paydown

Delivered on `change/test-debt-paydown-build` as one pull request (DEC-2, PD-14). What was built,
against the shape, is `proposal.md`'s *Delivered* table; how it ran is `design.md`'s
*Delivery decisions* (D-1 to D-7); the gate runs are `evidence/gates-stage1.md`.

## State

- Tasks 1.1 to 3.4 done; 3.5 done up to the merge, then the owner's acceptance and the archive.
- `make mutation`: 1091 mutants, 33 survivors, exactly `tests/audit/equivalent-mutants.md`.
- Spec deltas: `rp-developer-checks`, `rp-events`, `rp-messages`, `rp-testkit`, `rp-iri-policy`
  (the last added at the final review, D-7). They merge into `openspec/specs/` at the archive.

## For the owner

- Acceptance: the change pays the grooming's debt list and #215 S1-S3; the PR closes #215's S1-S3
  only (W2, W5, S4, S5 stay on it).
- Decisions taken by the lead within the PLAN, each recorded: `no-exp` and
  `exp-as-a-numeric-string` kept (19 token cases, not 17: each alone guards a check); the
  keep-alive test's 0.12 s; DEC-3 read as "wording" (a test may assert what a message must name);
  the two `make mutation` harness fixes (selection unchanged).

## Found, not fixed here (each wants an issue)

1. `tests/unit/core/test_sparql.py::test_any_string_literal_round_trips` fails on the Hypothesis
   example `text='\x1f0000'`: rdflib reads the escape and the four digits after it as one code
   point (`Invalid unicode code point: 001f0000`). A defect in the SPARQL literal escaping of
   `rdf_persistence/core`; it reproduces wherever `.hypothesis/` holds the example.
2. TC-36, `tests/unit/api/test_events_route.py::test_a_reader_whose_queue_filled_resumes_and_gets_every_missed_activity_once`,
   failed once under the full suite's load (`0 of 3 events within 30.0 s`) and passed every rerun:
   a race in the test's use of the hub's queues.
3. Deferred review items (D-7): a tooling guard that every kept toolkit patch carries its X mark;
   `tests/e2e/library_app.py` imported by a unit test; one `shacl.load_warm_shapes(path)` entry so
   the digest is not the caller's to get right; `BOOK_JSON` as a builder (its nested lists are
   shared by shallow copies); one fast-poll constant for the ≈15 `poll_seconds=0.01`; the toy
   vocabulary (`BIBO`, `TITLE`, `BOOK_CLASS`) in `tests/toy.py`.
4. A proof by hand-mutation of generated code needs
   `-p no:rdf_persistence_generation.testkit.freshness` (the freshness plugin stops pytest on a
   hand-edited generated file); worth a line in `testing.adoc`.

## Clean-up after the merge

Local branches `tdp/*` and the worktrees `.worktrees/tdp-*` and `.worktrees/test-debt-build`.
