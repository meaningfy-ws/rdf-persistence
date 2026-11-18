# Hand-over: generator-package, after stage 2

## Done
Stage 1, PR #162 (merged). Stage 2 (tasks 2.1 to 2.5), PR into `develop` (merged by the
watch-and-merge command after this note): the generator is the sibling package
`rdf_persistence_generation`, with its testkit, four deprecation shims, the package-wide contracts,
its own test pyramid, lane and CI job.

## Decided since the PLAN
D-1 to D-20 (design.md, Delivery decisions). Stage 2: D-7 to D-20.

## Open
- #164: hardening of the guards, under the floor (D-16); item 1 closed by D-19's `ast` guard.
- #165: remove the four shims in 0.6.0 (PD-3, D-12).
- `evidence/docs-owed.md`: pages for the docs stage after stage 4.
- `make refresh-map` lists 56+ new test ids with no row; mapped before the archive (D-17).
- PR #161 (the developer's `.gitignore`) is still open (D-7).

## Next
Stage 3, task 3.1 (F-4: `python_package` / `public_package`). Read first: tasks.md §Stage 3,
design.md PD-6, D-3 (review set), D-4 (tester). Then re-index Serena and GitNexus (stage 2 moved
the generator).

## Prompt
Act as the team lead. Deliver stage 3 of openspec/changes/generator-package from handover.md,
in .worktrees/lead.
