# Clarity gate: nested-collections PLAN

run 1, 2026-11-20, 9.1/10, self-score (planner), pass

Attack (step 7, inline) before the run turned five counterexamples into fixes or rows: a cycle
closed inside one transaction (PD-5 overlay), the cascade refusing nested members (F-4, PD-2), a
refusal that would name hidden collections (PD-7), `nests` over a collection member class (PD-3),
and a racing save that turns a reached leaf into a nesting collection (PD-4 step 4, guard on
leaves too).

run 2, 2026-11-20, 8.5/10, reviewer gate (fresh), fail. Six gaps; all revised in the PLAN (PD-5
exact shape, PD-9 Conflict naming, PD-10 `graphs_with` literal, `WriteGuards.prepare` corrected,
three spec scenarios, PD-11 logged deviation). Owner decided OPEN-1 to OPEN-4 (`inputs/qa.md`).
The next run reads only those six gaps.

Run 1 notes. Weakest criterion: specificity of `GuardContext` (PD-5): its shape is named, its exact type
signatures are left to task 1.3. Open owner decisions OPEN-1 to OPEN-4 carry recommended
defaults; the PLAN holds with each default. Scenarios not yet signed off by the owner.

run 2, 2026-11-20, 8.5/10, fresh reviewer, fail
run 3, 2026-11-20, 9.1/10, fresh reviewer (gaps only), pass
