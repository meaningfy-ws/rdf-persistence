# Clarity gate: narrowed-slot-override PLAN

run 1, 2026-11-27, 8.6/10, fail (fresh reviewer; actionability 9, specificity 8.5, consistency 8, structure 9.5, disambiguation 7.5, reference clarity 9)
- PD-2 rule 3 misses list invariance: a multivalued `list[A]` overridden by `list[B]` (B is_a A) is a mypy `[assignment]` error but goes unmarked; mark any range change on a multivalued slot.
- PD-2 ignores `inlined`/`inlined_as_list`: the same class range, or a subclass range, with different inlining (`A` vs `str`, list vs dict) goes unmarked; add rule 4: inlining differs → marked.
- PD-2 does not say what happens for a type against an enum; state it (marked).
- The error-matrix row "uri under string, not marked" is false: `sv.type_ancestors('uri') == ['uri']`; use a custom `typeof: string` type and add it to TC-2.
- RISK-2 is predictable, not low-likelihood: `unique_keys_validator.py.jinja` runs `for item in self.<slot> or []`, which over a single model yields field tuples; decide the shape now (the subclass overrides the inherited validator) instead of stop-and-escalate.
- proposal.md Impact says `attribute.py.jinja` is unchanged, but PD-1 edits it; align the two.
- The mark lands on the last line of a multi-line field (the `equals_number` branch), while mypy reports on the first; state that it is out of scope, or put the comment on the first line.
- TC-2 lacks the reverse-multivalued, mixin and type-range rows that the error matrix claims.

run 2, 2026-11-27, 9.0/10, pass (fresh reviewer; actionability 9.5, specificity 9, consistency 8.5, structure 9.5, disambiguation 9, reference clarity 9)
- List invariance: closed (PD-2 rule 3, matrix row, TC-2 case).
- Inlining: closed (PD-2 rule 4, two matrix rows, two TC-2 cases). Minor note: rule 4 compares raw `inlined`/`inlined_as_list`, not effective inlining (`sv.is_inlined`); an identifier-less class left implicit on one side can only add a harmless extra mark (`warn_unused_ignores = False`).
- Type against enum: closed (rule 5 and matrix row).
- uri row: closed (row corrected; custom `typeof: string` row added and in TC-2).
- RISK-2 / validator shape: closed (PD-5 decides the list-or-one loop; verified the template's `for item in self.<slot> or []` and that `keyed_slots` keeps multivalued slots only, so the narrowing subclass gets no validator of its own).
- proposal Impact vs PD-1: closed (Impact names the attribute template's two edits).
- Multi-line mark: closed (PD-6 puts `equals_number` on one line; verified the newline at `attribute.py.jinja:5-6` and no `, le=` continuation line in any generated file).
- TC-2 rows: closed (reverse multivalued, mixin, enum, type against enum, custom typeof present).
- NEW, open: RISK-1 says "task 1.1 runs `make generate`" and proposal Impact's last bullet says "task 1.1 reports any diff" and "toolkit and toy code unchanged", while tasks.md gives regeneration to the lead in 1.3 (AGENTS.md: only the lead runs `make generate`) and PD-5 changes every unique-key validator. Fix: point both to task 1.3 and say "unchanged apart from PD-5's validator lines".
- NEW, open: proposal DEC-4 says generated code only "gains a comment"; PD-5 changes each unique-key validator's loop. Fix: add "and each unique-key validator's loop accepts one value" to DEC-4.
- Both NEW items folded in before the commit of the PLAN (RISK-1 and proposal Impact name task
  1.3; DEC-4 names PD-5's loop).

Scenarios: signed off by the owner, 2026-11-27 (spec scenarios 1 to 3, design.md TC-1 to TC-6);
every recommendation accepted.
