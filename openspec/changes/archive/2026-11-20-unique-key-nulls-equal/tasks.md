EPIC: unique-key-nulls-equal (proposal.md, issue #202). Decisions: design.md PD-1 to PD-11, DEC-1 to DEC-3.

> Derives from: EPIC `unique-key-nulls-equal`. One stage (SMALL).

Every task: the failing test first, in the tier named; task gate `make test-changed
check-quality` (`make test-fast check-quality` where marked); commit body
`Refs: unique-key-nulls-equal <task> <PD>`. Builders never commit; the lead does.

## 1. Stage 1: absent values in tenant-scoped keys

- [x] 1.1 Lead (PD-9): before the first code task, check the two MODIFIED deltas
  (`specs/rp-aggregate-store/spec.md`: "Unique keys hold across the aggregates of a tenant" and
  "Existing key duplicates can be reported"; `specs/rp-generation/spec.md`: "A unique key across
  aggregates is declared with its scope") against the living specs on `develop`: each copies the
  current text and scenarios and changes only the option's sentences and scenarios. Accept: a
  diff of each requirement against the living one shows only those changes;
  `openspec validate unique-key-nulls-equal --strict` passes.
- [x] 1.2 Generator unit (PD-7), `tests/generator/unit/test_hard_check.py`. First, failing:
  TC-08 rewritten as a table: option at tenant scope → no problem; option with
  `rp_unique_scope: world` → a problem naming `rp_unique_scope: tenant`; `true` or unset → no
  problem. Then `checks/hard.py`. Lane: `make test-generator` (in `make check-all`). Accept: the
  table passes; reverting the hard.py change by hand fails its first row.
- [x] 1.3 Unit, schema (PD-1): `key_counts_absent` in `rp_core.yaml`, `make generate`, then
  `aggregate_keys()`. First, failing: `tests/unit/schema/test_aggregate_keys.py`, a table over an
  inline schema: `consider_nulls_inequal` false / true / unset → `key_counts_absent` True / False /
  False; TC-01 still equal (default False). Gate: `make test-fast check-quality` (generated
  domain model). Accept: the table passes; regenerated files are in the same commit.
- [x] 1.4 Unit, domain (PD-6): `absent_patterns` and `optional_value_patterns` in
  `core/domain/sparql.py`. First, failing, in the domain sparql tests: each renders the expected
  text; a bad variable name raises `SparqlError`; an IRI with `>` is escaped by `term()`. Gate:
  `make test-fast check-quality`. Accept: positive and negative row per helper.
- [x] 1.5 Unit, services (PD-2 to PD-5, PD-8), after 1.3 and 1.4: `ABSENT_KEY_VALUE` in
  `vocabulary.py`; `_values_of`, `_values`, `duplicates_query` in `unique_keys.py`. First,
  failing, in `tests/unit/persistence/test_session_unique_keys.py` on the fake store, the key of
  PD-8, one test per design worked example and per error-matrix row from "Add with an absence" to
  "Key without the option" (concurrency excepted), the store delta's "a present value differs",
  "an empty value is not an absence" and "a key without the option behaves as before" among them; plus
  `key_duplicates()` reporting `[Dune, <marker IRI>]` for two stored Dune / —. And a test that
  the toy `isbn_key`'s guard and duplicates query text are unchanged (G-4). Accept: all pass;
  the existing unique-key unit and adversarial tests pass unchanged.
- [x] 1.6 Integration (RISK-1), `tests/integration/store/test_unique_keys.py`: IT-NE-1, two
  concurrent adds of Dune / — on Fuseki, exactly one stored, the other `KeyConflict` (as IT-01);
  IT-NE-2, `key_duplicates()` on Fuseki reports the shared absence. Written by the builder, run by
  the lead in `make test-containers`. Accept: both pass on Fuseki.
- [x] 1.7 Docs: `user-manual/model.adoc` (the option on a key), `user-manual/store-and-read.adoc`
  (how a key behaves: absence counted, every-slot-absent rule PD-11, RISK-2; the marker in the
  report, RISK-3), `architecture/generation.adoc` section `[#hard-check]`, the item "a key
  annotated `rp_unique_scope`" (the refusal narrowed to scopes other than `tenant`). No new page.
  Accept: `make check-docs` passes; no text says the option is refused at tenant scope.
- [x] 1.8 Lead: `make check-all`, `make test-containers`, `make check-generated`; one review pass
  (SMALL); every new or changed scenario of both deltas and the issue's acceptance shown (`evidence/acceptance.md`).

## Roadmap

- [x] 1.1 ✓ · 1.2 ✓ · 1.3 ✓ · 1.4 ✓ · 1.5 ✓ · 1.6 ✓ · 1.7 ✓ · 1.8 ✓
  (1.2, 1.3 and 1.4 may run in parallel; 1.5 needs 1.3 and 1.4; 1.6 needs 1.5.)

## Verification

`make check-all` and `make test-containers` green; `openspec validate --all --strict`; the
clarity gate logged in `evidence/clarity-gate.md`.
