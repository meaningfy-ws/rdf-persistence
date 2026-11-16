# Skillery execution report: rdf-persistence, 2026-11-16

What happened when skillery 3.19.0's skills drove one long session on `rdf-persistence`: a
project-setup gap analysis, a slimming of the agent instructions, a `test-suite-care` audit, and the
delivery of its proposals (P-1 to P-8, P-20 to P-34 and P-40 to P-51: 35, of which the lead withdrew P-46 to P-48 as never W-5, leaving 32) as the change `test-suite-grooming` (epic-planning,
clarity-gate, epic-delivery). Written for the skillery maintainers. The chronological record, good
and bad, is `session-trace.md` beside this file; the owner's view of the decisions is
`decisions-to-validate.md`; the testing-strategy advice and the skill review are
`strategy-and-skill-review.md`.

## Outcome in one table

| Measure | Before | After |
|---|---|---|
| Unit + feature cases | 7,357 | AFTER_CASES |
| Container cases | 267 | AFTER_CONTAINERS |
| `make check-all` | 3 min 59 s | AFTER_CHECKALL |
| Run A wall (unit + feature, no coverage) | 123 s | AFTER_RUNA |
| Set-up share of summed unit time | 0.46 | AFTER_SETUP |
| Coverage | 95.59 % | AFTER_COVERAGE |
| Domain mutants caught (of 1,085) | 974 | AFTER_MUTATION |
| Asserts without a message | 1,301 (counted by an ast scan; the audit's "~1,120" summed only the findings files) | 0 |
| Wrong `slow` markers | 27 | AFTER_SLOW |
| CI job timeout / hung-test timeout | none / none | 30 min / 120 s |

## What worked (keep)

1. **Measure, map, then propose** (`test-suite-care`). Run A and run B through the project's own
   `make` targets, with `PYTEST_ADDOPTS`, worked verbatim.
2. **Mutation as the reduction proof.** `make mutation` on `domain/` ran in 56 s to 1 min 45 s
   depending on machine load; an identical
   surviving-mutant set before and after a merge is the strongest evidence that nothing was lost.
   It was used for the domain merges and the class-3 domain drops.
3. **Reading assertions refutes coverage containment.** Of 4,908 "contained" cases, the mapping
   agents confirmed only 14 droppable tests: shared lines are a hint, as the skill says.
4. **The clarity gate earned its cost.** 7.0 → 8.9 → 9.3. The first pass found four defects that
   would have broken builds (an impossible fix, an ordering hazard, a forbidden `pytestmark`, an
   undeclared API change).
5. **One shared brief for nine parallel mapping agents** produced uniform CSV rows that merged with
   no duplicate or missing id (3,439 + 184 = 3,623).
6. **The lead's own container gate** caught what builders could not run (no Docker in their
   sandbox), for example a consumer test importing a private testkit module.
7. **Measure-before-land** stopped two set-up proposals (P-2, P-4) whose estimated saving (by
   reading) was 20-60 % and whose measured saving was 0.

## What failed or cost time (fix)

| # | Where | What happened | Suggested fix (skill · file) |
|---|---|---|---|
| 1 | test-suite-care · measuring.md | Run A under xdist inflated per-test times: 14 of 32 slow candidates were false when run alone | add an "alone" confirmation step for W-2 |
| 2 | test-suite-care · scripts/phase_times.py | without xdist, fixture rows land in the phase file (KeyError 'phase') | write fixture rows to a separate file always |
| 3 | test-suite-care · overlap.py | `no_lines` inflated by code outside the measured package (tools, hooks, subprocesses) | split `no_lines` by coverage `source`/`omit` |
| 4 | test-suite-care · scripts | the map needs "the files each test covers"; no tool; the session wrote `covered_files.py` and a map refresher | ship both (the refresher with the empty-collection guard) |
| 5 | test-suite-care · waste.md W-1 | estimates "by reading" were wrong 2 of 4 times; sharing a WHOLE fixture among read-only tests saved ~95 %, sharing "the unchanging part" saved 0 | require timing the fixture's parts; prefer whole-fixture sharing for read-only tests |
| 6 | test-suite-care · waste.md W-3 | identical covered lines ≠ one equivalence class (generated per-field validators, multi-loop functions); "keep the first N" kept cases that hit two guards; three survivors were weaker than the dropped cases (caught by review) | survivor = the case that fails under the group's mutation; run mutmut on the touched module, not only a hand mutation; data-table rule rows need rule 8's every-rule-has-a-row test |
| 7 | test-suite-care · waste.md W-5 | a consolidating agent proposed dropping container tests that read the real store | repeat "never W-5 when the higher test reads the real store" inside the W-5 row |
| 8 | test-suite-care · waste.md W-7 | "no commit names the test" was true for 982 of 983 adversarial tests: commits name behaviours | evidence: a fix commit that touched the test file AND production code together |
| 9 | test-suite-care · waste.md W-8 | mutmut stops at the first kill (no per-test matrix); its serial stats phase took 11-14 min on the whole suite; its baseline failed on exotic parametrised ids | run per layer with the layer's tests; widen only survivors; discount message-only mutants |
| 10 | test-suite-care · "each tier" | `make test-containers` selects `integration or e2e`: the perf lane never ran | take tiers from the make lanes, not the folders |
| 11 | test-suite-care · scenario-map.md | the owner waived the sample check; the skill has no path for it | say what is recorded and whether class 3 may proceed |
| 12 | test-suite-care · report-template | inherited "X or Y" fixes became the PLAN's undecided items (gate 7.0) | one decided fix per broken-rule row |
| 13 | epic-delivery · team-and-briefs | the Agent tool's `isolation: worktree` based worktrees on the remote default branch, not the session's HEAD; in-worktree `git reset` failed on a read-only `.claude/hooks` | the lead creates worktrees itself (`git worktree add <path> <sha>`, outside the sandbox) and passes the path; the brief names the base commit |
| 14 | epic-delivery · stage loop | another session took the main checkout mid-delivery | a long, parallel epic session works in its own worktree from the start |
| 15 | epic-delivery · authority | "merge on green CI" blocked on a 32-min remote unit job; the owner wanted local-first | offer a "local only" authority option for solo sessions |
| 16 | implementer | builders used `sed -i`, heredoc or script rewrites (forbidden) 8 times, `pkill` once, `git stash` once; several left background runs they could not stop | brief lines: Makefile edits per recipe with Edit; never pkill/kill-by-pattern or git stash with parallel builders; never start a duplicate background run (or give builders TaskStop) |
| 17 | epic-planning · clarity-gate | the PLAN asserted code behaviour without reading it ("the assignment is refused"; a "taken before" bound) | a PLAN statement about current behaviour cites the code line it read |
| 18 | project-setup | scaffold dry-run listed `commons/`, `infra/` and `MEMORY.md` for a library; ast-grep missing at hand-off; uv/npm caches read-only in the sandbox | archetype-aware dry-run; check tools at hand-off; document `UV_CACHE_DIR`/`npm_config_cache` |
| 19 | cosmic-python · checklist rule 6 | mandates polyfactory; this repo's validated named builders meet the intent | allow validated builders; name `model_copy(update=)` as the smell |
| 20 | rule-learner | drafted a rule from a one-off task instruction; marked a wanted rule REJECT | an instruction for the current task is not a preference |

## Numbers of the session

- Subagents: about 45 (9 mappers, 1 fixture reader, 1 library reviewer, 1 consolidator, 1 drafter,
  2 clarity scorers' passes, 1 L2+L3 reviewer, ~27 builders and fixers, final reviewers).
- Wall time: about 9 hours, owner away for the last part.
- Commits on the change branch: AFTER_COMMITS_COUNT.
