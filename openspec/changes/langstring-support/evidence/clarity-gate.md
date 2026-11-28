# Clarity gate: langstring-support PLAN

2026-11-22, no run: shaped only. The EPIC is shaped (`proposal.md`, status shaped-not-planned);
no consumer need was found (`inputs/qa.md`), so design.md and tasks.md were not derived and there
is nothing for the gate to score. OPEN-1 asks the owner whether to plan now or park.

EPIC readiness check (lightweight, planner, 2026-11-22): pass. Problem stated with its evidence
(the refusal, the mapper's read-modify-write, plain JSON); appetite MEDIUM; five decisions as
DEC-1 to DEC-5 with rejected alternatives; rabbit-holes and no-gos present; golden-thread parents
cited. Undecided at bet level only what OPEN-2 to OPEN-4 name, each with a default the EPIC
assumes. Weakest point: DEC-4 leaves "refuse or keep" to a probe.

EPIC readiness check after the re-shape (lightweight, planner, 2026-11-28): pass. Appetite SMALL in
two named stages (DEC-6); the problem carries its evidence (#209, the P-0041 sweep's rows in
`inputs/qa.md`); DEC-1 to DEC-9 each with rejected alternatives; DEC-4's "refuse or keep" is decided
(refuse, Q-3); no-gos name the sweep's KEEP rows and `rdf:PlainLiteral`. Open at bet level only
DEC-8's direction (which side of JSON/TypeScript moves), left to the PLAN's probe. Weakest points:
DEC-8 is a behaviour change inside a cleanup stage, and the JSON-LD context term of `lang_string`
(rabbit-hole) is unverified. The PLAN (design.md, tasks.md) is next.

run 1, 2026-11-28, 8.5/10, fail (fresh gate subagent): G1 unowned rp-generation scenarios (2.1),
G2/G3 error-matrix rows contradict PD-10/PD-16, G4 RISK-4 cites a missing docs line, G5 task 2.9
location (pydantic_split.py, checks/hard.py), G6 PD-11 types section is new, G7 tasks lack
design.md#pd-n anchors, G8 PD-6 "…" and the unnamed PD-9 helper, G9 design.md 20,253 B over the
SMALL budget of 8,192 B, G10 langstring.feature's header names task 2.9. All ten folded in; run 2
reads only these gaps. The signed-off scenarios were not changed (G10 is a comment line).

run 2, 2026-11-28, 9.2/10, pass (fresh gate subagent, run 1's gaps only): G1 to G10 closed; G9 closed
by judgement (design.md 13,834 B, over the SMALL budget, but what remains is decisions and error
rows the builders need), scored as a Structure deduction.
