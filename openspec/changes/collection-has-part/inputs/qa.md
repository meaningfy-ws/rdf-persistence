<!-- Secondary input, never groomed. Q&A record of the shaping session of 2026-11-20. -->

# Q&A (2026-11-20)

Consumer triage: second after #196 and needed now. MWB2 `v2-02` task 2.1b (five collection
classes) cannot close without it, and collections in `v2-03` and `v2-05` use it.

1. **Q:** How should a collection class state `dct:hasPart` instead of `prov:hadMember`? The options
   were its own slot with `is_a: had_member`, an annotation the mapper rewrites, or deciding in the
   PLAN. **A (owner):** "just always and everywhere use dct hasPart, whatever the reliable and
   robust approach is". → DEC-1: the toolkit's default changes; no per-class option.
2. Open, to confirm in the PLAN: the collection's RDF type, today `prov:Collection` (OQ-1).

## PLAN round (2026-11-20, owner via the coordinator)

3. **Q (OPEN-1):** change the collection class from `prov:Collection` to `dcmitype:Collection`?
   **A (owner):** yes. → DEC-4 in proposal.md; design.md PD-8.
4. **Q (OPEN-2):** the toy's lock breaks on the rename; re-baseline it (delete, regenerate) or raise
   the toy to version 2? **A (owner):** the recommendation, re-baseline. → design.md PD-9.
5. **Q (OPEN-3):** `test_combined_artefacts.py` compares with the 0.6.0 copies byte for byte; drop
   the byte-identity test and the three non-frame copies, keep the presence and frame-set tests?
   **A (owner):** the recommendation, yes. → design.md PD-10.
