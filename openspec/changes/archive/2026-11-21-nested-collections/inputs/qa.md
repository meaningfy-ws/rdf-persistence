<!-- Secondary input, never groomed: the owner's answers to the PLAN's open questions, relayed by the
     coordinator on 2026-11-20. design.md (PD-2, PD-6, PD-8, PD-11) carries them. -->

# Q&A: nested-collections PLAN, 2026-11-20

| Id | Question | Owner's answer |
|---|---|---|
| OPEN-1 | Does `delete_cascade` descend into nested collections? | No: direct members only; a nested collection is deleted as a member, its own members kept. |
| OPEN-2 | Rename `deep` to `transitive`? | No. Keep `deep=`; the spec delta writes the issue's `transitive=True` as `deep=True`. Why: it avoids breaking existing callers. (The coordinator's recommendation, superseding the planner's.) |
| OPEN-3 | May a nested collection have `nests: false`? | Yes (a leaf folder). |
| OPEN-4 | Does a deep read of a nesting collection list the nested collections? | No: items only. |

## Logged deviation (PD-11)

The EPIC's rabbit-hole prefers "one SPARQL property path" for the transitive walk. The PLAN does
not use one: membership triples sit in each collection's own named graph and the store has no
union default graph, so a property path cannot cross from one collection's graph to the next.
The read walks breadth first and the cycle check walks one skeleton read in memory. The bet is
unchanged; this is a PLAN-level deviation, not a re-shape.
