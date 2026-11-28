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

## Owner's answers (2026-11-28)

- **OPEN-1: plan now.** The owner overrode the recommendation to park.
- **OPEN-2: keep it in this EPIC** (DEC-4 stays here). The owner asked whether rdflib's
  language-string support could carry it; it does, through OPEN-3's answer. Asked again in a
  follow-up round (what a `string` slot does on meeting a tagged literal), the owner chose
  **refuse, naming the slot**; recommended. Rejected: keep the tag in a `string` slot (the slot's
  type would no longer be what the model says).
- **OPEN-3 and OPEN-4: rdflib `Literal`, not a language map.** The owner asked whether rdflib's
  `Literal` can be adopted broadly, in the model and in plain JSON. Checked: rdflib is an allowed
  root package in `.importlinter`, and domain modules already import it
  (`core/domain/sparql.py`, `iris/domain/layout.py`), so DEC-1's reason for rejecting it does not
  hold. Offered three options (rdflib `Literal`; a toolkit `LangString` model; the language map as
  shaped); the owner chose **rdflib `Literal`**; recommended. The generated field is a
  Pydantic-validated `Annotated[rdflib.Literal, …]` that must carry a language; a multivalued slot
  is a list of them, so several values per language work (`skos:altLabel`); plain JSON, JSON-LD
  and TypeScript show each value as a JSON-LD value object `{"@value": …, "@language": …}`, so
  the JSON-LD context needs no `@language` container. Supersedes DEC-1 and DEC-3 as shaped and,
  for this range, DEC-35 of the SOA study (`LangString` as a language map).

## Re-shape round (2026-11-28): the P-0041 findings join the EPIC

The owner approved rule P-0041 (use rdflib's terms layer and utilities, #468) and asked to shape
"an epic as small as possible to address the lang strings and the rest of rdflib discoveries".
The findings came from two read-only sweeps with ast-grep, Serena and GitNexus (the index 212
commits behind; Serena's counts are the real ones):

- **Replace:** `rdf_persistence/schema/services/vocabulary.py:158-164` derives `PENDING_SINCE`,
  `RELAYED_AT`, `PUBLICATION_FAILED`, `ABSENT_KEY_VALUE` by `STARTED_AT.removesuffix('startedAt')`;
  a renamed `slot_uri` would move them silently. rdflib `Namespace` over the schema's `rp` prefix.
- **Small cleanups in the generator:** three copies of the `rsplit(":", 1)[-1]` local-name helper
  (`uml/naming.py:24`, `uml/context.py:33`, `uml/classes.py:379`); `uml/toolkit.py` `prefixes()`
  vs `SchemaView.namespaces()`; the `XSD` dict in `uml/slots.py:50-66` shadows `rdflib.XSD`;
  `ANY_URI = "linkml:Any"` defined twice; `extensions/typescript.py` `NUMBER_URIS`/`BOOLEAN_URI`
  compare CURIE strings.
- **Keep, documented:** `core/domain/sparql.py` `term()` and its escaping. rdflib 7.6.0
  `Literal._quote_encode` escapes only `\`, `"`, `\r`, `\n`, so `n3()` would reopen #270 and
  #108; `_is_valid_uri` lets control characters through; the language-tag regex is stricter
  (`fullmatch`). Skolem IRIs (`iris/domain/layout.py`) stay: rdflib's `skolemize` replaces the
  path, so it cannot scope one under its graph (PD-8a).
- **Outside P-0041, found on the way:** TypeScript types `xsd:decimal`, `double` and `float` as
  `number` while the JSON-LD context keeps their `@type`, so compacted JSON may carry them as
  strings (not probed).

| Id | Question | Recommendation | Owner's answer |
|---|---|---|---|
| Q-1 | How is the EPIC cut? | SMALL, 2 stages: rdflib cleanups first, then `lang_string` | **SMALL, 2 stages**; recommended |
| Q-2 | What does the converter do with `rdf:PlainLiteral`? | Keep refusing it; map only `rdf:langString` | **Keep refusing**; recommended |
| Q-3 | Risk of DEC-4 (refuse on read is BREAKING for stores holding tagged literals in `string` slots)? | Refuse, with a migration note; the first consumer's aggregates hold none | **Refuse, migration note**; recommended |
| Q-4 | The decimal/double/float mismatch: in this EPIC? | A separate issue | **Include in stage 1**; the owner overrode the recommendation |

## Planning round (2026-11-28): after the probes

Two fact-finding agents read the code (ast-grep, Serena, GitNexus on an index ~219 commits behind)
and ran probes in `temp/` (locked versions: rdflib 7.6.0, pydantic 2.14.2, pyld 3.3.0, linkml
1.12.1). Findings that moved the PLAN:

- **DEC-8, measured:** read back through `Documents.render`, `"1.5"^^xsd:decimal` and `xsd:float`
  come out as JSON strings (TypeScript says `number`); `xsd:double` comes out as a native number
  that the compactor cannot match to its typed term, so its key is the full IRI. Dropping `@type`
  for all three stores a JSON decimal as a double and trips SHACL.
- **JSON-LD context:** the stock term for a type with `uri: rdf:langString` carries
  `"@type": "rdf:langString"`; pyld then compacts `"Dune"@en` to `null`. Without `@type` it
  compacts to value objects.
- **Tag case:** rdflib 7.6 keeps a tag as given (`"x"@EN`); `==` ignores case,
  `rdflib.compare.isomorphic` does not. The EPIC's rabbit-hole said rdflib folds case: wrong.
- **Read paths:** the API's GET and listing frame with pyld (`documents.render`) and never call
  `Mapper._value`; the mapper serves Python sessions, write guards, the relay and events.
  `Mapper._value` is CRITICAL in GitNexus (13 processes), `_without_languages` HIGH; both went to
  the owner (AGENTS.md).
- **Plain-JSON writes** refuse any object other than `{"@id"}` today (`documents.py` `_plain`).
- **The toolkit's `label`** (`skos:prefLabel`, range `string`) is the slot most likely to hold
  tagged data; SHACL already refuses a tagged value on API writes.
- **Listing:** `?slot=Dune` on a lang slot builds `"Dune"^^rdf:langString` and matches nothing.
- **TypeScript:** the generator's module model has no type alias.

| Id | Question | Recommendation | Owner's answer |
|---|---|---|---|
| P-1 | DEC-4 scope (the API GET bypasses the mapper; `label` is the risky slot) | The mapper refuses; the API GET stays as it is; `label` stays `string`, the CHANGELOG tells consumers with tagged `prefLabel`s to fix their data | **As recommended** |
| P-2 | Normalise language-tag case? | Keep as given (a write-back stays isomorphic; no hidden rewrite) | **As recommended** |
| P-3 | DEC-8 fix | Split: decimal and float keep `@type`, TypeScript and OpenAPI say `string`; double becomes a native JSON number and plain-JSON writes coerce numbers to `xsd:double` | **As recommended** |
| P-4 | Listing filter on a lang slot; TypeScript value-object type | `BadQuery` for `=` and `~`; an inline TypeScript type | **As recommended** |
