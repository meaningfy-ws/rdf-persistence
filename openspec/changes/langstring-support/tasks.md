> Derives from: EPIC `langstring-support` (proposal.md, DEC-1 to DEC-9); issue #209; rule P-0041.

Two stages, one PR each, off `develop` (DEC-6). Each task names the design.md decisions it
implements (PD-n) and the spec scenarios it proves; tests come first in the tier named. Waves run in
parallel on disjoint files; the lead does the tasks marked "lead". `make generate`, `make
refresh-golden` and `uv sync` are the lead's.

## 1. Stage 1: rdflib terms, and one form for decimal numbers

Lead first: 1.0. Wave A: 1.1 ∥ 1.2 ∥ 1.3 ∥ 1.4. Then the lead: 1.5, 1.6.

- [ ] 1.0 Lead: the measures fixture both 1.3 and 1.4 use: `tests/fixtures/measures/measures.yaml`
  (a LinkML schema importing the toolkit, one aggregate `Measure` with `dec` decimal, `flt` float,
  `dbl` double), no generated package (tests generate what they need into `tmp_path`).
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
  `test_ext_typescript.py` (one `_scalar` case per XSD type) and the components' unit tests, on the
  measures fixture. Acceptance: the TypeScript and OpenAPI half of scenario "reading the three
  ranges" (rp-generation delta); TypeScript goldens byte-identical.
- [ ] 1.4 Double as a native JSON number, writes typed in both formats (PD-9). Files:
  `rdf_persistence_generation/extensions/jsonld_context.py`, `rdf_persistence/api/services/documents.py`;
  tests first: a generator unit test (the double term has no `@type`) and `test_documents.py` on a
  context generated from the measures fixture (read: key `dbl`, value `1.5`; decimal and float read
  as strings; write, plain JSON and JSON-LD: `3`, `3.0`, `"3"` stored as `xsd:double`, `true`
  refused). Then `features/decimal_numbers.feature` appended to `tests/feature/` with steps in
  `tests/feature/test_decimal_numbers.py`, which drive `Documents` on that context (no served
  model). Acceptance: scenarios "reading the three ranges" (JSON half), "a number or a string written
  to a double slot", "a boolean written to a double slot"; the feature passes.
- [ ] 1.5 Lead: the `term()` comment in `rdf_persistence/core/domain/sparql.py` (PD-7); the
  CHANGELOG lines of DEC-8 (PD-19, RISK-3, RISK-4, RISK-5).
- [ ] 1.6 Lead: `make check-generated` shows no diff (no IRI, no generated file moved: DEC-7);
  `make check-all`; one review pass; PR "rdflib terms, and one form for decimal numbers".

## 2. Stage 2: `lang_string`

Lead first: 2.0. Wave A: 2.1 ∥ 2.2 ∥ 2.3 ∥ 2.4. Then the lead: 2.5. Wave B: 2.6 ∥ 2.7 ∥ 2.8 ∥
2.9. Then 2.10, the lead's 2.11 and 2.12.

- [ ] 2.0 Lead: the `lang_string` type in `rdf_persistence/model/rp_core.yaml` (PD-11), and the
  shared language-tag pattern moved from `core/domain/sparql.py:24` into
  `rdf_persistence/core/domain/lang_string.py` (`sparql.py` imports it; behaviour unchanged, its
  tests green). No `make generate` yet.
- [ ] 2.1 The value type (PD-10). Files: `rdf_persistence/core/domain/lang_string.py`; unit tests
  first in `tests/unit/core/test_lang_string.py` (each Python row of the error matrix, `"en\n"`,
  `"x"` and `""` included; JSON dump and JSON Schema; a tag kept as given). Acceptance: those tests;
  `make check-architecture`.
- [ ] 2.2 JSON-LD context term with no `@type` for a langString range (PD-12). Files:
  `extensions/jsonld_context.py`; a generator unit test first on a temporary schema with a
  `lang_string` slot: the term keeps `@id` and `@container`, has no `@type`, and pyld compacts
  `"Dune"@en` to a value object under the slot's name. Acceptance: that test; existing context
  goldens unchanged.
- [ ] 2.3 TypeScript inline value-object type and the OpenAPI value-object schema (PD-13). Files:
  `extensions/typescript.py`, `rdf_persistence_generation/components.py`; tests first in
  `test_ext_typescript.py` and the components' tests. Acceptance: the TypeScript and OpenAPI half of
  scenario "the generated targets of a language-string slot".
- [ ] 2.4 UML converter maps `rdf:langString`; `rdf:PlainLiteral` refused naming `lang_string`
  (PD-17). Files: `rdf_persistence_generation/uml/slots.py`; tests first:
  `test_uml_rules.py:512-517, 583-592` rewritten, and `features/uml_langstring.feature` carried by a
  case in `tests/generator/feature/test_uml_import.py`. Acceptance: scenarios "a language string" and
  "a plain literal" (rp-uml-import delta).
- [ ] 2.5 Lead: `titles` on the toy `Book` (PD-18); `make generate`, the lock, every toolkit
  `rp-manifest.json` (PD-11) and `make refresh-golden`; then `make test-seed` in the background.
  Acceptance: scenario "the generated targets of a language-string slot" (SHACL and Python half);
  `make check-generated` clean after the commit.
- [ ] 2.6 Mapper keeps tags and refuses what it cannot decode (PD-14). Files:
  `rdf_persistence/persistence/services/mapper.py`, `rdf_persistence/schema/services/schema_structure.py`
  (`rdf_term`); unit tests first: keep, a tagged literal in a `string` slot refused through a
  session read and through a write guard's read, an untagged literal in a lang slot refused, a
  stable order with an IRI among the objects, `rdf_term` on a lang range; then
  `tests/integration/store/test_mapper.py` on Fuseki: a read-modify-write with `"Dune"@en, "Dune"@FR`
  stays isomorphic (RISK-2), and the raw-triple `"Arrakis"@en` in a `string` slot is refused with
  the store unchanged. Acceptance: scenarios "a read-modify-write keeps the tags", "a tagged literal
  in a string slot", "an untagged literal in a language-string slot";
  `tests/unit/api/test_documents.py:586-605` unchanged (P-1).
- [ ] 2.7 Documents keep value objects for lang slots and refuse malformed tags (PD-15). Files:
  `rdf_persistence/api/services/documents.py` (`__init__`, `_without_languages`, `_plain`/`_valued`,
  the body check, the `render` docstring); unit tests first in `test_documents.py`. Acceptance:
  scenarios "every format shows each title with its language", "a plain-JSON write of value
  objects", "a malformed language tag in a write".
- [ ] 2.8 Listing names the slot when it refuses a lang filter (PD-16). Files:
  `rdf_persistence/persistence/services/listing.py` (`typed_value` message); a unit test of `=` and
  `~`. Acceptance: scenario "a listing filter on a language-string slot".
- [ ] 2.9 `rp-generate` refuses a range override to or from `lang_string` and a lang slot in a
  unique key (PD-20). Files: the generator's lint (where `_incompatible_with`,
  `pydantic_split.py:557`, and the unique-key checks live); generator unit tests first, one
  positive and one negative row each. Acceptance: scenarios "a range narrowed to a language string"
  and "a language string in a unique key" (rp-generation delta).
- [ ] 2.10 Feature tests: `features/langstring.feature` appended to `tests/feature/` with its steps
  (no production code). Acceptance: they pass in `make test-changed`.
- [ ] 2.11 Lead: docs: `reference/uml-conventions.adoc#lang-string`, `howto/uml-to-linkml.adoc`, the
  user manual's generation page (the range, its JSON form, DEC-4's refusal, PD-20); CHANGELOG
  (PD-19); `make check-docs`.
- [ ] 2.12 Lead: `make check-all`, `make test-containers` (the mapper and the store changed); one
  review pass; the consumer told the change id (D-12, RISK-1, RISK-5); PR "lang_string".

## Roadmap

- [ ] 1.0 · [ ] 1.1 ∥ 1.2 ∥ 1.3 ∥ 1.4 · [ ] 1.5 · [ ] 1.6 (stage 1 PR)
- [ ] 2.0 · [ ] 2.1 ∥ 2.2 ∥ 2.3 ∥ 2.4 · [ ] 2.5 · [ ] 2.6 ∥ 2.7 ∥ 2.8 ∥ 2.9 · [ ] 2.10 ·
  [ ] 2.11 · [ ] 2.12 (stage 2 PR)

## Verification

Each builder: `make test-changed check-quality`. The lead, per stage: `make check-generated` (stage 1:
no diff), `make check-all`, and for stage 2 `make test-containers`; `openspec validate
langstring-support --strict`; the PLAN gated (`evidence/clarity-gate.md`).
