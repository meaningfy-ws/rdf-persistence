# Q&A record: langstring-support (secondary; never groomed)

## Is there a consumer need now? (planner, 2026-11-22)

**Finding: no.** The first consumer, Mapping Workbench 2 (MWBv2), does not need a language-string
range today. Evidence, all read-only:

1. **Issue #209** has no comments and names no consumer change; its need is generic ("models in
   the SEMIC style"). It was found while writing the converter's XSD map (#196, uml-to-linkml), not
   asked for by the consumer. #196 and its comment (the consumer's rules 14-19) ask for no
   language string.
2. **The consumer's EA model** (`docs/mwb2_ea_model_v1.qea` on its branch `feat/v2-02-phase-b`,
   commit `5b83640`, the newest): 86 attributes, typed `xsd:string` 40, `xsd:anyURI` 11,
   `xsd:boolean` 6, `xsd:date`/`xsd:dateTime` 4, `xsd:nonNegativeInteger` 2, untyped 21; **none**
   typed `rdf:langString` or `rdf:PlainLiteral`. So the converter's refusal never fires on it.
3. **The consumer's spine** (`openspec/changes/*`, both worktrees): no change names #209 or a
   toolkit language-string change (D-12 would require it). Its v2-02 tasks are blocked by #240,
   #242, #243 and #274, never by #209. Its mentions of `rdf:langString` / `rdf:PlainLiteral`
   are **data**: IRIs inside ontology-fragment class paths (`dct:Location / locn:Address /
   rdf:PlainLiteral`) and the datatype-match rule of `v2-05-target-and-fragments`; they are
   stored as strings, not as tagged literals. Its ontology labels pick `rdfs:label` in English
   from loaded ontology graphs (`mwb2/services/ontology.py:41`), not from its own aggregates.
4. **The consumer's archived toolkit upgrade** (`v2-01-toolkit-upgrade`, DEC-8) took the 0.5.0
   "language tag kept in JSON-LD" change through unchanged; nothing compensates for a missing
   range.
5. **This repository's backlog** (`openspec/changes/README.md`, 2026-11-20) lists #209 under
   "Issues found on the way", not on the consumer's critical path.

## Open questions

| Id | Question | Recommendation | Default the EPIC assumes |
|---|---|---|---|
| OPEN-1 | Plan now, or park until the consumer asks? | **Park.** Shaped, not planned: no consumer model uses `rdf:langString`, the converter's refusal protects the one path by which such a model would arrive, and the representation (DEC-1) is cheaper to settle against a real model. Plan it when a consumer change names it (D-12), or when a SEMIC-style model is converted. | Parked (`shaped-not-planned`). |
| OPEN-2 | The read-modify-write tag loss for a `string` slot holding a tagged literal (seed notes, `mapper._value`): fix it apart, now, as a bug? | **Probe it now as a TINY bug issue** (refuse or keep, never drop silently); it does not need the new range and it is the "never dropped" half of #209 that applies to existing models. | Left in this EPIC (DEC-4), so it waits with it. |
| OPEN-3 | One value per language (a language map, DEC-35) or several (`rdf:langString` multivalued, e.g. `skos:altLabel`)? | Language map for a single-valued slot; a map of lists for a multivalued one. | DEC-1 as written. |
| OPEN-4 | Plain JSON: show the language map, or keep flattening to one string? | Show the map for a language-string slot (no tag dropped); keep the current flattening for any other slot. | DEC-3 as written. |

OPEN-3 and OPEN-4 matter only when the EPIC is planned.

## Question round parked (2026-11-22)

The owner parked the question round: the OPEN items above are unanswered. The PLAN stands
under the recommended answers; nothing is decided until the owner answers.
