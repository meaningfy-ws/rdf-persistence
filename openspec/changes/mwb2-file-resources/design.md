<!-- Parent: EPIC mwb2-file-resources (proposal.md, DEC-1 to DEC-5). Seeds and answers: inputs/seed.md. -->

# Design: mwb2-file-resources

Decisions are the EPIC's DEC-n; this file says how. `T-n` are the tests each PD is proven by; they
are written first. File and line references are to `develop` at 85d3ab3.

**EPIC update (2026-11-09, from MWB2's impact note; proposal.md "Why" and "Solution outline").**
#59 is MWB2's critical path, and #54 is moot for MWB2, which drops `openapi-typescript` in its own
change `rp-adoption-refresh`. What it changes here: stage 1's close comments on and closes #59,
#55 and #54 as soon as its PR merges (MWB2 refreshes its lock then, not after stage 2); PD-4 and
T-12 stay as they are, because the OpenAPI document must stay valid for any consumer that
generates a client from it; S-90's removal is no longer an outcome of this change. Stage 2 is
unchanged; it unblocks v1-06 tasks 2.3, 2.4 and 3.7 (#56) and 1.7 (#60).

# Stage 1

## PD-1 A root's description is optional (#59, DEC-1)

**Cause.** `services/schema_structure.py:303` `apply_defaults` gives every aggregate root a
`slot_usage` `description: {required: true}`. It runs on the generation view, which the Python
(`generation/extensions/pydantic_split.py:171`), TypeScript (`generation/extensions/typescript.py`),
SHACL (`generation/extensions/shacl.py:130`) and shape-snapshot (`testkit/shape_snapshot.py:26`)
generators read; the JSON Schema / OpenAPI components
(`generation/components.py`) do not apply it. So `Book`, `Scan` and `LibraryAccess` in
`tests/fixtures/library/generated/` have `description: str = Field(default=...)` in Python and
`required: [id, label]` in `openapi-components.json`.

**Change.** Delete the root loop (l.313–314) and its docstring half; keep the `rp_unlabelled` half.
Update the `class_shapes` docstring (`shape_snapshot.py:20–21`: "an aggregate root's
description"). Regenerate the toolkit's and the toy's artefacts (`make generate`; the SHACL
shapes change too: no `minCount` on a root's `dcterms:description`) and the shape snapshot fixture
(`tests/fixtures/model-shape.yaml`, with `RP_REFRESH_SNAPSHOT=1`, `Makefile:90`). Existing tests that
assert the root description is required change to assert it is optional.

Example, after:
```python
Book(id="https://example.org/b/1", label="A")      # validates
Scan(id=..., label="s", file_name="s.pdf", ...)     # validates without a description
```

- **T-1** Toy roots `Book`, `Scan`, `LibraryAccess` build with only `id`, `label` (and their own
  required slots); `description` defaults to `None`.
- **T-2** A temp schema with an abstract `Item` (`AggregateRoot`, `Described`) and a served
  `Book is_a Item`: the generated `Book` builds without a description (the #59 reproduction).
- **T-3** `apply_defaults` still makes an `rp_unlabelled` class's label optional, and no longer
  touches a root's `description` `slot_usage`.

## PD-2 A guard for required-flag mismatches (#59, DEC-1)

`testkit/model_shape.py` gains `model_schema_diff(components: Mapping[str, Mapping], models:
Iterable[type[BaseModel]]) -> list[str]`, exported from `rdf_persistence.testkit`. `components`
is the `schemas` object of a generated `openapi-components.json`. For each model whose name is a
component: every JSON property name (a field's alias, else its name) that is required in exactly
one of the two gives a line `required differs: <Class>.<slot> (python: yes, json schema: no)`.
Properties absent from the component (internal slots, PD-trimmed) are skipped. The toolkit's own
generated-artefact test calls it on the toy (where `model_shape_diff` is already called), so CI
fails on a regression; `howto/adopt.adoc` step 6 adds it to the consumer's guards. The export
lists asserted in `tests/unit/test_testkit_lazy_import.py:66` and
`tests/unit/testkit/test_stage1_adversarial.py:11` gain the name.

Why a new function and not `model_shape_diff`: that one compares Python with shapes read from the
same generation view the Python came from, so a default applied there agrees with itself.

- **T-4** `model_schema_diff` on the toy's models and components is empty (after PD-1).
- **T-5** A model with a required `description` against a component that does not require it gives
  exactly one line naming the class and `description`; the reverse direction gives one too.

## PD-3 Service-written roots (#55, DEC-2)

**Model.** `model/rp_core.yaml`: `RpAnnotation` gains `rp_writes` ("Class annotation, `service` on
an aggregate root whose generic create, replace and delete are not served; the consumer writes it
through a session. A root that mixes in `StoredFile` is service-written without it.") and a new
enum `WritesKind` with the single value `service`. Regenerate. `generation/checks/hard.py:50`
lists `RpAnnotation.RP_WRITES: tuple(k.value for k in WritesKind)`, so any other value fails
generation as an unknown `database` value does today. There is no `generic` value: a `StoredFile`
root cannot opt back in (EPIC DEC-2).

**Rule.** `services/schema_structure.py` gains `is_service_written(view, cls) -> bool`: the
annotation is `service`, or `StoredFile` is among `view.class_ancestors(cls.name)`.

**Routes.** `entrypoints/router.py` `add_aggregate_routes` (l.330) mounts the listing and the read
always, and `create`, `replace`, `remove` only when `not is_service_written(kit.view, cls)`. The
OpenAPI document follows, because each route adds its own docs (`docs.create().add_to(...)`). A
`POST`/`PUT`/`DELETE` on a mounted path then answers 405 from the framework (EPIC rabbit-hole: no
handler is added to shape it). The `Allowed-Actions` header is unchanged: it states what the
caller may do, not which routes exist.

**Toy and tests.** `Scan` (a `StoredFile` root) becomes service-written, and it is the toy's only
served root with an internal slot (`file_key`). Every test that writes scans through the generic
routes changes as below; the builder re-greps `/scans` and `SCAN_BODY` first and reports any
test the table misses.

| Test | Change |
|---|---|
| `tests/unit/entrypoints/test_library_app.py:70` | create the scan through `kit.session(...)` + `UnitOfWork` |
| `tests/unit/entrypoints/test_kit_require.py:55` (`scanned`) | same |
| `test_router_hardening.py:37, :45` (a client cannot set `file_key`, JSON and JSON-LD) | delete: T-6 replaces them (the write route no longer exists). The stripping of internal slots keeps service-level unit tests: the builder confirms they exist in `tests/unit/services`, else adds one on a temp-schema root with an internal slot |
| `test_router_hardening.py:60` (a stored `file_key` is in no representation or listing) | keep; store the scan with its key through a session |
| `test_router_hardening.py:84` (a replace keeps internal values) | delete; same reason and coverage as l.37 |
| `test_router_hardening.py:107` (a node smuggled through a reference is a 422) | keep, on a served root with a reference slot if the toy has one, else at the `Aggregates` level |
| `tests/integration/api/test_replace.py` (replace keeps `fileKey`, Fuseki) | delete; PD-14b is covered by the service-level test above |
| `tests/e2e/library_app.py`, `tests/e2e/test_library.py:190` | the toy app gains its own `POST` scan route that writes the record through `kit.session` and the bytes through `kit.files` (the pattern of `howto/adopt.adoc` step 10); the e2e test uses it |
| `tests/unit/entrypoints/test_stage4_adversarial.py:351` (documented operations) | must still pass; update its expected list if it enumerates scan writes |

- **T-6** On the served toy, `POST /…/scans`, `PUT` and `DELETE /…/scans/{id}` answer 405 for a
  caller with `modify` and `delete`, as the existing `method-not-allowed` problem with an `Allow`
  header holding `GET` (as `test_router_hardening.py:210` asserts today); the scan stored by a session is unchanged; `GET` of it and the
  listing answer 200.
- **T-7** A temp schema root without `StoredFile`, annotated `rp_writes: service`: its OpenAPI paths
  have `get` only (collection and member).
- **T-8** Through `kit.session(...)`, a test adds, replaces and removes a `Scan`; each commit gets a
  new version.
- **T-9** `rp_writes: generic` fails generation with the hard check's message.

## PD-4 Listing filters carry their schema inline (#54, DEC-3)

**Where.** Route docs are built in `add_aggregate_routes`, before the component schemas are read,
so `_filter` (`entrypoints/openapi.py:355`) keeps its `$ref` and `install_openapi` (l.436) resolves
them: in `openapi()`, after merging the components, a pure function
`_inline_property_refs(document, raw)` replaces every parameter schema whose `$ref` is
`#/components/schemas/<C>/properties/<p>[/items]` with a deep copy of that target from `raw`,
without its `description` (the parameter has its own). This covers the paging parameters
(`ListRequest/properties/limit`) too, so no parameter points into a property.

Example, after: `authors` → `{"type": "string"}`; `genre` → `{"$ref": "#/components/schemas/Genre"}`;
`limit` → `{"type": "integer", "minimum": 1, "maximum": 200, ...}` as in `ListRequest`.

**Toolchain check.** A script `tests/dump_openapi.py` builds the toy service as the unit tests do
(no containers) and writes its OpenAPI document to the path it is given. A make target
`typecheck-openapi-ts` runs it as `uv run python -m tests.dump_openapi temp/toy-openapi.json`, then
`npx -y openapi-typescript@7.13.0 temp/toy-openapi.json -o temp/toy-openapi.ts` and
`npx -y -p typescript@5.9.3 tsc --noEmit --strict temp/toy-openapi.ts`. `check-types` depends on it
(the CI `types` job already sets up Node 20).

- **T-10** In the toy's document, the `authors` filter's schema is `{"type": "string"}` and
  `genre`'s is the `Genre` reference.
- **T-11** No parameter of any operation in the document has a `$ref` containing `/properties/`.
- **T-12** `make typecheck-openapi-ts` passes (run by the lead; before PD-4 it fails on the toy's
  `authors` filter).

# Stage 2

## PD-5 Reading a loaded graph back (#56, DEC-4)

`services/session.py` `Session.loaded_graph(iri: str, graph_iri: str) -> Graph`:
1. `self._graph(iri)` (refuses an IRI the policy does not mint, as every read does);
2. the aggregate's loaded graphs from the registry with the existing `READ_LOADED` query;
3. `graph_iri` not among them → `NotFound(f"{graph_iri} is not a graph loaded for {iri}")`;
4. `READ_GRAPH` on it; the answer's graph (an empty `Graph()` if the store answers none).

**Access (correction of the EPIC's spec scenario).** A session does not check permissions: the
consumer's route calls `kit.require_aggregate(authorization, t, rp_path, id, Action.READ)` before
opening the session, as for `get_graph`. The delta spec's scenario "a caller without read … its
session … is refused" is replaced by a requirement sentence and scenario saying the read is gated
like any read of the aggregate, through `require_aggregate` (PD-7 below records the divergence).

- **T-13** An aggregate committed with a graph loaded from Turtle: `loaded_graph` returns a graph
  isomorphic to the parsed Turtle.
- **T-14** Two aggregates with a loaded graph each: the first's IRI with the second's graph IRI
  raises `NotFound`; an unknown graph IRI does too.
- **T-15** `kit.require_aggregate(..., Action.READ)` for a principal without `read` raises
  `Forbidden` (the principal sees the tenant but may not read the aggregate; existing behaviour,
  asserted once beside the new read). Done as: already covered by
  `test_a_prohibition_on_the_aggregate_applies` (`tests/unit/entrypoints/test_kit_require.py`); no
  duplicate added.

## PD-6 Finding aggregates by slot value (#60, DEC-5)

**Wiring.** `Session.__init__` and `open_session` (public, `rdf_persistence/__init__.py:242`) take
a keyword `listings: Listings | None = None`. `Tenancy.__init__` takes the same keyword and passes
it in `_session`. `ServiceKit` builds `self.listings` before `Tenancy` (move `kit.py:61` above
l.81) and passes it, so the kit and its sessions share one instance. `fake_session` takes it too
(default `None`), so a unit test can opt in.

`Session.find(cls: type[BaseModel], **equals: object) -> list[str]`:
1. no `listings` → `RuntimeError("find needs a session opened with listings, e.g. by the service
   kit")`;
2. the class definition by `cls.__name__` from the listings' view (`Listings` gains a read-only
   `view` property); it must be in `aggregate_roots(view, [cls_def])`
   (`services/schema_structure.py:188`) and carry `rp_path`, else `ValueError(f"{name} is not an
   aggregate root with a path")`;
3. filters: one `Filter(slot=name, value=_text(v))` per value (a list or tuple value gives one per
   item: all must be present); `_text` is `v.value` for an enum, `str(v)` otherwise;
4. `listings.plan(cls_def, ListRequest(filters=..., limit=200, offset=k))` with no `hidden`
   graphs — an unknown slot raises the existing `BadQuery("Scan has no slot 'colour' to filter or
   sort on")`;
5. pages through `self.page(plan)` with `items_of`/`total_of` until `total` IRIs are collected;
   returns them as `str`, in IRI order.

Tenant scoping is the session's (its registry); class scoping is the plan's `target`.

**Prohibitions.** `find` ignores Prohibitions: it returns every matching aggregate of the tenant,
including ones the session's principal may not read. That is what a uniqueness check needs (a
hidden duplicate is still a duplicate), and a session never applies access rules (PD-7). A
consumer that shows the result to a caller checks each IRI with `require_aggregate`, or uses the
listing route. Task 5.2's docs say so.

- **T-16** Two scans `file_name` "a" and "b": `find(Scan, file_name="a")` is exactly the first IRI.
- **T-17** A scan "a" in another tenant and a `Book` with `isbn` "a": not returned.
- **T-18** `find(Scan, colour="red")` raises `BadQuery` naming `colour` and `Scan`.
- **T-19** A multivalued filter: `find(Book, authors=["X", "Y"])` returns only books with both.
- **T-20** 201 matching aggregates: all 201 IRIs come back (paging).
- **T-21** `fake_session` without listings + `find` raises the clear `RuntimeError`. With
  `listings=Listings(view)`, T-16 to T-20 run as unit tests if `FakeStore` answers the listing
  query; otherwise they run in `tests/integration/store` against Fuseki. The builder checks first
  and says which.

## PD-7 Divergence from the EPIC's delta spec (#56)

The EPIC's `rp-aggregate-store` scenario "a caller without read … its session … is refused" does
not match the architecture: sessions never check permissions; the gate does
(`ServiceKit.require_aggregate`). Recorded here and fixed in the delta spec when the PLAN was derived: the
requirement says the read is gated like `get_graph`, the scenario says a consumer route that checks
`read` with `require_aggregate` refuses the caller before the session is opened. The bet (DEC-4)
holds; this is a PLAN-level correction.

**How PD-3's open branches went (task 2.2, 2026-11-09).** The toy has no served root with a
reference slot other than `Scan.scan_of`, so the HTTP-level 422 test (`test_router_hardening.py`
l.107) was deleted; `tests/unit/services/test_documents_strict.py:155/161` already cover a smuggled
node at the `Documents` level. The service-level stripping of internal slots is covered by
`test_documents_strict.py` and `test_documents.py:377/390`; `Aggregates.replace` keeping them has
`tests/unit/services/test_replace_internal_values.py` (added after stage 1, R1-1). One test the table
missed, `tests/unit/entrypoints/test_openapi.py` (it listed the scan writes), now expects reads
only for scans. **Known limit:** the generator imports `WritesKind` from the generated
`rp_core.py`, so adding a value to a toolkit enum the generator itself reads needs a two-step
regeneration (as the builder did). Ordinary consumer regeneration is unaffected.

## PD-8 The JSON Schema reads the generation view too (#59, DEC-1; found in task 1.2)

T-4's first run found a second mismatch: `Chapter.label (python: no, json schema: yes)`.
`generation/components.py` builds `openapi-components.json` with
`JsonSchemaGenerator(str(schema_path))`, which never sees `apply_defaults`; so an `rp_unlabelled`
class's label is optional in Python, TypeScript and SHACL but required in the JSON Schema and
OpenAPI. Same defect class as #59. Decision (lead, 2026-11-09; the developer may overrule): the
components generator reads the schema of `generation_view(schema_path)`, so every artefact sees
the same defaults; T-4 passes as written. Rejected: exempting `rp_unlabelled` in the guard (hides
the bug); dropping `rp_unlabelled` from the toy's `Chapter` (hides it in the fixture only).
Proof: T-4, plus **T-4b** the toy's `Chapter` component does not list `label` as required.

## Anti-patterns (do / don't / why)

| Do | Don't | Why |
|---|---|---|
| Delete the root half of `apply_defaults` | Add `required: false` on the toy's roots | The defect is the default; fixtures would hide it |
| Compare Python with the generated JSON Schema (PD-2) | Extend `model_shape_diff` | It reads the same view as the Python and agrees with itself |
| Skip mounting the writes | Mount them and answer 405 by hand | Less code; the OpenAPI document follows for free |
| Resolve pointers once in `install_openapi` | Thread the components into every route doc | One place, pure, testable |
| Reuse `READ_LOADED`, `READ_GRAPH`, `Listings.plan`, `items_of` | Write new SPARQL for `loaded_graph`/`find` | The queries exist and are injection-safe |
| Check access with `require_aggregate` in the consumer's route | Add a permission check inside `Session` | Sessions never check access (PD-7) |

## Error matrix

| Situation | Answer |
|---|---|
| Generic `POST`/`PUT`/`DELETE` on a service-written root | 405 (framework), nothing written |
| `rp_writes` with a value other than `service` | Generation fails (hard check) |
| `loaded_graph` with an IRI the policy does not mint | `InvalidIri` |
| `loaded_graph` with a graph not loaded for that aggregate | `NotFound` |
| `loaded_graph` on a dropped tenant database | `DatabaseGone` (as every read) |
| `find` with an unknown slot | `BadQuery` naming the slot and the class |
| `find` with a class that is not an aggregate root with `rp_path` | `ValueError` naming the class |
| `loaded_graph` on an aggregate that does not exist | `NotFound` (its registry lists no loaded graph) |
| `find` on a session opened without listings | `RuntimeError` |
| `find` with a value the slot cannot take (e.g. not a date) | `BadQuery` (existing `typed_value`) |

# Stage 1 review decisions (2026-11-09)

Four read-only passes (L1, L2, L3, L4+L5); no blockers. Accepted findings are fixed in one
follow-up commit; each is an R1-n below.

**Accepted**
- **R1-1 (L2)** `Aggregates.replace` keeping internal values lost its only end-to-end test when
  #55 deleted the scan replace tests. Add a unit test on a temp-schema root with an internal slot
  that is not service-written: store a value, replace, the value stays. (Corrects "none was added"
  in PD-3's branch note.)
- **R1-2 (L2)** The durable requirement "One generic router serves every aggregate type" still says
  every root gets create/replace/delete. The delta spec gains a MODIFIED block scoping it to roots
  that are not service-written (done by the lead).
- **R1-3 (L2)** T-2 asserts the scenario in full: in its temp project, the JSON Schema of `Item` and
  `Thing` requires only `id` and `label`, and `model_schema_diff` is empty.
- **R1-4 (L2)** T-8 uses a root annotated `rp_writes: service` (T-7's `Shed`) and asserts the
  remove too.
- **R1-5 (L1)** The upload pattern consumers copy (adopt.adoc step 10 and `tests/e2e/library_app.py`)
  removes the blob when the commit fails, catches `Exception` (not `BaseException`) and suppresses a
  failing cleanup so the original error surfaces; a pydantic `ValidationError` while building the
  record answers 422. (Done as: the app's problem handlers already map a `ValidationError` to 422, so no
  code was added; the toy `Scan` cannot be made invalid from its route, so that 422 has no test, and
  the record is built before the bytes are stored, so a 422 leaves nothing to clean.)
- **R1-6 (L1)** That upload reads the body with `limited_body(request, kit.max_body_bytes)`;
  `limited_body` becomes a public name of `rdf_persistence` (it was internal to the router) so a
  consumer's own route gets the same bound as the generic ones.
- **R1-7 (L4)** One constant for the `/properties/` pointer segment, beside `COMPONENT_REFERENCES`
  in `services/artifacts.py`, used where `_PAGING` builds pointers and where they are inlined.
- **R1-8 (L4)** `description` is a constant again (`DESCRIPTION`), used in `_target_in` and l.181.
- **R1-9 (L5)** `model_schema_diff` matches its sibling: the message shape of `_flag_lines`, a
  per-model `_required_lines` helper, no `_yes`.
- **R1-10 (L5)** `STORED_FILE = StoredFile.__name__`; `is_service_written` names its two tests.
- **R1-11 (L5)** `_target_in`/`_inline_property_refs` use the `JsonSchema` alias.
- **R1-12 (L4)** One scans constant for the tests (`tests/toy.py`), used by `toy_service.py` and
  `e2e/library_app.py`.

**Rejected**
- L1 nit "check the upload's media type": which types a file root accepts is the consumer's rule;
  the toolkit has none to show. The example keeps storing what the client declares.
- L2 nit "T-1 builds Scan and LibraryAccess without a description": T-4 runs `model_schema_diff`
  over every toy class, which catches the same defect.
- L5 "a `component_pointer` helper shared with `services/components.py`", "import `JsonSchema` in
  `generation/components.py`" and L3 "read `WritesKind` values through a SchemaView in the hard
  check": forward-looking refactors of older code; out of this EPIC's appetite.
- L3 "move `tests/dump_openapi.py` under `tests/tools/`": only one such helper exists.
