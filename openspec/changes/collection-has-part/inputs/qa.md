<!-- Secondary input, never groomed. Q&A record of the shaping session of 2026-11-20. -->

# Q&A (2026-11-20)

Consumer triage: second after #196 and needed now. MWB2 `v2-02` task 2.1b (five collection
classes) cannot close without it, and collections in `v2-03` and `v2-05` use it.

1. **Q:** How should a collection class state `dct:hasPart` instead of `prov:hadMember`? The options
   were its own slot with `is_a: had_member`, an annotation the mapper rewrites, or deciding in the
   PLAN. **A (owner):** "just always and everywhere use dct hasPart, whatever the reliable and
   robust approach is". → DEC-1: the toolkit's default changes; no per-class option.
2. Open, to confirm in the PLAN: the collection's RDF type, today `prov:Collection` (OQ-1).
