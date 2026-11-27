# Q&A: narrowed-slot-override (secondary; never groomed)

2026-11-27. The owner reviewed the open issues with the planner, grouped them into three changes
and answered "accept recommendations". Every recommendation below is accepted.

| # | Question | Recommendation (accepted) | Becomes |
|---|---|---|---|
| 1 | How to group #417 with the other open issues | Its own TINY change, shipped first: it holds MWB2's EA round 26 merge. Not bundled with #402 (`typescript-toolkit-modules`, BREAKING, needs a migration note) so it is not slowed down | appetite, DEC-4 |
| 2 | Change or no change | An OpenSpec change, as for every bug fix (P-0020) | this change |
| 3 | Fix shape | Widen the predicate that already marks an incompatible override with `# type: ignore[assignment]` (PD-11 of `mwb2-file-resources`); the field keeps the narrowed type | DEC-1 |
| 4 | Test scenarios | A generated project reproducing #417 is mypy-clean; the ignore sits on the narrowed field and only there; a single-valued parent narrowed to a subclass range carries none; the existing `Chapter.label` pin keeps passing | DEC-3, design TC rows |
| 5 | Risks | None accepted: each RISK- gets a mitigation, as the leader's choice the owner may overrule | design.md Risks |
