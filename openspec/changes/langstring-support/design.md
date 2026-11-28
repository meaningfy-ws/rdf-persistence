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
  gets `"@type": "rdf:langString"`, under which pyld cannot use the term for `"Dune"@en` and puts
  the value under its full IRI; without `@type` it compacts to value objects under the slot's name. TypeScript falls to `string`; its module model has no alias.
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
  so its term has no `@type` and a read gives a JSON number under its own name. Removing `@type`
  also removes how writes are typed, so `Documents` types them itself: one helper, applied to plain
  JSON bodies (in `_valued`, `documents.py:277`) and to JSON-LD bodies (before expansion,
  `documents.py:219`), wraps a JSON number or a string on a double term as
  `{"@value": v, "@type": xsd:double}`; a boolean there is refused (`InvalidBody`). So `3`, `3.0`
  and `"3"` are all stored as `xsd:double`, in both formats, as today. TypeScript and OpenAPI stay
  `number`.

**Stage 2**
- **PD-10** `LangString = Annotated[Literal, _LangStringSchema]` in a new domain module
  `rdf_persistence/core/domain/lang_string.py`. Validation accepts a `Literal` with a language, or a
  dict whose keys are exactly `@value` and `@language` (made a `Literal`); it then checks the
  built literal's `.language` against the toolkit's own tag pattern, the `fullmatch` that `term()`
  uses, moved from `sparql.py:24` to a shared constant in `core/domain` (rdflib's check accepts
  `"en\n"`, `"x"` and `""` gives an untagged literal). It refuses anything else with "a language
  string needs a well-formed language tag". Python dump keeps the
  `Literal`; JSON dump is the value object; JSON Schema is the value-object object schema. Tags are
  kept as given (P-2). The repr is `LangString`, never `Literal` (the generator aliases `typing`
  names).
- **PD-11** The type `lang_string` in `rdf_persistence/model/rp_core.yaml` (its first `types:`
  entry): `typeof: string`, `uri: rdf:langString`, `repr: LangString`, `python_import:
  rdf_persistence.core.domain.lang_string`. No metamodel lock change (the lock holds classes and
  enums), but every toolkit `rp-manifest.json` hashes `rp_core.yaml`, so each is regenerated, and a
  consumer's own generated-file check shows a diff after upgrading (CHANGELOG). The lead adds the
  type at stage start (task 2.0), so the converter's toolkit index sees it, and runs `make generate`
  once the generator changes are in (task 2.5).
- **PD-12** JSON-LD context: `visit_slot` (`extensions/jsonld_context.py:73`) drops `@type` when the
  slot's range has `rdf:langString` among its type ancestors' `uri`s, keeping `@id` and `@container`.
- **PD-13** TypeScript: `range()` returns the inline type `{ "@value": string; "@language": string }`
  for such a range (P-4). OpenAPI: the same `_trimmed` post-pass as PD-8 rewrites a `lang_string`
  property (the stock generator gives `{"type": "string"}`, from `typeof: string`) to the value-object
  schema `{"type": "object", "required": ["@value", "@language"], "additionalProperties": false,
  "properties": {"@value": {"type": "string"}, "@language": {"type": "string"}}}`, the item schema
  when multivalued.
- **PD-14** Mapper: `_value` returns the `Literal` itself when the slot's range is `lang_string`,
  and raises `StoredDataInvalid` (`core/domain/exceptions.py:217`) naming the class and the slot when
  that literal has no language (data stored before the slot became `lang_string`; a SPARQL
  migration, which bypasses the mapper, is the fix). Any other slot meeting a `Literal` with a
  language raises `StoredDataInvalid` naming the class, the slot and the tag. `rdf_term` returns a
  tagged `Literal` unchanged for a `rdf:langString` range and raises `ValueError` for an untagged
  one (`typed_value` already turns that into `BadQuery`). `_read` sorts by
  `(str(term), getattr(term, "language", None) or "")`: objects include `URIRef`s and blank nodes.
- **PD-15** Documents: `Documents.__init__` computes once the JSON names of every slot ranged
  `lang_string` (`json_name` over the view's induced slots; one name, one range, which PD-20
  guarantees); `_without_languages` leaves value objects under those keys; `_valued`/`_plain` accept
  a value object for those slots. Every other slot keeps today's flattening and refusal (P-1). On
  every write, both formats, a value object whose `@language` fails the shared tag pattern (PD-10)
  is refused as `InvalidBody`, so a malformed tag never reaches the commit's `term()`.
- **PD-16** Listing: `~` is already refused on a slot that does not hold text (`_contains`,
  `listing.py:407`) and the OpenAPI parameters already omit it; `=` reaches `rdf_term`, whose
  `ValueError` (PD-14) `typed_value` already turns into `BadQuery`. Task 2.8 only makes that
  message name the slot and pins both operators with a test.
- **PD-17** UML converter: `rdf:langString` maps to `lang_string` (`XSD_RANGES`). No import is
  added: every converted module imports `rp_annotations` (`convert.py:80, 374`), which imports
  `rp_core`, so the type is reachable. `rdf:PlainLiteral` stays a `no_rule` whose message names
  `lang_string` (DEC-9).
- **PD-18** The toy `tests/fixtures/library/books.yaml` `Book` gains `titles` (multivalued,
  `lang_string`) for the feature and integration tests; the lead runs `make generate` and refreshes
  the lock and goldens (`make refresh-golden`). The DEC-4 test injects `"Arrakis"@en` into a
  `string` slot as raw triples (SHACL refuses it on API writes).
- **PD-19** CHANGELOG `[Unreleased]`: BREAKING for DEC-4 (the mapper refuses; the fix is a slot of
  the consumer's own ranged `lang_string`, never a narrowed `label` (PD-20), or a SPARQL migration
  that cleans the data; a tagged `skos:prefLabel` on `label` is the likely case), for plain JSON of
  a slot that becomes `lang_string`, for DEC-8 (TypeScript `string` for decimal and float; double now
  a JSON number), and the regenerated manifests (PD-11); Added for `lang_string` and the converter.
- **PD-20** `rp-generate` refuses, naming the class and the slot: a `slot_usage` or an attribute
  that changes a slot's range to or from `lang_string` (the context's terms are per slot name, so
  one name must keep one range), and a `lang_string` slot among a class's unique-key slots (the
  store's guard matches terms exactly while Python equality ignores tag case). Rejected: type-scoped
  context terms (a second mechanism for a case no model has).

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
| trust rdflib's or pyld's tag check | the shared tag pattern (PD-10, PD-15) | both accept `"en\n"` |
| `term.language` on any RDF object | `getattr(term, "language", None)` | `URIRef` and `BNode` have none |
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
| Write, either format: a value object whose `@language` is malformed (`"en\n"`, `"not a tag!"`) | the shared tag pattern (PD-15) | `InvalidBody` (422), before the commit |
| Store: an untagged literal in a slot now ranged `lang_string`, read through the mapper | `_value` (PD-14) | `StoredDataInvalid` naming class and slot; a SPARQL migration is the fix |
| Model: a `slot_usage` or attribute changing a range to or from `lang_string` | `rp-generate` (PD-20) | refused naming class and slot |
| Model: a `lang_string` slot in a unique key | `rp-generate` (PD-20) | refused naming class and slot |
| Python: `titles` holds `"Dune"@en` and `"Dune"@EN` | rdflib equality ignores tag case | one of them is kept on write (RISK-7) |
| Plain-JSON or JSON-LD write: `"dbl": 3`, `3.0` or `"3"` on a double slot | the double helper (PD-9) | stored as `xsd:double`; SHACL passes |
| Write, either format: `"dbl": true` | the double helper (PD-9) | `InvalidBody` (422) |
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
- **RISK-7** (accepted): two values of one text whose tags differ only in case (`@en`, `@EN`) are
  equal in rdflib, so a graph keeps one of them. BCP 47 tags are case-insensitive, so they name the
  same language; no check is added. Tests compare tags through `.language` or
  `rdflib.compare.isomorphic`, never by model `==`.
- **RISK-6** The GitNexus index is far behind; blast radius was cross-checked with Serena. The lead
  runs the impact tool at stage start on whatever index the developer allows.

## Attack (2026-11-28)

A fresh subagent tried to break the PLAN (probes in `temp/attack/`). Fifteen findings, each folded
in: PD-20 (a range override; unique keys), PD-9 (string and JSON-LD writes to a double slot; a
boolean), PD-10 and PD-15 (malformed tags), PD-14 (untagged data in a lang slot; the sort key), RISK-7
(case-only duplicates), PD-16 and PD-17 narrowed (both were mostly there already), the fixture and
the feature files given owners (tasks 1.3, 1.4, 2.4), a Turtle scenario and a set comparison (the
rp-service-api delta), the stock compaction fact corrected (Context), the manifests (PD-11). Held up:
stage 1 changes no committed generated file; events and SSE dump through pydantic JSON mode, so
value objects round-trip there.

## Open Questions

None. P-1 to P-4 and Q-1 to Q-4 are answered (`inputs/qa.md`); the attack's findings are folded in
as above, as the planner's decisions (the SMALL appetite's two question rounds are spent).
