# Clarity gate: collection-has-part (design.md + tasks.md)

run 1, 2026-11-20, 9/10, self-score (planner), pass

| Criterion | Score | Note |
|---|---|---|
| Actionability | 9 | each task names its failing tests, files and acceptance command |
| Specificity | 9 | the migration step is given verbatim; every touched file listed, hand-written vs generated |
| Consistency | 9 | PD-2/PD-3 agree with F-1 to F-6; tasks cite PDs; spec delta gains the MODIFIED requirement it contradicted |
| Structure | 9 | template sections present; error matrix, 7 anti-patterns, 5 risks |
| Disambiguation | 8 | three owner decisions open (OPEN-1 to OPEN-3), each with a default that 1.1 applies |
| Reference clarity | 9 | file:line for every reader and fact |

Weakest: disambiguation (the OPENs) and the test specification's integration side (one Fuseki
test, IT-1; the restore and start-up paths are proved in the unit tier with an rdflib dataset).

Attack (step 7), counterexamples turned into PLAN content: no stored graph is typed
`prov:Collection` (PD-3: select by `rp:memberClass`); the consumer lock break (F-5, PD-5, TC-9,
RISK-5); the drafted DROP running before the rewrite (F-3, TC-6, error-matrix row on a failed
toolkit step); token rotation on the first toolkit migration with a step (RISK-1); a second slot
on `dcterms:hasPart` (RISK-2); the byte-identity test against 0.6.0 (F-8, OPEN-3); the drafted
empty `2__3.yaml` (anti-pattern, task 1.2 acceptance); the base spec still naming
`prov:hadMember` (PD-7, MODIFIED block).

Accepted DEC ids: none. Not yet scored by a fresh reviewer.

run 2, 2026-11-20, 9/10, fresh reviewer, pass
