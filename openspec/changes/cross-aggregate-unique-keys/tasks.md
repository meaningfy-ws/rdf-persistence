> Derives from: EPIC `cross-aggregate-unique-keys` (proposal.md). Two stages, one PR each into
> `develop`. Starts after `atomic-commit` (issue #83) is merged. Type: Implementation.

`T` and `U` are toy library tenants; `A`, `B`, `C`, `D` books of `T`. "Keys" is
`aggregate_keys(load_schema(TOY_SCHEMA))` (`tests/toy.py`); the session tests open
`fake_session(..., keys=keys)`. "The transaction" is atomic-commit's `Transaction`
(`services/session.py`): its private `_guards` list, `commit` and `_diagnose`, as built (PD-15;
a `KeyConflict` from the store is a diagnosis). Lists of IRIs in the tables are shown as lists; the code uses sorted tuples. The adversarial tester runs right after task
1.2, the riskiest (new invariant in the write path).

## 1. Declare and enforce (stage 1, PR 1)

- [x] 1.1 Declaration. Test first, in `tests/unit/generation/test_hard_check.py` (schema edits as
  in `test_boundary_check.py`'s `Edit`) and a new `tests/unit/services/test_aggregate_keys.py`
  (inline schemas). Then: in `rdf_persistence/model/rp_core.yaml`, the `rp_unique_scope` value of
  `RpAnnotation`, the enum `UniqueScope` (`tenant`), the classes `AggregateKey` and `KeyDuplicate`
  (PD-1, PD-3, PD-11); in `rdf_persistence/model/service/rp_service.yaml`, `ProblemSlug`
  `key_conflict` (PD-8); `make generate`. In `services/schema_structure.py`: `_keys_of` skips
  scoped keys; new `aggregate_keys(view)` (PD-3). In `generation/checks/hard.py`: the checks of
  PD-2, `ALLOWED_ANNOTATIONS` and `_annotated_elements`. In `testkit/conformance.py`,
  `class_kinds` counts only unscoped keys. In `tests/fixtures/library/books.yaml`, `Book` declares
  `isbn_key` (PD-13); `make generate`. Gates: `make test-fast`, `make check-quality`,
  `make clean-code`.

| ID | Input | Expected |
|---|---|---|
| TC-01 | toy schema | `aggregate_keys` == `[AggregateKey(key_name="isbn_key", root_class=bibo:Book, key_predicates=[bibo:isbn])]` (PD-16) |
| TC-02 | inline schema: abstract `Publication` with scoped key over `title`; roots `Book2`, `Magazine` `is_a Publication`; `Magazine` redeclares the key name over `issn` | two entries: `Book2` over `title`, `Magazine` over `issn` (nearest wins), each with its own class IRI |
| TC-03 | toolkit schemas and toy schema regenerated | Grant's validator and shape byte-identical to before; no validator or shape for `isbn_key`; `class_kinds("Book")` lacks `UNIQUE_KEYS`, `class_kinds("Grant")` has it |
| TC-04 | `Book` scoped key over `chapters` / over `authors` / over `id` / over `shelf` (not a slot) | `rp-generate` fails, a `unique_key` problem naming `Book`, `isbn_key` and the slot; no output changes |
| TC-05 | `rp_unique_scope: world` | fails, naming the value and the allowed `tenant` |
| TC-06 | scoped key on `Chapter` (owned part), on `Library` (tenant root), on a `database: system` root | fails, naming the class |
| TC-07 | unscoped `unique_keys` on `Book` | fails, naming `Book` and the key, telling to add `rp_unique_scope: tenant` |
| TC-08 | scoped key with `consider_nulls_inequal: false` | fails; with `true` or unset, passes |
| TC-08a | abstract mixin with an unscoped key over `title`, used by `Book` (root) and `Chapter` (owned) | passes; the key stays an in-aggregate key on `Chapter`; no cross-aggregate key for `Book` (PD-2) |

- [x] 1.2 Enforcement. Test first, in a new `tests/unit/services/test_session_unique_keys.py`
  (fake store, toy mapper) and `tests/unit/domain/test_sparql.py`. Then: `domain/sparql.py`
  `value_patterns`, `value_variables` (PD-12); `domain/exceptions.py` `KeyConflict` (PD-8); new
  `services/unique_keys.py` (`KeyClaim`, `KEY_HELD`, `claims`, `same_value`, `guard`, `diagnosis`;
  Algorithm); in `services/session.py`, `keys` on `Session` and `open_session`, the claims in the
  transaction, the guards and the diagnosis (PD-6, PD-9, PD-10), and the module and
  `find` docstrings (a key check with `find` is racy; declare a key instead); `Tenancy.__init__`
  and `_session` (`services/tenancy.py`); `fake_session` (`testkit/fakes.py`); export
  `KeyConflict` (`rdf_persistence/__init__.py`, as `Conflict`). Gates: `make test-fast`,
  `make check-quality`, `make clean-code`.

| ID | Input | Expected |
|---|---|---|
| TC-10 | add `A` isbn "1"; add `B` isbn "1" | second raises `KeyConflict(iris=[B], keys=["isbn_key"])`; `B` has no graph, no registry entry |
| TC-11 | `A` isbn "1"; replace `A` keeping "1", then with "2" | both stored |
| TC-12 | `A` "1", `B` "2"; replace `B` with "1" | `KeyConflict(iris=[B])`; `A`, `B` keep their versions and triples |
| TC-13 | `A` "1"; remove `A`; add `B` "1" (two commits) | stored |
| TC-14 | `A` "1"; one unit of work removes `A` and adds `B` "1" | stored |
| TC-15 | `A` "1", `B` "2"; one unit of work swaps the two ISBNs | stored |
| TC-16 | one unit of work adds `C` "3" and `D` "3" | `KeyConflict(iris=[C, D])`; the fake store received no update |
| TC-17 | add two books without ISBN | both stored |
| TC-18 | `A` read at v1, replaced elsewhere; replace `A` at v1 with `B`'s ISBN | exactly `Conflict` (`type(e) is Conflict`), `iris=[A]` |
| TC-19 | loaded graph of `A` holds `<x> bibo:isbn "9"`, `<x> a bibo:Book`; add `B` "9" | stored |
| TC-20 | `A` "1" in tenant `T`; add a book "1" in `U` (same fake store, `U`'s registry) | stored |
| TC-21 | keys built by hand: one key on class `lib:Book2` over `dcterms:title`; a root typed `lib:Book2` with title "X" stored; add a root typed `lib:Magazine` (a subclass, own key not given) with title "X" | stored (another type, PD-4) |
| TC-22 | raw `session.add_graph(B, triples with two bibo:isbn values)` | `InvalidBody`; nothing sent |
| TC-23 | session opened with `keys=()`; add `A` "1", `B` "1" | both stored (PD-10) |
| TC-24 | the guard and diagnosis texts for an ISBN `'"} ; DROP ALL ; #'` | the value appears only as an escaped literal; the update parses |
| TC-25 | refused request whose holder is removed before the diagnosis (fake store hook) | `Conflict(iris=())`, not `KeyConflict` |
| TC-26 | `A` stored with isbn `"1"` (plain); raw `add_graph(B)` with `"1"^^xsd:string` | `KeyConflict(iris=[B])` (PD-5 normalisation) |
| TC-27 | `max_roots=2`; batch commit of `C` "5", `D` "6", `E` "5" | `KeyConflict(iris=[E], keys=["isbn_key"])` from the second batch; message says 1 batch committed |

- [x] 1.3 The problem. Test first, in `tests/unit/entrypoints/test_problems.py`,
  `tests/unit/entrypoints/test_router.py`, `tests/unit/entrypoints/test_openapi.py`. Then the
  `ERROR_KINDS` row and `KEY_CONFLICT` in `entrypoints/problems.py` (PD-8). Gates:
  `make test-changed`, `make check-quality`, `make clean-code`.

| ID | Input | Expected |
|---|---|---|
| TC-30 | `kind_of(KeyConflict(...))`; `kind_of(Conflict(...))` | `KEY_CONFLICT` (409, "Key conflict"); `CONFLICT` unchanged |
| TC-31 | toy service: POST a book with isbn "1" twice | second: 409, type `…/problems/key-conflict`, no `detail`; one book listed |
| TC-32 | PUT `B` with `A`'s isbn and a stale `If-Match` | 409, type `…/problems/conflict` |
| TC-33 | OpenAPI document | lists `key-conflict` among the problem types |

- [ ] 1.4 On Fuseki. New `tests/integration/store/test_unique_keys.py`; router case in
  `tests/integration/api/test_router.py`. Gate:
  `make test-containers TEST_PATH="tests/integration/store/test_unique_keys.py tests/integration/api/test_router.py"`.

| ID | Input | Expected |
|---|---|---|
| IT-01 | 20 rounds: two sessions `asyncio.gather` adds of two books with one fresh ISBN | each round: exactly one succeeds, the other raises `KeyConflict`; one book per ISBN |
| IT-02 | TC-12 and TC-14 on Fuseki | as TC-12, TC-14 |
| IT-03 | router: two tenants each POST a book with isbn "1"; then a second POST in the first | 201, 201, then 409 `key-conflict` |
| IT-04 | TC-18 on Fuseki | as TC-18 |

- [ ] 1.5 Stage close: `make check-all`, `make test-containers`; PR 1 into `develop`
  (`Refs: cross-aggregate-unique-keys PD-1..PD-10, PD-12, PD-13`); merge on green CI.

## 2. Report, cost and docs (stage 2, PR 2)

- [ ] 2.1 The duplicates report. Test first, in `tests/unit/services/test_session_unique_keys.py`.
  Then `duplicates_query` (`services/unique_keys.py`) and `Session.key_duplicates()` (PD-11);
  export `KeyDuplicate`. Gates: `make test-changed`, `make check-quality`, `make clean-code`.

| ID | Input | Expected |
|---|---|---|
| TC-40 | session without keys writes `A`, `B` with isbn "1", `C` "2"; keyed session `key_duplicates()` | `[KeyDuplicate(key_name="isbn_key", root_class=bibo:Book, key_values=["1"], key_roots=[A, B])]` (PD-16); store unchanged |
| TC-41 | no duplicates; no keys | `[]` |
| TC-42 | TC-40, then replace `A` keeping "1" with the keyed session | `KeyConflict`; after changing `A` to "4", `key_duplicates()` is `[]` |

- [ ] 2.2 Cost and report on Fuseki, in `tests/integration/store/test_unique_keys.py`. Gate:
  `make test-containers TEST_PATH=tests/integration/store/test_unique_keys.py`.

| ID | Input | Expected |
|---|---|---|
| IT-05 | TC-40 on Fuseki | as TC-40 |
| IT-06 | 1,000 stored books with distinct ISBNs; 20 keyed adds, 20 adds without ISBN | mean keyed add < 0.5 s; both means printed and recorded in design.md, RISK-1 (RISK-1) |

- [ ] 2.3 Docs. `docs/modules/ROOT/pages/architecture/index.adoc`: the building block row
  "Unique keys across aggregates" from deferred to delivered, and the `Session` row (key guards in
  the guard operation). `architecture/generation.adoc`: scoped keys beside the `unique_keys`
  rows and the hard-check list. `architecture/api.adoc`: the `key-conflict` problem.
  `howto/adopt.adoc`: in `#model`, declaring a key; in `#session`, `KeyConflict`, `open_session`
  without `keys` (RISK-3), canonical numbers (RISK-5); a new subsection "Add a key to live data"
  (declare, run `key_duplicates()` on every tenant, fix, deploy; RISK-6). `questions.adoc`: drop
  the item from "What could strengthen it in the future"; add the question "Can two aggregates
  share a key value?". Gates: `make check-docs`, `make check-diagrams`.

## 3. Close

- [ ] 3.1 `make check-all`, `make test-containers`; `openspec validate cross-aggregate-unique-keys
  --strict`; PR 2 into `develop` (`Refs: cross-aggregate-unique-keys PD-11`); merge on green CI;
  archive the change.
