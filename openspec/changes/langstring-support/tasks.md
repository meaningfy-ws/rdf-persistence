> Derives from: EPIC `langstring-support` (proposal.md, DEC-1 to DEC-9); issue #209; rule P-0041.

Two stages, one PR each, off `develop` (DEC-6). Each task names the design.md decisions it
implements (PD-n) and the spec scenarios it proves; tests come first in the tier named. Waves run in
parallel on disjoint files; the lead does the tasks marked "lead". `make generate`, `make
refresh-golden` and `uv sync` are the lead's.

## 1. Stage 1: rdflib terms, and one form for decimal numbers

Wave A: 1.1 ∥ 1.2 ∥ 1.3 ∥ 1.4. Then the lead: 1.5, 1.6.

- [ ] 1.1 Relay plumbing IRIs from the `rp` namespace (PD-1). Files:
  `rdf_persistence/schema/services/vocabulary.py`; a unit test beside the vocabulary's tests that
  each of the four equals its literal IRI. Acceptance: that test, `test_session_unique_keys.py`,
  the relay and tenancy unit tests green, unchanged.
- [ ] 1.2 UML converter cleanups (PD-2, PD-3, PD-4). Files: `rdf_persistence_generation/uml/`
  `naming.py`, `context.py`, `classes.py`, `toolkit.py`, `slots.py`; `test_uml_naming.py` (a
  parametrised `local_of` case first), `test_uml_cli.py:293` (`prefixes()` equals the view's
  namespaces), `test_uml_rules.py` (the renamed table). Acceptance: `test_uml_golden` unchanged;
  generator unit tests green.
- [ ] 1.3 TypeScript and OpenAPI types from IRIs; decimal and float as strings (PD-5, PD-6, PD-8).
  Files: `rdf_persistence_generation/extensions/typescript.py`, `pydantic_split.py` (the shared
  constant only), `rdf_persistence_generation/components.py`; tests first in
  `test_ext_typescript.py` (one `_scalar` case per XSD type) and the components' unit tests, on a
  temporary schema with decimal, float and double slots. Acceptance: scenario "reading the three
  ranges" (its TypeScript and OpenAPI half) of the rp-generation delta; TypeScript goldens
  byte-identical.
- [ ] 1.4 Double as a native JSON number (PD-9). Files:
  `rdf_persistence_generation/extensions/jsonld_context.py`, `rdf_persistence/api/services/documents.py`
  (`_valued`); tests first: a generator unit test (the double term has no `@type`) and a
  `test_documents.py` round trip on a context generated from the same temporary schema (read: key
  `dbl`, value `1.5`; write: `3` stored as `"3.0"^^xsd:double`; decimal and float read as strings).
  The toy does not change in stage 1. Acceptance: scenarios "reading the three ranges" (its JSON
  half) and "a whole number written to a double slot"; `features/decimal_numbers.feature` runs with
  its steps.
- [ ] 1.5 Lead: the `term()` comment in `rdf_persistence/core/domain/sparql.py` (PD-7); the
  CHANGELOG lines of DEC-8 (PD-19, RISK-3, RISK-4, RISK-5).
- [ ] 1.6 Lead: `make check-generated` shows no diff (no IRI, no generated file moved: DEC-7);
  `make check-all`; one review pass; PR "rdflib terms, and one form for decimal numbers".

## 2. Stage 2: `lang_string`

Wave A: 2.1 ∥ 2.2 ∥ 2.3 ∥ 2.4. Then the lead: 2.5. Wave B: 2.6 ∥ 2.7 ∥ 2.8. Then 2.9, the lead's
2.10 and 2.11.

- [ ] 2.1 The value type (PD-10). Files: new `rdf_persistence/core/domain/lang_string.py`; unit
  tests first in `tests/unit/core/test_lang_string.py` (each row of the error matrix's Python
  lines; JSON dump and JSON Schema; a tag kept as given). Acceptance: those tests;
  `make check-architecture` (a domain module importing rdflib and pydantic only).
- [ ] 2.2 JSON-LD context term with no `@type` for a langString range (PD-12). Files:
  `extensions/jsonld_context.py`; a generator unit test first on a temporary schema with a
  `uri: rdf:langString` type: the term keeps `@id` and `@container`, has no `@type`, and pyld
  compacts `"Dune"@en` to a value object. Acceptance: that test; existing context goldens unchanged.
- [ ] 2.3 TypeScript inline value-object type and the OpenAPI value-object schema (PD-13). Files:
  `extensions/typescript.py`, `rdf_persistence_generation/components.py`; tests first in
  `test_ext_typescript.py` and the components' tests on the same temporary schema. Acceptance:
  the TypeScript and OpenAPI half of scenario "the generated targets of a language-string slot".
- [ ] 2.4 UML converter maps `rdf:langString`; `rdf:PlainLiteral` refused naming `lang_string`
  (PD-17). Files: `rdf_persistence_generation/uml/slots.py`, `convert.py`, the toolkit index
  (`uml/toolkit.py`); tests first: `test_uml_rules.py:512-517, 583-592` rewritten, a
  `tests/generator/feature/test_uml_import.py` case carrying `features/uml_langstring.feature`.
  Acceptance: scenarios "a language string" and
  "a plain literal" of the rp-uml-import delta (the `rp-generate` half once 2.5 has run).
- [ ] 2.5 Lead: the `lang_string` type in `rp_core.yaml` (PD-11) and `titles` on the toy `Book`
  (PD-18); `make generate`, the lock and `make refresh-golden`; then `make test-seed` in the
  background. Acceptance: scenario "the generated targets of a language-string slot" (SHACL and
  Python half); `make check-generated` clean after the commit.
- [ ] 2.6 Mapper keeps tags and refuses a tagged literal in another slot (PD-14). Files:
  `rdf_persistence/persistence/services/mapper.py`, `rdf_persistence/schema/services/schema_structure.py`
  (`rdf_term`); unit tests first (keep, refuse naming class and slot, stable order, `rdf_term` on a
  lang range), then `tests/integration/store/test_mapper.py`: a read-modify-write on Fuseki with
  `"Dune"@en, "Dune"@FR` stays isomorphic (RISK-2), and the raw-triple `"Arrakis"@en` in a `string`
  slot is refused with the store unchanged. Acceptance: scenarios "a read-modify-write keeps the
  tags" and "a tagged literal in a string slot"; `tests/unit/api/test_documents.py:586-605`
  unchanged (P-1).
- [ ] 2.7 Documents keep value objects for lang slots, both directions (PD-15). Files:
  `rdf_persistence/api/services/documents.py` (`__init__`, `_without_languages`, `_plain`/`_valued`,
  the `render` docstring); unit tests first in `test_documents.py`. Acceptance: scenarios "plain
  JSON of a language-string slot" and "a plain-JSON write of value objects".
- [ ] 2.8 Listing refuses `=` and `~` on a lang slot (PD-16). Files:
  `rdf_persistence/persistence/services/listing.py` (`typed_value`), the OpenAPI listing parameters;
  unit test first. Acceptance: scenario "a listing filter on a language-string slot".
- [ ] 2.9 Feature tests: the change's `features/langstring.feature` scenarios appended to
  `tests/feature/representations.feature` with their steps (no production code). Acceptance: they
  pass in `make test-changed`.
- [ ] 2.10 Lead: docs: `reference/uml-conventions.adoc#lang-string`, `howto/uml-to-linkml.adoc`, the
  user manual's generation page (the range, its JSON form, DEC-4's refusal); CHANGELOG (PD-19);
  `make check-docs`.
- [ ] 2.11 Lead: `make check-all`, `make test-containers` (the mapper and the store changed); one
  review pass; the consumer told the change id (D-12, RISK-1, RISK-5); PR "lang_string".

## Roadmap

- [ ] 1.1 ∥ 1.2 ∥ 1.3 ∥ 1.4 · [ ] 1.5 · [ ] 1.6 (stage 1 PR)
- [ ] 2.1 ∥ 2.2 ∥ 2.3 ∥ 2.4 · [ ] 2.5 · [ ] 2.6 ∥ 2.7 ∥ 2.8 · [ ] 2.9 · [ ] 2.10 · [ ] 2.11 (stage 2 PR)

## Verification

Each builder: `make test-changed check-quality`. The lead, per stage: `make check-generated` (stage 1:
no diff), `make check-all`, and for stage 2 `make test-containers`; `openspec validate
langstring-support --strict`; the PLAN gated (`evidence/clarity-gate.md`).
