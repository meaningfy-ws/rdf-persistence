<!-- Parents: issue #209 (inputs/seed.md); openspec/specs/rp-uml-import ("A UML class model converts
     to toolkit-conformant LinkML", scenario "a language string"); openspec/specs/rp-generation ("A
     generated field can hold a toolkit type"); openspec/specs/rp-service-api ("Plain JSON by
     default, RDF serialisations on request"); archived uml-to-linkml D-12 and its XSD-map row;
     archived manual-revision-notes TC-22 to TC-24b; archived soa-python-rdf-orm DEC-35 / ADR-15.
     Seeds: inputs/seed.md. Q&A: inputs/qa.md. -->

# EPIC: Language-tagged strings as a model range

> **Status: shaped, to be planned** (shaped 2026-11-22; owner's answers 2026-11-28 in
> `inputs/qa.md`). No consumer need yet: the first consumer's model has no `rdf:langString`
> attribute and no consumer change names this one (D-12). The owner chose to plan it now (OPEN-1).
> The PLAN (design.md, tasks.md) is not derived and the clarity gate has not run.

**Golden-thread parent:** issue #209; the refusal in `rp-uml-import` (scenario "a language string")
that this EPIC lifts; DEC-35 of the SOA study (`LangString` as a language map), superseded for this
range by DEC-1.

## Appetite

**MEDIUM.** One new capability, a language-string range, carried through the generator's targets
and the mapper's read and write; the converter and the plain-JSON document touched lightly.

## Why

A model cannot declare multilingual text: the toolkit has no range for `rdf:langString`, the UML
converter refuses such an attribute, and a tagged literal read into a `string` slot loses its tag
when written back through the Python path; plain JSON shows only the text. Models in the SEMIC
style use `rdf:langString` throughout, so the first such model to be converted stops here. No
consumer has one yet; the owner chose to plan it ahead of that need (OPEN-1).

## Solution outline

A toolkit range, `lang_string`, that any model slot may use. Its generated field holds rdflib
`Literal`s that carry a language; its SHACL says `sh:datatype rdf:langString`; its JSON-LD,
plain-JSON and TypeScript form is the JSON-LD value object `{"@value": …, "@language": …}`. The
mapper passes each tagged literal through, so a read-modify-write keeps every tag. A tagged literal
met in a `string` slot is refused, naming the slot. The converter maps `rdf:langString` (and
`rdf:PlainLiteral`) to it instead of refusing. Success: a value `"Dune"@en, "Dune"@fr` survives store, read, edit of another slot, write, and every
document form, isomorphic to the original graph.

## Key decisions

- **DEC-1** (owner, 2026-11-28, OPEN-3): the value is an **rdflib `Literal` with a language**,
  typed `Annotated[rdflib.Literal, …]` and validated by Pydantic; a multivalued slot is a list of
  them, so a language may hold several values. rdflib is an allowed package in the domain layer
  (`.importlinter`), so the generated classes may hold it. Rejected: a language map (DEC-35 of the
  SOA study; one value per language unless a map of lists, and it needs a JSON-LD `@language`
  container the stock generator lacks), a toolkit `LangString` model (a second type for what
  rdflib already has).
- **DEC-2**: a plain string and a language string are different ranges: `string` keeps meaning
  `xsd:string`; a model chooses per slot. An untagged literal in a `lang_string` slot is refused,
  never guessed into a language. Rejected: one range accepting both (the shape could not say which).
- **DEC-3** (owner, 2026-11-28, OPEN-4): plain JSON, JSON-LD and TypeScript show each value of a
  `lang_string` slot as a JSON-LD value object `{"@value": …, "@language": …}`; every other slot
  keeps today's flattening (`_without_languages`). Rejected: flattening it too (drops tags, the
  issue's complaint), a language map (DEC-1).
- **DEC-4** (owner, 2026-11-28, OPEN-2): a tagged literal met in a `string` slot is **refused,
  naming the slot** and pointing to `lang_string`; it stays in this EPIC. Rejected: today's silent
  loss, keeping the tag in a `string` slot (the slot's type would no longer be the model's).
- **DEC-5**: the range is generated, not hand-written: a LinkML type in the toolkit metamodel with
  its Python class through the toolkit-type mechanism (`rp-generation`), extended in
  `rdf_persistence_generation/` where a stock generator lacks the `Literal` field or the
  TypeScript value-object type. Rejected: hand-edited
  generated output (AGENTS.md principle 2).

## Rabbit-holes

- Language-tag validation beyond BCP 47 well-formedness (registry lookup, case folding rules other
  than the one rdflib applies).
- Listing filters on a language-string slot (`contains` per language, language preference): a
  separate need; the existing filters keep their behaviour on `string` slots.
- Pydantic and rdflib `Literal`: an arbitrary type needs its own core schema (validate from a
  `Literal` or a value object, serialise to the value object) and a JSON Schema; rdflib folds the
  language tag to lower case, so equality and round trips compare folded tags.
- `rdf:PlainLiteral` mixes tagged and untagged values; DEC-2 refuses the untagged one, which may
  surprise a model that used it loosely; the converter's message must say so.

## No-gos

- No language negotiation (`Accept-Language`, picking one language per request).
- No translation, no default-language fallback in the library.
- No change to slots ranged `string` other than DEC-4.
- No property-graph (LPG) encoding of tags.
- No consumer-specific term or model in the toolkit, its tests or its docs.

---

## What Changes

- A `lang_string` range in the toolkit metamodel: an rdflib `Literal` field, SHACL
  `sh:datatype rdf:langString`, and the JSON-LD value object as its JSON and TypeScript form.
- The mapper reads and writes it, every tag kept.
- **BREAKING (for a client of a slot that becomes `lang_string`)**: plain JSON shows value objects
  where it showed one string. No existing slot changes range.
- **BREAKING (DEC-4)**: a tagged literal in a `string` slot is refused, naming the slot, where its
  tag was dropped silently; a store holding such data must range the slot `lang_string`.
- `rp-uml2linkml` maps `rdf:langString` and `rdf:PlainLiteral` to the range; the refusal scenario
  in `rp-uml-import` is modified when the EPIC is planned.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rp-generation`: a language-string range across the generated targets.
- `rp-service-api`: a language-string slot keeps its tags in every document form.
- `rp-uml-import`: `rdf:langString` converts instead of being refused (delta written at planning).

## Impact

`rdf_persistence/model/` (the metamodel type, likely `rp_core.yaml`), `rdf_persistence_generation/` (the `Literal` field,
TypeScript, UML slot map `uml/slots.py`), `rdf_persistence/persistence/services/mapper.py`,
`rdf_persistence/api/services/documents.py`, docs `reference/uml-conventions.adoc#lang-string`,
`howto/uml-to-linkml.adoc`, the user manual's generation page. No new dependency.
