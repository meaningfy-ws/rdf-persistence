# Q&A record: converter-hardening (secondary; never groomed)

Shaped by the planner as a subagent on 2026-11-22, which could not ask the owner. The questions it
could not decide are below; the PLAN is complete under each recommended answer, which it assumes
until the owner answers. The owner's answers go in the last column.

## Round 2026-11-22 (planner, from the seeds)

| Id | Question | Recommended | PLAN assumes | Owner's answer |
|---|---|---|---|---|
| OPEN-1 | #229 holds a deep restructure (one owner for package paths and exclusion, passes returning values instead of filling `Context`, `slots.py` split, the import-graph code out of `convert.py`, `Usage`/`Composed` generated or justified, a purity contract, indexes). Defer it to its own EPIC, after generator-module-cycles? | Defer: it breaks SMALL, and generator-module-cycles rewrites the import-graph half | deferred (DEC-1); #229 is closed by this EPIC with the deferred list moved to a new issue | |
| OPEN-2 | #260: a lone `dct:hasPart` role to the collection's own class fixes `member_class` to that class (a collection of collections); a self-role beside a role to another class stays nesting. A model that drew a lone self-role meaning nesting changes output | Yes, as the toolkit's `ReferenceCollection` description and `rp-reference-collections` say | yes (DEC-2, RISK-3) | |
| OPEN-3 | #258: read the roles file through the same reader as workflows, so a key given twice in one entry is refused too (stricter at service start) | Yes: one reader for the toolkit's YAML files | yes (DEC-5, RISK-6) | |
| OPEN-4 | A disk or folder error while writing: exit 2 (setup unusable) rather than 1 (model problems)? | Exit 2 | exit 2 (DEC-4) | |
| OPEN-5 | PD-3 stages inside `--out`, so a killed run (SIGKILL, power loss) leaves a hidden `out/.uml-write-*` folder that a consumer might commit. Accept it (reported as `stale-file` by the next run), stage elsewhere, or also write a `.gitignore` hint? | Accept, and have the how-to (task 1.8) say to add `.uml-write-*` to the consumer's `.gitignore`; staging elsewhere brings back `EXDEV`, and writing a `.gitignore` into `--out` is a file the consumer did not ask for | accept + how-to line (PD-3) | |

Planner's decisions, not asked (design.md): `immutable=1` only when no `-wal` file exists (PD-1);
a staging folder left by a killed run is reported, never deleted (PD-3); the whole-model check runs
only when a workflow is drawn, on this run's files (PD-4, DEC-3); `convert` takes the `Toolkit`
(PD-7).

Risk questions (R-0002), asked of the task's own context and answered from the code and the
archived changes: what could go wrong around the converter (EA writing the file during a read:
RISK-1; an old system SQLite: RISK-2; consumers whose models change output: RISK-3, RISK-6; the
cycle EPIC landing first: RISK-4; a slower run: RISK-5; scope growth: RISK-7).

## Question round parked (2026-11-22)

The owner parked the question round: the OPEN items above are unanswered. The PLAN stands
under the recommended answers; nothing is decided until the owner answers.
