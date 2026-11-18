<!-- SECONDARY INPUT: preserved, never groomed. The EPIC (../proposal.md) is the shaped truth. -->

# Seed: the generators as a sibling package

This change has no seed of its own. Its inputs are those of the `manual-revision-notes`
initiative, read in place:

- [`../../manual-revision-notes/inputs/seed.md`](../../manual-revision-notes/inputs/seed.md): the
  developer's note "the generators (all of them) must be a sibling repo to the rdf_persistence
  (not within), and the tests ... for the generators shall be separate (e2e, feature, unit,
  integration, etc...)".
- [`../../manual-revision-notes/inputs/answers-2026-11-17.md`](../../manual-revision-notes/inputs/answers-2026-11-17.md):
  Q-3, "not a sibling repository but a sibling python module (sitting in the root folder) ...
  it could be a parameterised install ... as the generators are not needed in the runtime, only
  at development time". The slicing puts this change 4th, after `technical-models` and
  `otel-observability`, before `thematic-structure`.
- [`../../manual-revision-notes/inputs/improvements.md`](../../manual-revision-notes/inputs/improvements.md)
  group F: the ids this change owns, **F-1, F-2 (as Q-3 reshaped it), F-3, F-4**.
- [`../../manual-revision-notes/inputs/analysis.md`](../../manual-revision-notes/inputs/analysis.md)
  §5.3 (the constraints on `TOOLKIT_PACKAGE`) and §5.4 (size, tests, coupling, options).
- [`../../manual-revision-notes/inputs/keep.md`](../../manual-revision-notes/inputs/keep.md),
  "Structure and generation that stay": committed generated code, `check-generated`,
  `check-freshness`, linkml out of the runtime, `model/rp_*.yaml` flat.

The developer delegated the packaging choice (one or two distributions) to the lead; the lead's
choice is DEC-1 of the EPIC and may be overruled.
