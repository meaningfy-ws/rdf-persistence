> Derives from: EPIC `test-suite-grooming` (proposal.md); audit `tests/audit/report-2026-11-16.md`.

Gates (develop/agents.adoc): **TG** = `make test-changed check-quality`; **TF** =
`make test-fast check-quality` (after a change to `domain`, a port, the testkit or shared test
infrastructure). The lead runs `make check-all` and `make test-containers` once per stage.
The stages land as commit groups of one pull request (design.md D-1).

## 1. Stage 1: set-up and libraries

- [x] 1.1 PD-9: pytest-timeout (+ its pytester test), quarantine marker in every listed lane (+ its Makefile test), Hypothesis profiles in the root conftest (+ its test), mutmut `setup.cfg` and `make mutation`, polyfactory dropped and the rule-6 line in `testing.adoc`; `make mutation` run once, its killed/survived/untested summary pasted in design.md. Gate: TF.
- [x] 1.2 PD-9: the pytest-randomly trial (two seeds); adopt, or delete the dead flags and fill *Order dependence*. Gate: TF.
- [x] 1.3 PD-7: the six timed runs; the dist mode adopted; times recorded in design.md. Gate: TF.
- [x] 1.4 PD-1: `bootstrapped_template`. Gate: TG, then the file twice and reversed.
- [x] 1.5 (built, measured: no saving; not landed, see PD-2) PD-2: `ServiceKit` / `install_service` accept a `SchemaView`, test first; `toy_view()`. Gate: TF.
- [x] 1.6 PD-3: `TestReadOnlyListing`. Gate: TG, then the file twice and reversed.
- [x] 1.7 (built, measured: no saving; not landed, see PD-4) PD-4: module-scoped book triples. Gate: TG.
- [x] 1.8 PD-5: testkit `shared_key()` with the rp-testkit scenario test; `signer` fixtures. Gate: TF.
- [x] 1.9 PD-8: `poll_seconds` with the rp-testkit scenario test; in-process callers pass 0.01. Gate: TF.
- [x] 1.10 PD-6: re-time and change the slow markers; update `tests/audit/slow-markers.md` (runs last, alone on the machine, after stage 5). Gate: TG.

## 2. Stage 2: merged cases

- [x] 2.1 PD-10: P-20, P-21 (adapters, entrypoints). Gate: TG.
- [x] 2.2 PD-10: P-22, P-23 (domain). Gate: TF.
- [x] 2.3 PD-10: P-24, P-25 (generation). Gate: TG.
- [x] 2.4 PD-10: P-26 (testkit). Gate: TF.
- [x] 2.5 PD-10: P-27, P-28, P-29 (collaboration adversarial files; survivors of P-40/P-41 untouched). Gate: TG.
- [x] 2.6 PD-10: P-30, P-32, P-33 (other services files). Gate: TG.
- [x] 2.7 PD-10: P-31 (container tier; unit half under *Debt*, D-4), P-34. Gate: the lead's `make test-containers`.
- [x] 2.8 PD-16: write `tests/audit/refresh_map.py` and refresh the map. Gate: it reports no unknown id.

## 3. Stage 3: dropped tests

- [x] 3.1 PD-11: P-42 and P-44 (survivor case first), P-40, P-41, P-43. Gate: TG.
- [x] 3.2 PD-11: P-45 (map check first), P-49, P-50, P-51 (two pins kept, D-4). Gate: TG; the lead's `make test-containers`.
- [x] 3.3 PD-16: map refresh. Gate: as 2.8.

## 4. Stage 4: broken rules except 11

- [x] 4.1 PD-12: rule 21 renames and splits, rule 1 moves, rule 15 comments and `example.feature` deleted, the *Docs owed* pages. Gate: TF.
- [x] 4.2 PD-12: rules 17, 12 (perf moves included), 14, 10. Gate: TF; `make test-perf`.
- [x] 4.3 PD-12: rules 7, 9, 6. Gate: TF.
- [x] 4.4 PD-12: rules 3, 5, 13 (container tier). Gate: TF; the lead's `make test-containers`.
- [x] 4.5 The order-dependence failures recorded by 1.2: none were found (*Order dependence*).
- [x] 4.6 PD-16: map refresh; out-of-scope report rows copied under *Debt* in design.md. Gate: as 2.8.
- [x] 4.7 The accepted findings F-1 to F-8 of the stage 1-3 review and the lead's container gate (design.md). Gate: TF.

## 5. Stage 5: rule 11

- [x] 5.1 PD-13: messages in `tests/unit/services/`. Gate: TG.
- [x] 5.2 PD-13: messages in every other test folder except the fixer's files. Gate: TF.
- [x] 5.3 PD-13: messages in the nine files the fixer of 4.7 owned; a scan finds no assert without a message. Gate: TF.

## 6. Close

- [x] 6.1 PD-15: the after-measurements and `tests/audit/report-<date>-after.md`.
- [x] 6.2 The full review (PD-14), its Critical findings fixed; proposal reconciled (P-0004); archive the change.

## Roadmap

- [x] 1.1 · [x] 1.2 · [x] 1.3 · [x] 1.4 · [x] 1.5 · [x] 1.6 · [x] 1.7 · [x] 1.8 · [x] 1.9 · [x] 1.10 · [x] 2.1 · [x] 2.2 · [x] 2.3 · [x] 2.4 · [x] 2.5 · [x] 2.6 · [x] 2.7 · [x] 2.8 · [x] 3.1 · [x] 3.2 · [x] 3.3 · [x] 4.1 · [x] 4.2 · [x] 4.3 · [x] 4.4 · [x] 4.5 · [x] 4.6 · [x] 4.7 · [x] 5.1 · [x] 5.2 · [x] 5.3 · [x] 6.1 · [x] 6.2

## Verification

Every spec-delta scenario has its check (tests in 1.1, 1.8, 1.9; the mutation scenario by the
`make mutation` run in 1.1); each stage: `make check-all` and `make test-containers` green, one
L2+L3 review; at the end, the before/after report and `openspec validate --all --strict`.
