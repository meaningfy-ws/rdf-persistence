# Q&A record: test-debt-paydown re-plan (secondary; never groomed)

Earlier rounds: the PLAN gate of 2026-11-17 (`inputs/handover.md`, `evidence/clarity-gate.md`).

## Round 2026-11-20 (the PLAN found stale after the thematic restructure)

| Question | Recommended | Owner's answer |
|---|---|---|
| How far should the update go? | rebase on themes now | **defer until wave 2** (nested-collections, delete-refuses-referenced) |
| Keep PD-11's moves (`tests/unit/tooling/`, `package/`, `test_tenant_move.py`)? | drop the moves | **keep the moves** |
| How does PD-12 fix stage 3? | re-run at stage start | **re-run at stage start** |
| Take #215 S1-S3? | take them | **take S1-S3** |

## Round 2026-11-21 (after the fact refresh, inputs/refresh-a.md to refresh-c.md)

| Question | Recommended | Owner's answer |
|---|---|---|
| G-6 / PD-7: the shapes cache saves < 10 %, the repeated `warm_up` costs 139 of 242 ms | warm once per shapes digest, keep G-6 | **warm once per shapes** (PD-7) |
| G-1: ~20 monkeypatches of toolkit code PD-1 does not list | narrow G-1, open an issue | **widen: triage all 20 here** (PD-17) |
| DEC-2 (one PR) vs P-0013 (a PR per stage) | one PR per stage | **one PR at the end** (PD-14) |

Lead's decisions, not asked (within the answers above): `test_private_transaction_pieces.py` stays
in its theme; `test_tenant_move.py` stays in `tests/unit/tenancy/` under its own import contract;
PD-4 uses 0.001 s (0 is refused by the settings); PD-10 covers the new hostile-contains test; PD-17's
five exception classes.
