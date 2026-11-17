# Clarity gate: manual-revision-notes (design.md + tasks.md)

The earlier entry (run 1, 9/10) was the shaping agent's self-score; it is superseded by the
independent runs below.

- run 1, 2026-11-17, 9.0/10, pass. Independent, after the attack (rubric: actionability 9,
  specificity 9, consistency 8.5, structure 9, disambiguation 9.5, reference clarity 9). Gaps,
  folded in or left to the developer, no second run (R-0005):
  - proposal.md Impact says "no breaking change"; design.md "Breaking changes" lists five. The
    EPIC is not edited by the gate; the reconciliation (P-0004) or the developer corrects it.
  - DEC-1 says ML-DSA joins "with no toolkit release"; with PyJWT pinned exactly it needs a pin
    bump, and `technical-models` adds a pattern (its RISK-8). Recorded in RISK-1; DEC wording to
    the developer.
  - TC-60 named no way to build a predicate without an XML local name; now a direct `render` call
    (folded in).
  - PD-13 names "pyoxigraph's evaluation errors" without the class; the implementer reads it from
    pyoxigraph 0.5.13 (small, accepted).
  - OQ-3 (weak `ETag` behind a proxy) is open for the developer; the PLAN proceeds on DEC-4.
- run 2, 2026-11-17, 9.2/10, pass. Re-gate of the reconciliation only (DEC-1, PD-7, PD-9, TC-26b,
  TC-33, proposal Impact), checked against `mapper.py`, `reference_collections.py`,
  `entrypoints/problems.py`, `domain/exceptions.py`. Run 1's Impact and DEC-1 gaps are closed.
  Folded in: the rp-identity ML-DSA scenario and design worked example 3 still said "no change to
  the toolkit" (now: a toolkit release pinning a PyJWT that implements it); PD-7 now says
  `UnitOfWork` keeps its `ValueError` for an explicit value under 1 and its positional slot.
