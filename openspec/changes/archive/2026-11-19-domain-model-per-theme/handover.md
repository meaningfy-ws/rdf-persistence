# Hand-over: domain-model-per-theme, after stage 1 (the last)

## Done
Stage 1 (tasks 1.1 to 3.1), PR #191, merged by the watch-and-merge command after this note.
Gates: `make check-all` green on dfb82ec6 (7379 + 97 + 1052 passed), `make test-containers` green
on 09a9489d (314 passed; after it only the spine, the docs and the scenario map changed),
`make check-spec` and `make refresh-map` green on a9fdb882. The tester after task 1.2 (5 findings,
D-5 fixed), one L2+L3 stage pass and the full review (L1, L2, L3 apart, L4+L5; D-7): 44 findings,
four groups re-labelled Critical and fixed (D-8 to D-11). The checker (2 unmet items, fixed as
D-12). Acceptance demo waived (`evidence/acceptance.md`); docs written in the stage
(`evidence/docs-owed.md`); proposal reconciled (P-0004); the change archived.

## Decided since the PLAN
D-1 to D-12 (design.md, Delivery decisions), the lead's, for the developer to validate (R-0007).
D-1 narrows PD-5 to a theme root; D-7 records the review set the developer asked for.

## Open
- Everything under the floor, collected in #192: the E-2 closure check (D-9), `is_stored_file`'s
  scan per call, the theme target declared on `GenerationTarget` (and the partial artefacts it
  would stop writing), `Run` carrying the targets, the `TOOLKIT_ROOTS` patching, test hygiene.
- GitNexus: the incremental re-index failed twice on a duplicate embedding key; the clean rebuild
  worked (D-3). An external tool's defect.

## Next
Release 0.7.0 with both changes (DEC-8), per `develop/index.adoc#release`: the changelog PR,
release-please's PR, `main` fast-forwarded to the tag; then move the getting-started example's pin
to `v0.7.0`. The same session does it after this merge.

## Prompt
Act as the release manager. Cut 0.7.0 per docs/modules/ROOT/pages/develop/index.adoc#release
(target-kind-from-the-model and domain-model-per-theme are merged), then move the getting-started
example's pin to v0.7.0 after the tag exists.
