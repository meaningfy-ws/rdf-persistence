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
