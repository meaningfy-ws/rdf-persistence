> Derives from: EPIC `langstring-support` (proposal.md, DEC-1 to DEC-9); issue #209; rule P-0041.

## Context

The EPIC is SMALL in two stages (DEC-6). The facts below come from two read-only sweeps and the
probes of 2026-11-28 (`inputs/qa.md`, "Re-shape round" and "Planning round"; probes in `temp/`,
not committed). Locked versions: rdflib 7.6.0, pydantic 2.14.2, pyld 3.3.0, linkml 1.12.1.

- **Toolkit types.** `sparql_term` (`rdf_persistence/model/technical/schema/rp_schema_templates.yaml:26-35`)
  is the precedent: a LinkML type with `repr` and the annotation `python_import` becomes a field of
  that Python type (`rdf_persistence_generation/extensions/pydantic_split.py:436-444, 533-540`).
  `SparqlTerm` (`core/domain/sparql.py:31-41`) already carries a pydantic core schema in a domain
  module. The schema lock holds classes and enums only, so an added type changes no lock.
- **Stock outputs for `uri: rdf:langString`.** SHACL gives `sh:datatype rdf:langString` (pyshacl
  accepts `"Dune"@en`, refuses `"Dune"` and `"Dune"^^rdf:langString`). The JSON-LD context term
  gets `"@type": "rdf:langString"`, under which pyld compacts `"Dune"@en` to `null`; without
  `@type` it compacts to value objects. TypeScript falls to `string`; its module model has no alias.
- **Read paths.** `Mapper.from_graph` → `_read` → `_value` (`persistence/services/mapper.py:256-269`)
  serves Python sessions, write guards, discussion, reference collections, activities, the relay
  and events (decoding), and tenancy; `_value` returns `term.toPython()`, which drops a tag. The
  API's GET and listing frame with pyld in `documents.render` (`api/services/documents.py:484-511`)
  and never call `_value`; plain JSON then collapses every value object (`_without_languages`,
  `:526-534`). Plain-JSON writes refuse any object other than `{"@id"}` (`_plain`, `:287-293`).
- **Write path.** `_term` → `rdf_term` (`schema_structure.py:172-194`) builds
  `Literal(value, datatype=datatype_of(range))`; on a `Literal` with a language it would build a
  term with both a language and a datatype.
- **Listing.** `typed_value` (`listing.py:183-203`) builds `"Dune"^^rdf:langString` for a lang slot;
  the filter then matches nothing.
- **Tags.** rdflib keeps a tag's case; `==` and `hash` ignore it, `rdflib.compare.isomorphic` does
  not.
- **DEC-8 measured.** Through `Documents.render`: `"1.5"^^xsd:decimal` and `xsd:float` read as JSON
  strings; `xsd:double` reads as a native number the compactor cannot match to its typed term, so the
  key is the full IRI. Writes through `triples_of` type all three correctly from numbers or strings;
  a JSON decimal number passes through a Python float. TypeScript says `number` for all three
  (`extensions/typescript.py:57-58`, `_scalar` `:97-107`); OpenAPI components say `number`. No
  committed `.ts` output has a decimal, double or float slot; float slots exist only in toolkit
  settings and adapters; no double slot exists.
- **Blast radius** (GitNexus, index ~219 commits behind): `Mapper._value` CRITICAL (13 processes),
  `_without_languages` HIGH, `rdf_term` and `_scalar` LOW. Both high ones went to the owner (P-1).

## Goals / Non-Goals

**Goals:**
- Stage 1: the P-0041 replacements and cleanups (DEC-7), with every IRI and every generated file
  unchanged; DEC-8's split fix.
- Stage 2: `lang_string` through the generator, the mapper, the documents, listing and the UML
  converter, with the spec deltas' scenarios proven.

**Non-Goals:** the EPIC's no-gos; normalising tag case (P-2); changing the API GET of a tagged
literal in a `string` slot (P-1); a TypeScript alias (P-4); `NaN`/`INF` doubles (RISK-3).

## Decisions

Each builder task names the PD it implements; the EPIC's DEC-n are not re-explained.

**Stage 1**
- **PD-1** `vocabulary.py`: `RP = Namespace(view.namespaces()[view.schema.default_prefix])` with
  `view = metamodel()` (already imported, `:42`); `PENDING_SINCE`, `RELAYED_AT`,
  `PUBLICATION_FAILED`, `ABSENT_KEY_VALUE` become `RP.pendingSince` etc. Same `URIRef`s (probed).
  Rejected: `split_uri(STARTED_AT)[0]` (still derived from another slot's IRI).
- **PD-2** One local-name helper, `local_of`, in `rdf_persistence_generation/uml/naming.py` (it owns
  the CURIE separator); `context.py` imports it instead of defining it, `classes.py:379` calls it.
  `naming.py`'s private `_local_part` goes.
- **PD-3** `uml/toolkit.py` `prefixes()` returns `{p: str(ns) for p, ns in view.namespaces().items()}`
  (equal to today's map, probed: 13 entries).
- **PD-4** The `XSD` dict in `uml/slots.py` becomes `XSD_RANGES`; its keys stay the CURIEs UML
  authors write. `rdflib.XSD` is then free to import there. The test copy in `test_uml_rules.py`
  follows the rename.
- **PD-5** One `linkml:Any` constant: `ANY_CLASS_URI` stays in `extensions/pydantic_split.py`;
  `extensions/typescript.py` imports it instead of its own `ANY_URI`.
- **PD-6** `_scalar` compares `view.expand_curie(type.uri)` with `rdflib.XSD` terms
  (`XSD.integer`, `XSD.boolean`, …) instead of CURIE strings.
- **PD-7** `core/domain/sparql.py`: a comment above `term()` saying why it does not use rdflib's
  `n3()`: rdflib 7.6 escapes only `\ " \r \n` (#270, #108), lets control characters into IRIs and
  accepts a language tag with a trailing newline. No code change.
- **PD-8** DEC-8, decimal and float: the JSON-LD context keeps their `@type`; TypeScript `_scalar`
  maps `xsd:decimal` and `xsd:float` to `string`; the OpenAPI component of such a slot says
  `{"type": "string"}`. The components are generated by the stock `JsonSchemaGenerator` in
  `rdf_persistence_generation/components.py` (`_generated`, `:41`) and post-processed per class by
  `_trimmed` (`:77`); a property whose slot's range has `xsd:decimal` or `xsd:float` among its type
  ancestors' `uri`s is rewritten there (the item schema when multivalued).
- **PD-9** DEC-8, double: `xsd:double` joins `NATIVE_JSON_DATATYPES` (`extensions/jsonld_context.py:43`),
  so its term has no `@type` and a read gives a JSON number under its own name. `Documents._valued`
  (`documents.py:277`) writes a JSON number on a double slot as `{"@value": n, "@type": xsd:double}`,
  so `3` is stored as `"3.0"^^xsd:double`, not `xsd:integer`. TypeScript and OpenAPI stay `number`.

**Stage 2**
- **PD-10** `LangString = Annotated[Literal, _LangStringSchema]` in a new domain module
  `rdf_persistence/core/domain/lang_string.py`. Validation accepts a `Literal` with a language, or a
  dict whose keys are exactly `@value` and `@language` (made a `Literal`; rdflib checks BCP 47 form);
  it refuses anything else with "a language string needs a language tag". Python dump keeps the
  `Literal`; JSON dump is the value object; JSON Schema is the value-object object schema. Tags are
  kept as given (P-2). The repr is `LangString`, never `Literal` (the generator aliases `typing`
  names).
- **PD-11** The type `lang_string` in `rdf_persistence/model/rp_core.yaml` (its first `types:`
  entry): `typeof: string`, `uri: rdf:langString`, `repr: LangString`, `python_import:
  rdf_persistence.core.domain.lang_string`. No metamodel lock change (the lock holds classes and
  enums). The lead runs `make generate`.
- **PD-12** JSON-LD context: `visit_slot` (`extensions/jsonld_context.py:73`) drops `@type` when the
  slot's range has `rdf:langString` among its type ancestors' `uri`s, keeping `@id` and `@container`.
- **PD-13** TypeScript: `range()` returns the inline type `{ "@value": string; "@language": string }`
  for such a range (P-4). OpenAPI: the same `_trimmed` post-pass as PD-8 rewrites a `lang_string`
  property (the stock generator gives `{"type": "string"}`, from `typeof: string`) to the value-object
  schema `{"type": "object", "required": ["@value", "@language"], "additionalProperties": false,
  "properties": {"@value": {"type": "string"}, "@language": {"type": "string"}}}`, the item schema
  when multivalued.
- **PD-14** Mapper: `_value` returns the `Literal` itself when the slot's range is `lang_string`;
  any other slot meeting a `Literal` with a language raises `StoredDataInvalid`
  (`core/domain/exceptions.py:217`) naming the class, the slot and the value's tag. `rdf_term`
  returns a tagged `Literal` unchanged for a `rdf:langString` range and raises `ValueError` for an
  untagged one (the model already refused it; this guards hand-built calls). `_read` sorts by
  `(str(term), term.language or "")`, so two tags of one text keep a stable order.
- **PD-15** Documents: `Documents.__init__` computes once the JSON names of every slot ranged
  `lang_string` (`json_name` over the view's induced slots; terms are global in the context);
  `_without_languages` leaves value objects under those keys; `_valued`/`_plain` accept a value
  object for those slots. Every other slot keeps today's flattening and refusal (P-1).
- **PD-16** Listing: `typed_value` raises `BadQuery` naming the slot for `=` and `~` on a
  `lang_string` slot; the OpenAPI listing parameters omit those operators for such slots. Sorting
  stays as it is.
- **PD-17** UML converter: `rdf:langString` maps to `lang_string` (`XSD_RANGES`); the toolkit module
  that defines a used type is imported (a `module_of_type` lookup on the toolkit index, beside the
  existing one for classes and shared slots, `convert.py:370-375`); `rdf:PlainLiteral` stays a
  `no_rule` whose message names `lang_string` (DEC-9).
- **PD-18** The toy `tests/fixtures/library/books.yaml` `Book` gains `titles` (multivalued,
  `lang_string`) for the feature and integration tests; the lead runs `make generate` and refreshes
  the lock and goldens (`make refresh-golden`). The DEC-4 test injects `"Arrakis"@en` into a
  `string` slot as raw triples (SHACL refuses it on API writes).
- **PD-19** CHANGELOG `[Unreleased]`: BREAKING for DEC-4 (the mapper refuses; the fix is to range
  the slot `lang_string` or clean the data; a tagged `skos:prefLabel` on `label` is the likely
  case), for plain JSON of a slot that becomes `lang_string`, and for DEC-8 (TypeScript `string`
  for decimal and float; double now a JSON number); Added for `lang_string` and the converter.

## Algorithm / approach

**Stage 1** is local edits behind tests. Proof that nothing else moved: `make check-generated`
(regenerates the toolkit and the toy, type-checks, then `git diff --exit-code` over every
`generated/` tree) shows no diff; the goldens under `tests/generator` are unchanged. DEC-8 changes no
committed generated file (no `.ts` output has these ranges; no double slot exists; float slots'
`@type` is kept).

**Stage 2**, one value end to end:

```
store   <book> ex:titles "Dune"@en, "Dune"@FR .
mapper  _value(slot=titles, range lang_string)  -> Literal("Dune", lang="en") (kept, not toPython)
model   Book.titles == [Literal("Dune", lang="FR"), Literal("Dune", lang="en")]   # sorted (str, lang)
edit    book.subtitle = "…"; session.replace(book)
mapper  _term -> rdf_term(range rdf:langString) -> the same Literal  -> graph isomorphic to the store
JSON    documents.render: pyld compacts under a term with no @type -> value objects;
        _without_languages skips "titles" -> [{"@value":"Dune","@language":"FR"}, …]
write   plain JSON {"titles":[{"@value":"Dune","@language":"en"}]} -> _plain accepts for titles
        -> expand -> "Dune"@en -> SHACL sh:datatype rdf:langString passes
```

A tagged literal in a `string` slot: `_value(slot=subtitle, range string)` sees `term.language`
and raises `StoredDataInvalid("Book.subtitle holds a language-tagged literal (@en); range the slot
lang_string")`; the session's read fails before any write, so nothing is written.

**Idempotency.** No new write operation. A read is pure; a read-modify-write of unchanged values
writes an isomorphic graph, so replaying it is a no-op on the store. The converter is
deterministic (byte-identical output on an unchanged model, as today).

### Anti-patterns
| Don't | Do instead | Why |
|---|---|---|
| `term.toPython()` for a lang slot | return the `Literal` | `toPython()` drops the tag |
| lower-case or otherwise rewrite a tag | keep it as given | a write-back would change the stored graph (P-2) |
| swap `term()` for `Literal.n3()` | keep `term()`, add the comment | reopens #270 and #108 (DEC-7) |
| `repr: Literal` in the type | `repr: LangString` | the generator reads `Literal` as `typing.Literal` |
| hand-edit `context.jsonld`, `.ts` or goldens | change the generator, `make generate`, `make refresh-golden` | AGENTS.md principle 2 |
| refuse in `documents.render` | refuse only in the mapper | the API GET keeps its behaviour (P-1) |
| a `LangString` class or a language map | the rdflib `Literal` | DEC-1, P-0041 |

## Error matrix

| Failure mode | How it is detected | Expected handling |
|---|---|---|
| Python: `Book(titles=["Dune"])`, `[Literal("Dune")]` or a typed literal | `_LangStringSchema` validator | `ValidationError` naming `titles` |
| Python: value object with a malformed tag (`"not a tag!"`) | rdflib's BCP 47 check in `Literal(...)` | `ValidationError` naming `titles` |
| Plain-JSON write: value object in a lang slot | `_plain` with the lang-slot set | accepted, stored tagged |
| Plain-JSON write: bare `"Dune"` in a lang slot | SHACL `sh:datatype rdf:langString` | `InvalidBody` (422) |
| Plain-JSON write: value object in a non-lang slot | `_plain` | `InvalidBody`, as today |
| JSON-LD write: `"Dune"@en` in a `string` slot | SHACL `sh:datatype xsd:string` | `InvalidBody`, as today |
| Store: tagged literal in a non-lang slot, read through the mapper | `_value` sees `term.language` | `StoredDataInvalid` naming class and slot (500 on the API's mapper paths); nothing written |
| Same value, API GET | not checked (P-1) | JSON-LD keeps the tag, plain JSON shows the text, as today |
| `rdf_term` called with an untagged value on a lang range | `rdf_term` | `ValueError` |
| Listing `?titles=Dune` or `?titles~Dune` | `typed_value` | `BadQuery` naming `titles` (400) |
| UML attribute typed `rdf:PlainLiteral` | `_plain_type` | `no_rule` naming the attribute and `lang_string`; nothing written |
| Plain-JSON write: `"dbl": 3` on a double slot | `_valued` (PD-9) | stored `"3.0"^^xsd:double`; SHACL passes |
| Plain-JSON write: `"dec": 1.5` on a decimal slot | `triples_of` | stored `"1.5"^^xsd:decimal`, as today (a JSON number passes a float: RISK-4) |
| Stage 1 moves an IRI or a generated file | `make check-generated`, the pinning tests (`test_session_unique_keys.py:502`, `test_uml_cli.py:293`, goldens) | the stage fails its gate |

## Risks / Trade-offs

- **RISK-1** (DEC-4, accepted by the owner, P-1): a consumer holding tagged `skos:prefLabel`s on
  `label` gets `StoredDataInvalid` on every mapper read of those aggregates. Likelihood low (API
  writes refuse it through SHACL; only loaded or migrated data can hold it), impact high for that
  consumer. Mitigation: the CHANGELOG entry names `label` and the fix; the consumer is told the
  change id (D-12).
- **RISK-2** Fuseki and tag case: whether Fuseki keeps `@FR` as given is unchecked. Mitigation: the
  integration test of the read-modify-write uses a mixed-case tag; a store that folds case fails it
  and the finding goes to the owner.
- **RISK-3** (accepted): a `NaN` or `INF` double read as a native JSON number is not valid JSON. No
  model has a double slot today; left as a known limit in the CHANGELOG line of PD-9.
- **RISK-4** (accepted, today's behaviour): a decimal sent as a JSON number passes a Python float and
  may lose precision; a client sends a string for exact decimals. Stated in the docs line of PD-8.
- **RISK-5** DEC-8 is BREAKING for a consumer whose TypeScript holds decimal or float slots (they
  become `string`). Mitigation: the CHANGELOG entry; the consumer is told (D-12).
- **RISK-6** The GitNexus index is far behind; blast radius was cross-checked with Serena. The lead
  runs the impact tool at stage start on whatever index the developer allows.

## Open Questions

None. P-1 to P-4 and Q-1 to Q-4 are answered (`inputs/qa.md`).
