<!-- SECONDARY INPUT: preserved, never groomed. The EPIC (../proposal.md) is the shaped truth. -->

# Seed: technical models (pointer)

This change is the second slice of the `manual-revision-notes` initiative. Its seeds live there
and are not copied:

- `../../manual-revision-notes/inputs/seed.md`: the developer's notes, verbatim (the notes on
  constants, on bare dict keys at `unique_keys.py:126`, and on models "under /adapters and under
  /services").
- `../../manual-revision-notes/inputs/answers-2026-11-17.md`: Q-1 (generate the settings) and Q-2
  ("we must separate the technical and the domain models ... then we truly see what are the DTOs
  that are technology bound, and what are the domain classes and objects"), and the slicing.
- `../../manual-revision-notes/inputs/improvements.md`: the ids this change owns.
- `../../manual-revision-notes/inputs/analysis.md` §1.4, §5.1, §5.2, §5.3.
- `../../manual-revision-notes/inputs/keep.md`: what must not change.

Ids owned: Q-1, Q-2, C-1, C-2, C-3, C-4, B-8, D-1, D-2, D-4. A-6 is covered by
`manual-revision-notes`. D-3 (`LogContext`) belongs to `otel-observability`; the technical-schema
mechanism here must take it. E (thematic packages) and F (the generator package) come later.

Rules in force: P-0007 (a concept-carrying dict is a model), P-0008 (reuse), P-0009 (deployment
values in central generated settings, protocol constants next to their use).
