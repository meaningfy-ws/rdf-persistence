> Derives from: EPIC `langstring-support` (proposal.md, DEC-1 to DEC-9); issue #209; rule P-0041.

## Context

SMALL, two stages (DEC-6). Facts from two read-only sweeps, their probes and an attack, 2026-11-28
(`inputs/qa.md`; probes in `temp/`, not committed). rdflib 7.6.0, pydantic 2.14.2, pyld 3.3.0,
linkml 1.12.1. The facts each decision rests on are stated in that decision.

- The API's GET and listing frame with pyld (`documents.render`, `api/services/documents.py:484-511`)
  and never call the mapper; the mapper (`persistence/services/mapper.py`) serves sessions, write
  guards, the relay and events.
- rdflib keeps a tag's case; its `==` and `hash` ignore case, `rdflib.compare.isomorphic` does not.
- Blast radius (GitNexus, stale index, cross-checked with Serena): `Mapper._value` CRITICAL,
  `_without_languages` HIGH, both decided by the owner (P-1); `rdf_term`, `_scalar` LOW.

## Goals / Non-Goals

**Goals:** stage 1, the P-0041 cleanups (DEC-7) with every IRI and generated file unchanged, and
DEC-8's split fix; stage 2, `lang_string` end to end, the spec deltas' scenarios proven.

**Non-Goals:** the EPIC's no-gos; tag-case normalising (P-2); the API GET of a tagged literal in a
`string` slot (P-1); a TypeScript alias (P-4); `NaN`/`INF` doubles (RISK-3).

## Decisions

Tasks link each decision as `design.md#pd-n`. The EPIC's DEC-n are not re-explained.

**Stage 1**
- <a id="pd-1"></a>**PD-1** `schema/services/vocabulary.py`: `RP = Namespace(view.namespaces()[view.schema.default_prefix])`,
  `view = metamodel()` (`:42`); `PENDING_SINCE`, `RELAYED_AT`, `PUBLICATION_FAILED`,
  `ABSENT_KEY_VALUE` become `RP.pendingSince`, `RP.relayedAt`, `RP.publicationFailed`,
  `RP.absentKeyValue`: the same `URIRef`s (probed). Rejected: `split_uri(STARTED_AT)[0]`.
- <a id="pd-2"></a>**PD-2** One local-name helper, `local_of`, in `rdf_persistence_generation/uml/naming.py`;
  `context.py` imports it, `classes.py:379` calls it; `naming.py`'s `_local_part` goes.
- <a id="pd-3"></a>**PD-3** `uml/toolkit.py` `prefixes()` returns
  `{p: str(ns) for p, ns in view.namespaces().items()}` (equal to today's 13 entries, probed).
- <a id="pd-4"></a>**PD-4** `uml/slots.py`'s `XSD` dict becomes `XSD_RANGES` (keys stay the CURIEs UML authors
  write), freeing the name `XSD` for rdflib; `test_uml_rules.py`'s copy follows.
- <a id="pd-5"></a>**PD-5** `ANY_CLASS_URI` stays in `extensions/pydantic_split.py:112`;
  `extensions/typescript.py` imports it and drops its `ANY_URI` (`:59`).
- <a id="pd-6"></a>**PD-6** `_scalar` (`typescript.py:97-107`) compares `view.expand_curie(type.uri)` with
  `XSD.integer`, `XSD.decimal`, `XSD.double`, `XSD.float`, `XSD.boolean` instead of CURIE strings.
- <a id="pd-7"></a>**PD-7** A comment above `term()` in `core/domain/sparql.py`: rdflib 7.6's `n3()` escapes
  only `\ " \r \n` (#270, #108), lets control characters into IRIs and accepts a tag ending in a
  newline. No code change.
- <a id="pd-8"></a>**PD-8** Decimal and float (DEC-8, P-3): the context keeps their `@type` (reads are JSON strings
  today); `_scalar` maps them to `string`; in `rdf_persistence_generation/components.py`, `_trimmed`
  (`:77`, the per-class pass over the stock `JsonSchemaGenerator` output of `_generated`, `:41`)
  rewrites a property ranged over them to `{"type": "string"}` (the item schema when multivalued).
- <a id="pd-9"></a>**PD-9** Double (DEC-8, P-3): `xsd:double` joins `NATIVE_JSON_DATATYPES`
  (`extensions/jsonld_context.py:43`), so a read is a JSON number under the slot's name (today the
  key is the full IRI). With `@type` gone, writes are typed by a helper, `_typed_doubles`, run on
  plain-JSON bodies (`_valued`, `documents.py:277`) and JSON-LD bodies (before expansion, `:219`):
  a number or a string on a double term becomes `{"@value": v, "@type": xsd:double}`; a boolean is
  `InvalidBody`. TypeScript and OpenAPI stay `number`.

**Stage 2**
- <a id="pd-10"></a>**PD-10** `LangString = Annotated[Literal, _LangStringSchema]` in a new
  `rdf_persistence/core/domain/lang_string.py`, which also holds the language-tag pattern moved from
  `sparql.py:24` (`term()` imports it). It accepts a `Literal` with a language, or a dict whose keys
  are exactly `@value` and `@language` (made a `Literal`), then checks `.language` with that pattern's
  `fullmatch` (rdflib accepts `"en\n"` and `"x"`; `""` gives an untagged literal); anything else is
  refused: "a language string needs a well-formed language tag". Python dump: the `Literal`; JSON
  dump and JSON Schema: the value object. Tags kept as given (P-2). Repr `LangString`, never
  `Literal` (read as `typing.Literal`).
- <a id="pd-11"></a>**PD-11** `rdf_persistence/model/rp_core.yaml` gets a new `types:` section holding `lang_string`:
  `typeof: string`, `uri: rdf:langString`, `repr: LangString`, `python_import:
  rdf_persistence.core.domain.lang_string` (the `sparql_term` precedent,
  `technical/schema/rp_schema_templates.yaml:26-35`). No lock change (classes and enums only); every
  toolkit `rp-manifest.json` hashes `rp_core.yaml`, so all regenerate.
- <a id="pd-12"></a>**PD-12** `visit_slot` (`jsonld_context.py:73`) drops `@type` for a range whose type ancestors'
  `uri` is `rdf:langString`, keeping `@id`, `@container` (with it, pyld files the value under the full
  IRI; without it, value objects under the slot's name).
- <a id="pd-13"></a>**PD-13** TypeScript `range()` returns `{ "@value": string; "@language": string }` for that range;
  `_trimmed` (PD-8) rewrites such a property to `{"type": "object", "required": ["@value",
  "@language"], "additionalProperties": false, "properties": {"@value": {"type": "string"},
  "@language": {"type": "string"}}}`.
- <a id="pd-14"></a>**PD-14** Mapper. `_value` (`mapper.py:262-269`, today `term.toPython()`) returns the `Literal` for
  a `lang_string` slot; raises `StoredDataInvalid` (`core/domain/exceptions.py:217`) naming class
  and slot for an untagged one there (fix: a SPARQL migration), and naming class, slot and tag for a
  tagged literal in any other slot. `rdf_term` (`schema/services/schema_structure.py:172-194`)
  returns a tagged `Literal` unchanged for that range and raises `ValueError` for an untagged one.
  `_read` (`:256`) sorts by `(str(term), getattr(term, "language", None) or "")`.
- <a id="pd-15"></a>**PD-15** Documents. `__init__` collects the JSON names of `lang_string` slots (one name, one range:
  PD-20); `_without_languages` (`:526-534`) skips them; `_plain` (`:287-293`, today `{"@id"}` only)
  accepts a value object for them. Any write, either format, with a value object whose `@language`
  fails PD-10's pattern is `InvalidBody`, before the commit's `term()` sees it.
- <a id="pd-16"></a>**PD-16** Listing: `~` is refused by `_contains` (`listing.py:407`; OpenAPI already omits it); `=`
  reaches `rdf_term`'s `ValueError`, which `typed_value` (`:183-203`) turns into `BadQuery`. Both
  messages are made to name the slot.
- <a id="pd-17"></a>**PD-17** Converter: `XSD_RANGES` maps `rdf:langString` to `lang_string`; no import is added
  (every module imports `rp_annotations`, `convert.py:80, 374`, which imports `rp_core`);
  `rdf:PlainLiteral` stays a `no_rule` naming `lang_string` (DEC-9).
- <a id="pd-18"></a>**PD-18** The toy `tests/fixtures/library/books.yaml` `Book` gains `titles` (multivalued,
  `lang_string`). The DEC-4 tests inject `"Arrakis"@en` into a `string` slot as raw triples (SHACL
  refuses it on API writes).
- <a id="pd-19"></a>**PD-19** CHANGELOG `[Unreleased]`, BREAKING: DEC-4 (the mapper refuses; fix with a slot of one's
  own ranged `lang_string`, never a narrowed `label` (PD-20), or a SPARQL migration; tagged
  `skos:prefLabel`s on `label` are the likely case); plain JSON of a slot that becomes `lang_string`;
  DEC-8 (decimal and float `string` in TypeScript and OpenAPI; double a JSON number; send exact
  decimals as strings, RISK-4); the regenerated manifests (PD-11). Added: `lang_string`, the converter.
- <a id="pd-20"></a>**PD-20** `rp-generate` refuses, naming class and slot: a range changed to or from `lang_string`
  by a `slot_usage` or an attribute (`_incompatible_with`, called by `_overrides_incompatibly`,
  `extensions/pydantic_split.py:558`), and a `lang_string` slot in a unique key (`_bad_key_slot`,
  `checks/hard.py:140`). Rejected: type-scoped context terms.

## Algorithm / approach

**Stage 1**: local edits behind tests. `make check-generated` (regenerate toolkit and toy,
type-check, `git diff --exit-code` over `generated/`) shows no diff; goldens unchanged. DEC-8
changes no committed file (no `.ts` has these ranges; no double slot exists; float `@type` kept).

**Stage 2**, one value end to end:

```
store   <book> ex:titles "Dune"@en, "Dune"@FR .
mapper  _value(titles: lang_string)  -> Literal("Dune", lang="en")      (not toPython)
model   Book.titles == [Literal("Dune", lang="FR"), Literal("Dune", lang="en")]
edit    book.subtitle = "…"; session.replace(book)
mapper  rdf_term(lang range) -> the same Literal -> graph isomorphic to the store
read    render: term without @type -> value objects; _without_languages skips "titles"
write   {"titles":[{"@value":"Dune","@language":"en"}]} -> _plain accepts -> "Dune"@en -> SHACL passes
```

A tagged literal in a `string` slot: `_value` raises `StoredDataInvalid("Book.subtitle holds a
language-tagged literal (@en); range the slot lang_string")`; the read fails before any write.

**Idempotency.** No new write operation; reads are pure; a write-back of unchanged values is
isomorphic, so a replay is a no-op. The converter stays byte-identical on an unchanged model.

### Anti-patterns
| Don't | Do instead | Why |
|---|---|---|
| `term.toPython()` for a lang slot | return the `Literal` | drops the tag |
| rewrite a tag's case | keep it as given | the stored graph would change (P-2) |
| `Literal.n3()` for `term()` | keep `term()`, comment it | reopens #270, #108 |
| `repr: Literal` | `repr: LangString` | read as `typing.Literal` |
| hand-edit `context.jsonld`, `.ts`, goldens | change the generator, regenerate | AGENTS.md principle 2 |
| refuse in `documents.render` | refuse in the mapper only | P-1 |
| rdflib's or pyld's tag check | PD-10's pattern | both accept `"en\n"` |
| `term.language` on any object | `getattr(term, "language", None)` | `URIRef`, `BNode` have none |
| a `LangString` class or a language map | the rdflib `Literal` | DEC-1, P-0041 |

## Error matrix

| Failure mode | How it is detected | Expected handling |
|---|---|---|
| Python: `titles=["Dune"]`, `[Literal("Dune")]`, a typed literal | `_LangStringSchema` | `ValidationError` naming `titles` |
| Python: value object tagged `"not a tag!"` or `"en\n"` | `_LangStringSchema`, PD-10's pattern | `ValidationError` naming `titles` |
| Write, either format: value object tagged `"en\n"` or `"not a tag!"` | PD-15's body check | `InvalidBody` (422), before the commit |
| Plain JSON: value object in a lang slot | `_plain` | stored tagged |
| Plain JSON: bare `"Dune"` in a lang slot | SHACL `sh:datatype rdf:langString` | `InvalidBody` (422) |
| Plain JSON: value object in another slot | `_plain` | `InvalidBody`, as today |
| JSON-LD: `"Dune"@en` in a `string` slot | SHACL `xsd:string` | `InvalidBody`, as today |
| Mapper read: tagged literal in another slot | `_value` | `StoredDataInvalid` naming class, slot (500); nothing written |
| Same value, API GET | not checked (P-1) | as today |
| Mapper read: untagged literal in a lang slot | `_value` | `StoredDataInvalid` naming class, slot |
| `rdf_term`: untagged value, lang range | `rdf_term` | `ValueError` |
| Listing `?titles=Dune` | `typed_value` | `BadQuery` naming `titles` (400) |
| Listing `?titles~Dune` | `_contains` | `BadQuery` naming `titles` (400) |
| Model: range changed to or from `lang_string` | PD-20 | refused naming class, slot |
| Model: `lang_string` in a unique key | PD-20 | refused naming class, slot |
| `titles` holds `"Dune"@en` and `"Dune"@EN` | rdflib equality | one kept (RISK-7) |
| Either format: `"dbl"` `3`, `3.0`, `"3"` | `_typed_doubles` | stored `xsd:double`; SHACL passes |
| Either format: `"dbl": true` | `_typed_doubles` | `InvalidBody` (422) |
| Plain JSON: `"dec": 1.5` | `triples_of` | `xsd:decimal`, as today (RISK-4) |
| UML `rdf:PlainLiteral` | `_plain_type` | `no_rule` naming attribute, `lang_string` |
| Stage 1 moves an IRI or generated file | `make check-generated`, `test_session_unique_keys.py:502`, `test_uml_cli.py:293`, goldens | the gate fails |

## Risks / Trade-offs

- **RISK-1** (P-1, accepted): tagged `skos:prefLabel`s on `label` make every mapper read of those
  aggregates fail. Low likelihood (SHACL refuses them on API writes), high impact for that consumer.
  Mitigation: PD-19's entry; the consumer told the change id (D-12).
- **RISK-2** Fuseki may fold tag case. Mitigation: the integration read-modify-write uses `@FR`; a
  failure goes to the owner.
- **RISK-3** (accepted): a `NaN` or `INF` double is not valid JSON; no double slot exists. Noted in
  PD-19's entry.
- **RISK-4** (accepted, today's behaviour): a decimal sent as a JSON number passes a float; PD-19's
  entry says to send exact decimals as strings.
- **RISK-5** DEC-8 is BREAKING for a consumer with decimal or float in its TypeScript. Mitigation:
  PD-19; the consumer told (D-12).
- **RISK-6** The GitNexus index is far behind; blast radius was cross-checked with Serena; the lead
  runs impact at stage start on the index the owner allows.
- **RISK-7** (accepted): tags differing only in case are equal in rdflib, so a graph keeps one;
  BCP 47 tags are case-insensitive. Tests compare via `.language` or `isomorphic`, never model `==`.

## Open Questions

None: P-1 to P-4 and Q-1 to Q-4 are answered (`inputs/qa.md`). The attack's 15 findings are folded
into the decisions above (probes in `temp/attack/`).

## Delivery decisions

Taken by the lead during delivery (R-0007), for the owner to validate at the end.

**Stage 1**
- **D-1** (1.3) An OpenAPI property rewritten to `{"type": "string"}` keeps its `title` and
  `description`; only the numeric keywords (`minimum`, `maximum`, ...) go. PD-8 said the bare
  schema; the docs text is still true of a string.
- **D-2** (1.4) A double slot is one whose range type's IRI is `xsd:double` (no derived types: none
  exists). In JSON-LD the double terms are matched by JSON name across every class, so a body that
  writes a double by its full IRI or a renamed term is left to JSON-LD, untyped.
- **D-3** (1.2) `local_of` keeps `rsplit(":")`: rdflib's `split_uri` works on IRIs, not on the
  `pfx:Local` names UML authors write, and could change outputs on odd names (DEC-7).
- **D-4** (1.6) `make generate` after stage 1 moves only the manifests' generator input hashes; no
  generated output changes (DEC-7).
- **D-5** `Documents._valued` came out CRITICAL in GitNexus impact (7 API write processes). PD-9
  names that spot and the owner gated the PLAN; the builder added a "left as it was" row for a
  string, an integer and a reference slot beside each double row.
- **D-6** Parallel builders in one worktree cannot pass `make test-changed`: the freshness plugin
  stops every pytest session while generator sources are mid-edit. Builders ran their tests with
  `-p no:rdf_persistence_generation.testkit.freshness`; the lead regenerated and ran the full gates.
  Stage 2 gives each wave-A builder of a generator file its own worktree, or accepts the same.
- **D-7** `tests/measures.py` (1.4's helper, which runs `rp-generate` on the measures fixture into
  `tmp_path`) is the tenth file of `TOOL_USERS` (`test_library_tests_stay_apart.py`, TC-28), whose
  count test asks for a decision. Rejected: moving the generation into `tests/conftest.py`, already
  listed, which keeps nine but hides which tests run the generator.
