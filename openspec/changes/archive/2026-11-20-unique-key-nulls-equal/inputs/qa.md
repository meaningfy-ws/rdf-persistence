<!-- Secondary input, never groomed: the owner's answers to the planner's open questions, relayed
     by the coordinator, 2026-11-20. The PLAN (../design.md PD-9 to PD-11) records them. -->

# Q&A: unique-key-nulls-equal

| Q | Question (planner, 2026-11-20) | Recommendation | Owner's answer (2026-11-20) | Recorded as |
|---|---|---|---|---|
| Q-1 | The EPIC lists `rp-generation` as modified, but the change had no delta for it, and the living spec still says the hard check SHALL refuse `consider_nulls_inequal: false`. | Add a MODIFIED delta of that requirement. | Accepted. The delta is written now, with the unsupported-scope scenario moved into it; the store requirement is MODIFIED too (gate run 1, gaps 1 and 2). | PD-9 |
| Q-2 | Should in-aggregate (unscoped) keys with the option change? | Leave them as they are; a follow-up issue if a consumer asks. | Accepted. Their validators already count two absent values as equal. | PD-10 |
| Q-3 | With every slot absent, one root per type and tenant may lack all key values (as SQL `NULLS NOT DISTINCT`). | Accept and document. | Accepted. | PD-11 |
