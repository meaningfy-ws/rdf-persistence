# Hand-over: generator-package, after stage 4

## Done
Stage 1, PR #162; stage 2, PR #166; stage 3, PR #168 (merged). Stage 4 (tasks 4.1 to 4.4), the
docs stage (D-30) and the reconciliation of `proposal.md` (P-0004), PR into `develop` (merged by
the watch-and-merge command after this note). Acceptance waived by the developer
(`evidence/acceptance.md`, D-2). Every build box of `tasks.md` is ticked.

## Decided since the PLAN
D-1 to D-30 (design.md, Delivery decisions). Stage 4: D-26 to D-30.

## Open
- #164 (follow-ups under the floor, items 1–12; item 1 closed by D-19), #165 (shims out in 0.6.0).
- PR #161 (the developer's `.gitignore`) and #167 (another session's 0.5.0 changelog) are open.

## Next
Archive the change per `spec-stewardship` (`openspec archive generator-package --yes`), with
`make refresh-map` exiting 0 (it does on this head), as its own PR merged like a stage. Then
`thematic-structure` stage 1: its preconditions were checked on 2026-11-18 (ASM-1..3 hold; stale
PLAN references listed in the lead's `temp/ts-asm-check.md`, to record as its first D-n).

## Prompt
Act as the team lead. Archive openspec/changes/generator-package from handover.md, then deliver
thematic-structure stage 1, in .worktrees/lead.
