EPIC: narrowed-slot-override (proposal.md). Decisions: DEC-1 to DEC-4 (proposal), PD-1 to PD-6 (design.md).

> Derives from: EPIC `narrowed-slot-override`. Issue #417.

Every task: test-first; task gate `make test-changed check-quality`; commit body
`Refs: narrowed-slot-override <task> <PD>` (`Refs: #417` on the task that closes it).
Builders never commit; the lead does and ticks this file.

## 1. One stage — branch `change/narrowed-slot-override`, one PR

- [x] 1.1 **unit + integration + code (the mark)** — design.md PD-1, PD-2, PD-6; spec scenarios 1
  and 2. First the failing tests: TC-1 and TC-5's integration half in
  `tests/generator/integration/test_generated_code_imports.py` (TC-1 must fail with the
  `[assignment]` error before the fix), TC-2 and TC-5's unit half in
  `tests/generator/unit/test_ext_pydantic_split.py`. Then PD-1's rename and PD-2's rule in
  `rdf_persistence_generation/extensions/pydantic_split.py`, and in
  `templates/pydantic/attribute.py.jinja` the condition (PD-1) and the one-line `equals_number`
  branch (PD-6); reword TC-3's message. Accept: TC-1, TC-2, TC-3, TC-5 pass; task gate green.
- [ ] 1.2 **integration + code (the unique-key check)** — after 1.1 (same test file); PD-5, spec
  scenario 3. First TC-4 (fails today with `AttributeError`), then the two lines of
  `templates/pydantic/unique_keys_validator.py.jinja`. Accept: TC-4 passes; the existing unique-key
  tests pass unchanged (RISK-2); task gate green.
- [ ] 1.3 **lead: regenerate** — after 1.2: `make generate`; commit the regenerated toolkit and toy
  files (`rp-manifest.json`, the unique-key validators' new lines). Accept: no generated `.py`
  line changes outside PD-5's validator lines and a real incompatible override (RISK-1; any other
  diff is reported, not fixed); `make typecheck-generated` green.
- [x] 1.4 **docs** — after 1.2; PD-4: `CHANGELOG.md` `[Unreleased]` *Fixed*. Accept:
  `make check-docs` green.
- [ ] 1.5 **lead** — scenario-map rows for TC-1, TC-2, TC-4, TC-5; `make check-all`; one review
  pass; PR into `develop` naming MWB2 EA round 26 (D-12) and asking MWB2 to run
  `rp-generate --check` on it against the branch (RISK-3); merged on green CI; #417 closed; archive.

## Roadmap

- [x] 1.1 · [ ] 1.2 · [ ] 1.3 · [x] 1.4 · [ ] 1.5 (1.4 may run beside 1.3)

## Verification

`make test-generator`, `make typecheck-generated` and `make check-all` green; the clarity gate on
this PLAN ≥ 9/10 (8.8 accepted, R-0005) before 1.1.
