# Hand-over: aggregate-guards, after stage 2

## Done
Stage 1, PR #334 (merged). Stage 2 (#309, delete rules), PR feat/delete-validators (merged by the
watch-and-merge command after this note).

## Decided since the PLAN
D-9 to D-14 (design.md, Delivery decisions). D-12 is the developer's: a delete rule refuses with
`Refused`, answered as a 409 `refused` problem that keeps the rule's message.

## Open
- Under the floor, stage 2: no tenant-deletion test with a delete rule registered (R2-W4); T11 is
  a plain transaction, not `delete_cascade` (R2-W5). Stage 1's R1-W2 to R1-W5 likewise.
- `ServiceKit.remove_with_files` has no route in the toolkit: a consumer route must pass
  `readable_by(caller, access)` as `may_read` (its docstring says so).

## Next
Close: task 3.2. Archive the change and comment on #305 and #309.

## Prompt
Act as the team lead. Close openspec/changes/aggregate-guards from handover.md: archive it and
comment on #305 and #309.
