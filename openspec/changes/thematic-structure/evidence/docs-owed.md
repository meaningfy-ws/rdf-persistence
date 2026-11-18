# Docs owed: thematic-structure

Task 7.2 writes the pages of the move (the theme map, the rule of DEC-3, the contracts). Found
while building, owed to the same task:

| Page | What is owed | From |
|---|---|---|
| `architecture/generation.adoc` (~361, the `pydantic_split` row ~270) | A target imports another target's module from that module's `python_package` (cross-target import, PD-3); a consumer's generated code imports `RpModel` from `rdf_persistence` (PD-8) | stage 1, D-9 W3 |
| `architecture/generation.adoc` (§target-kind ~356, step 2 failures ~588) | The kind/folder rule: toolkit run only, the segment before `generated`, the two exempt packages; its rule id (`TARGET_KIND`) | stage 1, D-9 W4 |
