<!-- SECONDARY INPUT: preserved, never groomed. The EPIC (../proposal.md) is the shaped truth. -->

# Seed: list the graphs loaded for an aggregate

## Seed text

GitHub issue #70, copied in `issue.md`. The consumer MWB2 (change `v1-06-project-resources`,
tasks 2.4 and 3.7) loads an ontology for a document aggregate and, in a later request, cannot find
the loaded graph's IRI: `Session._registered_loaded` is private and a flat, opaque IRI policy makes
the IRI underivable.

## What was read

- `rdf_persistence/services/session.py`: `READ_LOADED`, `_registered_loaded` (returns the registry's
  loaded graphs sorted by IRI), `_stored` (raises `NotFound`), `_graph` (raises `InvalidIri`),
  `load_graph`, `loaded_graph`, `replace_graph`, `remove`.
- `openspec/specs/rp-aggregate-store/spec.md` ("A loaded graph can be read back").
- Tests: `tests/unit/services/test_loading.py`, `tests/integration/store/test_loading.py`,
  `tests/unit/services/test_iri_policy_adversarial.py` (calls `_registered_loaded`).
- Docs: `docs/modules/ROOT/pages/howto/adopt.adoc` (Session table, "Reading a loaded graph back"),
  `docs/modules/ROOT/pages/questions.adoc`.
- `rdf_persistence/testkit/fakes.py`: `fake_session` wraps a real `Session`, so it needs no change.

## Questions and answers (developer, 2026-11-10)

1. **Order of the list.** The issue asks for load order; the registry records none. Options: sorted
   by IRI, no registry change (recommended), or record a load order in the registry (schema change,
   SMALL appetite). **Answer: sorted by IRI.**
2. **Delivery autonomy.** **Answer: commit, push, PR and merge on green CI; archive and close #70.**

## Observations by the leader (not questions)

- The issue sketches a sync `def loaded_graphs`; every store read is async, so it is `async def`.
- `_registered_loaded` returns `[]` for an aggregate that does not exist; the public read must check
  the aggregate first to raise `NotFound`.
