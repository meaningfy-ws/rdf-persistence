<!-- Parents: issue #209 (inputs/seed.md); rule P-0041 (use rdflib's terms layer and utilities,
     #468); openspec/specs/rp-uml-import ("A UML class model converts to toolkit-conformant LinkML",
     scenario "a language string"); openspec/specs/rp-generation ("A generated field can hold a
     toolkit type"); openspec/specs/rp-service-api ("Plain JSON by default, RDF serialisations on
     request"); archived uml-to-linkml D-12 and its XSD-map row; archived manual-revision-notes
     TC-22 to TC-24b; archived soa-python-rdf-orm DEC-35 / ADR-15.
     Seeds: inputs/seed.md. Q&A: inputs/qa.md (OPEN-1 to OPEN-4, Q-1 to Q-4). -->

# EPIC: Language-tagged strings as a model range, on rdflib's terms

> **Status: shaped, to be planned.** Shaped 2026-11-22; re-shaped 2026-11-28 as a logged event
> (DEC-6): the owner's answers turned the value into an rdflib `Literal` (DEC-1) and added the
> findings of rule P-0041 as a first stage (Q-1 to Q-4 in `inputs/qa.md`). No consumer need yet
> (D-12); the owner chose to plan it now (OPEN-1). The PLAN is not derived and the gate has not run.

**Golden-thread parent:** issue #209; the refusal in `rp-uml-import` (scenario "a language string")
that this EPIC lifts; rule P-0041; DEC-35 of the SOA study (`LangString` as a language map),
superseded for this range by DEC-1.

## Appetite

**SMALL, two stages, one PR each** (Q-1). The language-string range rides the existing
toolkit-type mechanism (the precedent is `sparql_term`), so no new generation mechanism is built;
the rdflib cleanups are local and keep behaviour apart from the decimal fix (DEC-8).

- **Stage 1, rdflib terms:** the P-0041 replacements and cleanups (DEC-7) and the
  decimal/double/float mismatch (DEC-8).
- **Stage 2, `lang_string`:** the range end to end (DEC-1 to DEC-5).

## Why

A model cannot declare multilingual text: the toolkit has no range for `rdf:langString`, the UML
converter refuses such an attribute, and a tagged literal read into a `string` slot loses its tag
when written back through the Python path; plain JSON shows only the text. Models in the SEMIC
style use `rdf:langString` throughout, so the first such model to be converted stops here. No
consumer has one yet; the owner chose to plan it ahead of that need (OPEN-1).

The language-string value is an rdflib term (DEC-1), and rule P-0041 says RDF terms, namespaces and
their utilities come from rdflib. Its sweep found the toolkit already mostly does, with one fragile
spot (the relay plumbing IRIs, derived by cutting text off another IRI) and a handful of generator
cleanups. Doing them first leaves stage 2 on clean ground. A TypeScript/JSON mismatch for decimal
numbers was found on the way and joins stage 1 (Q-4).

## Solution outline

**Stage 1.** The relay plumbing IRIs (`PENDING_SINCE`, `RELAYED_AT`, `PUBLICATION_FAILED`,
`ABSENT_KEY_VALUE`) come from an rdflib `Namespace` over the schema's `rp` prefix; their values do
not change. The generator keeps one local-name helper, takes the metamodel's prefixes from
`SchemaView.namespaces()`, stops shadowing `rdflib.XSD`, defines `linkml:Any` once and compares XSD
types as expanded IRIs. `sparql.py` states why `term()` keeps its own escaping (rdflib's `n3()`
would reopen #270 and #108). A decimal, double or float slot gets one form in compacted JSON and
TypeScript. Generated output is byte-identical except where DEC-8 changes it.

**Stage 2.** A toolkit range, `lang_string`, that any model slot may use. Its generated field holds
rdflib `Literal`s that carry a language; its SHACL says `sh:datatype rdf:langString`; its JSON-LD,
plain-JSON and TypeScript form is the JSON-LD value object `{"@value": …, "@language": …}`. The
mapper passes each tagged literal through, so a read-modify-write keeps every tag. A tagged literal
met in a `string` slot is refused, naming the slot. The converter maps `rdf:langString` to it;
`rdf:PlainLiteral` stays refused (DEC-9).

Success: a value `"Dune"@en, "Dune"@fr` survives store, read, edit of another slot, write, and
every document form, isomorphic to the original graph; stage 1 changes no IRI and no generated file
outside DEC-8.

## Key decisions

- **DEC-1** (owner, 2026-11-28, OPEN-3): the value is an **rdflib `Literal` with a language**,
  typed `Annotated[rdflib.Literal, …]` and validated by Pydantic; a multivalued slot is a list of
  them, so a language may hold several values. rdflib is an allowed package in the domain layer
  (`.importlinter`). Rejected: a language map (DEC-35; one value per language unless a map of
  lists, and it needs a JSON-LD `@language` container the stock generator lacks), a toolkit
  `LangString` model (a second type for what rdflib already has; P-0041).
- **DEC-2**: a plain string and a language string are different ranges: `string` keeps meaning
  `xsd:string`; a model chooses per slot. An untagged literal in a `lang_string` slot is refused,
  never guessed into a language. Rejected: one range accepting both (the shape could not say which).
- **DEC-3** (owner, 2026-11-28, OPEN-4): plain JSON, JSON-LD and TypeScript show each value of a
  `lang_string` slot as a JSON-LD value object; every other slot keeps today's flattening
  (`_without_languages`). Rejected: flattening it too (drops tags), a language map (DEC-1).
- **DEC-4** (owner, 2026-11-28, OPEN-2, Q-3): a tagged literal met in a `string` slot is
  **refused, naming the slot** and pointing to `lang_string`, with a BREAKING entry and its fix in
  the CHANGELOG. The refusal is the mapper's, the one read path that writes back; the API's GET
  keeps its behaviour (`inputs/qa.md` P-1). Rejected: today's silent loss; keeping the tag in a `string` slot (the slot's type
  would no longer be the model's); refusing on write only (needs the original tag tracked through
  the session); a flag (a setting to retire).
- **DEC-5**: the range is generated, not hand-written: a LinkML type in the toolkit metamodel whose
  `repr` names the Python type, through the toolkit-type mechanism (`rp-generation`), extended in
  `rdf_persistence_generation/` where a stock generator lacks the TypeScript value-object type.
  Rejected: hand-edited generated output (AGENTS.md principle 2).
- **DEC-6** (owner, 2026-11-28, Q-1): **re-shape**: the P-0041 findings join this EPIC as stage 1,
  and the appetite drops from MEDIUM to SMALL because the toolkit-type mechanism already exists.
  Rejected: one stage (a bigger review, and the cleanups wait); two separate changes.
- **DEC-7** (P-0041): stage 1 takes exactly the sweep's REPLACE and SMALL CLEANUP rows
  (`inputs/qa.md`) and keeps its KEEP rows, with the `sparql.py` reason written in the code.
  Rejected: swapping `term()` for `n3()`, `skolem_iri` for `BNode.skolemize`, `_last_segment` for
  `split_uri` (each would regress; reasons in `inputs/qa.md`).
- **DEC-8** (owner, 2026-11-28, Q-4): the decimal/double/float mismatch is probed and fixed in
  stage 1, so that a value's compacted-JSON form and its TypeScript type agree. After the probe the
  owner chose the split fix (`inputs/qa.md` P-3). Rejected: a separate issue (the owner's call).
- **DEC-9** (owner, 2026-11-28, Q-2): the converter maps only `rdf:langString`; `rdf:PlainLiteral`
  stays refused, its message naming `lang_string`. Rejected: mapping it too (its untagged values
  would be refused at write time, a surprise far from the model).

## Rabbit-holes

- Language-tag validation beyond BCP 47 well-formedness (registry lookup, case folding rules other
  than the one rdflib applies).
- Listing filters on a language-string slot (`contains` per language, language preference): a
  separate need; the existing filters keep their behaviour on `string` slots.
- Pydantic and rdflib `Literal`: an arbitrary type needs its own core schema (validate from a
  `Literal` or a value object, serialise to the value object) and a JSON Schema. (Corrected at
  planning, `inputs/qa.md` P-2: rdflib keeps a tag's case; tags are kept as given.)
- The JSON-LD context term of a `lang_string` slot must not coerce `@type` (a value object may
  not carry both `@type` and `@language`); the stock `gen-jsonld-context` output for the type's
  `uri` is checked, not assumed.
- Stage 1 is a cleanup: anything that changes an IRI or a generated file outside DEC-8 is out.

## No-gos

- No language negotiation (`Accept-Language`, picking one language per request).
- No translation, no default-language fallback in the library.
- No change to slots ranged `string` other than DEC-4.
- No `rdf:PlainLiteral` mapping (DEC-9).
- No replacement of the KEEP rows of the sweep (DEC-7): `term()` escaping, skolem IRIs,
  `_last_segment`, the pyld and rdflib#3710 workarounds.
- No property-graph (LPG) encoding of tags.
- No consumer-specific term or model in the toolkit, its tests or its docs.

---

## What Changes

- Stage 1: the relay plumbing IRIs from an rdflib `Namespace` (same values); the generator's
  XSD/CURIE cleanups; the `sparql.py` comment; decimal/double/float agree between compacted JSON
  and TypeScript (DEC-8; possibly BREAKING for generated TypeScript or JSON, stated once probed).
- Stage 2: a `lang_string` range in the toolkit metamodel: an rdflib `Literal` field, SHACL
  `sh:datatype rdf:langString`, and the JSON-LD value object as its JSON and TypeScript form; the
  mapper reads and writes it, every tag kept.
- **BREAKING (for a client of a slot that becomes `lang_string`)**: plain JSON shows value objects
  where it showed one string. No existing slot changes range.
- **BREAKING (DEC-4)**: a tagged literal in a `string` slot is refused, naming the slot, where its
  tag was dropped silently; a store holding such data ranges the slot `lang_string`.
- `rp-uml2linkml` maps `rdf:langString` to the range; `rdf:PlainLiteral` stays refused.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rp-generation`: a language-string range across the generated targets; decimal numbers agree
  between JSON and TypeScript.
- `rp-service-api`: a language-string slot keeps its tags in every document form.
- `rp-uml-import`: `rdf:langString` converts instead of being refused (delta written at planning).

## Impact

Stage 1: `rdf_persistence/schema/services/vocabulary.py`, `rdf_persistence/core/domain/sparql.py`
(comment), `rdf_persistence_generation/uml/` (`naming.py`, `context.py`, `classes.py`,
`toolkit.py`, `slots.py`), `rdf_persistence_generation/extensions/typescript.py` and
`jsonld_context.py`, `rdf_persistence/testkit/shape_snapshot.py`.
Stage 2: `rdf_persistence/model/` (the metamodel type), `rdf_persistence_generation/` (TypeScript,
`uml/slots.py`), `rdf_persistence/persistence/services/mapper.py`,
`rdf_persistence/api/services/documents.py`, docs `reference/uml-conventions.adoc#lang-string`,
`howto/uml-to-linkml.adoc`, the user manual's generation page. No new dependency.
