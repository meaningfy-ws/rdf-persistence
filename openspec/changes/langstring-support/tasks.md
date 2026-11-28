> Derives from: EPIC `langstring-support` (proposal.md, DEC-1 to DEC-9); issue #209; rule P-0041.

Two stages, one PR each, off `develop` (DEC-6). Each task links the decisions it implements
(`design.md#pd-n`) and names the spec scenarios it proves; tests come first in the tier named. Waves
run in parallel on disjoint files; "lead" tasks are the lead's, as are `make generate`,
`make refresh-golden` and `uv sync`.

## 1. Stage 1: rdflib terms, and one form for decimal numbers

Lead: 1.0. Wave A: 1.1 ∥ 1.2 ∥ 1.3 ∥ 1.4. Lead: 1.5, 1.6.

- [x] 1.0 Lead: the fixture 1.3 and 1.4 share, `tests/fixtures/measures/measures.yaml`: a LinkML
  schema importing the toolkit, one aggregate `Measure` with `dec` (decimal), `flt` (float), `dbl`
  (double); no generated package (tests generate into `tmp_path`).
- [x] 1.1 Relay plumbing IRIs from the `rp` namespace ([PD-1](design.md#pd-1)). Files:
  `rdf_persistence/schema/services/vocabulary.py`; a unit test that each of the four equals its
  literal IRI. Acceptance: that test, `test_session_unique_keys.py`, the relay and tenancy unit
  tests green, unchanged.
- [x] 1.2 UML converter cleanups ([PD-2](design.md#pd-2), [PD-3](design.md#pd-3),
  [PD-4](design.md#pd-4)). Files: `rdf_persistence_generation/uml/` `naming.py`, `context.py`,
  `classes.py`, `toolkit.py`, `slots.py`; tests first: a parametrised `local_of` case in
  `test_uml_naming.py`, `prefixes()` against the view's namespaces in `test_uml_cli.py:293`, the
  renamed table in `test_uml_rules.py`. Acceptance: `test_uml_golden` unchanged; generator unit
  tests green.
- [x] 1.3 Types from IRIs; decimal and float as strings ([PD-5](design.md#pd-5),
  [PD-6](design.md#pd-6), [PD-8](design.md#pd-8)). Files: `extensions/typescript.py`,
  `extensions/pydantic_split.py` (the constant only), `rdf_persistence_generation/components.py`;
  tests first: one `_scalar` case per XSD type in `test_ext_typescript.py`, the components' tests on
  the measures fixture. Acceptance: the TypeScript and OpenAPI half of "reading the three ranges"
  (rp-generation delta); TypeScript goldens byte-identical.
- [x] 1.4 Double as a JSON number, writes typed in both formats ([PD-9](design.md#pd-9)). Files:
  `extensions/jsonld_context.py`, `rdf_persistence/api/services/documents.py`; tests first: a
  generator unit test (no `@type` on the double term) and `test_documents.py` on a context generated
  from the measures fixture. Then `features/decimal_numbers.feature` into `tests/feature/`, steps in
  `tests/feature/test_decimal_numbers.py` driving `Documents` on that context. Acceptance: "reading
  the three ranges" (JSON half), "a number or a string written to a double slot", "a boolean written
  to a double slot"; the feature passes.
- [x] 1.5 Lead: the comment of [PD-7](design.md#pd-7); the DEC-8 lines of
  [PD-19](design.md#pd-19) (RISK-3, RISK-4, RISK-5).
- [ ] 1.6 Lead: `make check-generated` with no diff (DEC-7); `make check-all`; one review pass; PR
  "rdflib terms, and one form for decimal numbers".

## 2. Stage 2: `lang_string`

Lead: 2.0. Wave A: 2.1 ∥ 2.2 ∥ 2.3 ∥ 2.4. Lead: 2.5. Wave B: 2.6 ∥ 2.7 ∥ 2.8 ∥ 2.9. Then 2.10;
lead: 2.11, 2.12.

- [ ] 2.0 Lead: the `types:` section of [PD-11](design.md#pd-11) in `rp_core.yaml`; the tag
  pattern moved into `rdf_persistence/core/domain/lang_string.py` ([PD-10](design.md#pd-10)),
  `sparql.py` importing it, its tests green. No `make generate` yet.
- [ ] 2.1 The value type ([PD-10](design.md#pd-10)). Files: `core/domain/lang_string.py`; tests
  first in `tests/unit/core/test_lang_string.py` (each Python row of the error matrix, `"en\n"`,
  `"x"`, `""` included; JSON dump and schema; a tag kept as given). Acceptance: "a value object
  becomes a tagged literal" and "an untagged value in a language-string field" (rp-generation
  delta), at the type's level; `make check-architecture`.
- [ ] 2.2 No `@type` on a langString term ([PD-12](design.md#pd-12)). Files:
  `extensions/jsonld_context.py`; a generator unit test first on a temporary schema with a
  `lang_string` slot (no `@type`; `@id`, `@container` kept; pyld compacts `"Dune"@en` to a value
  object under the slot's name). Acceptance: that test; context goldens unchanged.
- [ ] 2.3 TypeScript and OpenAPI value-object types ([PD-13](design.md#pd-13)). Files:
  `extensions/typescript.py`, `rdf_persistence_generation/components.py`; tests first in
  `test_ext_typescript.py` and the components' tests. Acceptance: the TypeScript and OpenAPI half of
  "the generated targets of a language-string slot".
- [ ] 2.4 Converter ([PD-17](design.md#pd-17)). Files: `rdf_persistence_generation/uml/slots.py`;
  tests first: `test_uml_rules.py:512-517, 583-592` rewritten; `features/uml_langstring.feature`
  carried by a case in `tests/generator/feature/test_uml_import.py`. Acceptance: "a language string"
  and "a plain literal" (rp-uml-import delta).
- [ ] 2.5 Lead: `titles` on the toy ([PD-18](design.md#pd-18)); `make generate`, the lock, the
  manifests ([PD-11](design.md#pd-11)), `make refresh-golden`; `make test-seed` in the background.
  Acceptance: the SHACL and Python half of "the generated targets of a language-string slot", and
  "a value object becomes a tagged literal" and "an untagged value in a language-string field" on
  the generated `Book`; `make check-generated` clean after the commit.
- [ ] 2.6 Mapper ([PD-14](design.md#pd-14)). Files: `persistence/services/mapper.py`,
  `schema/services/schema_structure.py`; unit tests first (keep; a tagged literal in a `string` slot
  refused through a session read and a write guard's read; an untagged literal in a lang slot
  refused; stable order with an IRI among the objects; `rdf_term` on a lang range); then
  `tests/integration/store/test_mapper.py` on Fuseki (a read-modify-write with `"Dune"@en,
  "Dune"@FR` stays isomorphic, RISK-2; the raw `"Arrakis"@en` refused, store unchanged).
  Acceptance: "a read-modify-write keeps the tags", "a tagged literal in a string slot", "an
  untagged literal in a language-string slot"; `tests/unit/api/test_documents.py:586-605`
  unchanged (P-1).
- [ ] 2.7 Documents ([PD-15](design.md#pd-15)). Files: `api/services/documents.py`; unit tests
  first in `test_documents.py`. Acceptance: "every format shows each title with its language", "a
  plain-JSON write of value objects", "a malformed language tag in a write".
- [ ] 2.8 Listing names the slot ([PD-16](design.md#pd-16)). Files:
  `persistence/services/listing.py` (`typed_value`, `_contains` messages); a unit test of `=` and
  `~`. Acceptance: "a listing filter on a language-string slot".
- [ ] 2.9 Generation refusals ([PD-20](design.md#pd-20)). Files:
  `extensions/pydantic_split.py` (`_incompatible_with`/`_overrides_incompatibly`, `:558`) and
  `rdf_persistence_generation/checks/hard.py` (`_bad_key_slot`, `:140`); generator unit tests first,
  a positive and a negative row each. Acceptance: "a range narrowed to a language string", "a
  language string in a unique key" (rp-generation delta).
- [ ] 2.10 `features/langstring.feature` into `tests/feature/` with its steps (no production code).
  Acceptance: it passes in `make test-changed`.
- [ ] 2.11 Lead: docs: `docs/modules/ROOT/pages/reference/uml-conventions.adoc#lang-string`,
  `docs/modules/ROOT/pages/howto/uml-to-linkml.adoc`,
  `docs/modules/ROOT/pages/user-manual/generated-classes.adoc` (the range, its JSON form, DEC-4's
  refusal, PD-20); the CHANGELOG lines of [PD-19](design.md#pd-19); `make check-docs`.
- [ ] 2.12 Lead: `make check-all`, `make test-containers`; one review pass; the consumer told the
  change id (D-12, RISK-1, RISK-5); PR "lang_string".

## Roadmap

- [x] 1.0 · [x] 1.1 ∥ 1.2 ∥ 1.3 ∥ 1.4 · [x] 1.5 · [ ] 1.6 (stage 1 PR)
- [ ] 2.0 · [ ] 2.1 ∥ 2.2 ∥ 2.3 ∥ 2.4 · [ ] 2.5 · [ ] 2.6 ∥ 2.7 ∥ 2.8 ∥ 2.9 · [ ] 2.10 ·
  [ ] 2.11 · [ ] 2.12 (stage 2 PR)

## Verification

Each builder: `make test-changed check-quality`. The lead, per stage: `make check-generated` (stage 1:
no diff), `make check-all`, and for stage 2 `make test-containers`; `openspec validate
langstring-support --strict`; the PLAN gated (`evidence/clarity-gate.md`).
