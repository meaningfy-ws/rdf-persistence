# Hand-over: technical-models, closed after stage 4

## Done
All four stages are merged: #144 (the split), #145 and #146 (templates), #150 (settings), and
#155 (the testkit records, the BDD feature, the docs, the full review's fixes and the
reconciliation of `proposal.md`), which the watch-and-merge command merges after this note. The
developer accepted the change without a demo (D-53, `evidence/acceptance.md`); no docs are owed
(`evidence/docs-owed.md`). Next comes the archive (`spec-stewardship`), which merges the three spec
deltas into `openspec/specs/`.

## Decided since the PLAN
D-1 to D-56 and the floor lists of stages 1 to 4 (design.md, Delivery decisions). Stage 4 adds:
the opt-in `field_name: slot` annotation in place of a LinkML alias rule (D-48, D-52, the
developer's choice to extend our generator); technical classes exempt from the stored-class rules,
with a non-technical module refused for holding one and a technical module for declaring a root
(D-49, D-55); every duration bounded at one year and the JWKS cooldown at 1 s and the TTL
(D-55); and the lead's slip of a doubled scenario map, repaired (D-54).

## Open
- **Upstream (external):** linkml/linkml#4160 (a multivalued `ifabsent`, the D-31 work-around),
  #4256 (a field named after an identifier alias) and #4257 (`alias` in `slot_usage`). When #4256
  lands, `field_name: slot` can give way to the generator's own option.
- **Floor items** for a later change: the stage 4 list in design.md (the `Seconds` type, the `RP_`
  prefix constant, the `secret` annotation's values, tighter security maxima, F-5, F-6) and the
  earlier stages' lists.
- `make refresh-map` lists 147 unmapped test ids, none from this change.
- **Process:** a union script over a conflict must refuse a hunk that spans the file (D-54). After
  every rebase, `make generate` and the whole `git status` (D-27, D-37).

## Next
Archived on 2026-11-17: the deltas merged into `openspec/specs/` (`rp-generation` + 4,
`rp-package-boundaries` ~ 1, the new `rp-settings` + 2), the change folder in
`openspec/changes/archive/2026-11-17-technical-models/` with its inputs and evidence. Nothing
continues from this change; its floor items and the upstream issues above are open for later
changes.
