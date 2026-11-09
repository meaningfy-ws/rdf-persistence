<!-- PLAN, design half. Derives from: EPIC `mwb2-adoption-fixes` (proposal.md, DEC-1 to DEC-4);
     answers in inputs/seed.md. Decisions are cited, not restated. -->

# Design: mwb2-adoption-fixes

Four independent fixes, one stage. Each PD names its files, the algorithm, a worked example, the
tests (with ids `T-n`) and its traps. Code facts were read at `develop` `f38a11a` (2026-11-09) and
checked by an independent review the same day (see "Clarity gate" in tasks.md).

## PD-1 `py.typed` in the wheel (#42, DEC-4)

- Add an empty `rdf_persistence/py.typed`. `uv_build` (`pyproject.toml` `[tool.uv.build-backend]`,
  `module-root = ""`) ships the files of the module folder; T-1 proves it for this file.
- **T-1** `tests/unit/test_packaging.py` (new, `unit` lane — `pytest.ini` has no `slow` marker):
  `uv build --wheel --no-build-isolation --out-dir <tmp_path>` (no network). `uv_build` is not in
  the environment today: first `uv add --dev "uv_build>=0.10,<0.11"` (the range of
  `[build-system] requires`; check it there and match it),
  open the wheel with `zipfile`, assert `rdf_persistence/py.typed` is a member.
- Example: `unzip -l dist/rdf_persistence-*.whl | grep py.typed` → `rdf_persistence/py.typed`.

## PD-2 Deleting a tenant requires `administer` (#43, DEC-1)

- `rdf_persistence/entrypoints/router.py`, `add_tenant_routes` (~l.259): the tenant `delete` route
  takes `may_administer`; the `may_delete` dependency there is removed (no other user). The
  aggregate routes (`gate.aggregate(rp_path, Action.DELETE)`, ~l.321) are untouched.
- No OpenAPI change: `TenantOpenApi.delete()` (`entrypoints/openapi.py` ~l.285) names no action.
- Matrix (actions the caller holds on the tenant):

  | Caller | `DELETE /libraries/{t}` | `DELETE /libraries/{t}/books/{id}` |
  |---|---|---|
  | `[read, modify, delete, administer]` (librarian) | 204 | 204 |
  | `[read, modify, delete]` (role made in the test) | **403**; tenant, database, bucket remain | 204 |
  | `[read]` (reader) | 403 | 403 |
  | librarian + Prohibition of `administer` on the tenant | 403 | 204 |
  | librarian + Prohibition of `delete` on the tenant | **204 (was 403)** | 403 |

- **T-2** (new, `tests/unit/entrypoints/test_router.py` with `scene.py`): row 2, both cells; the
  fake store and file store still hold the dataset and bucket after the 403.
- **T-3** (new): row 4, the `administer` Prohibition blocks the tenant delete.
- **T-4** (change, `test_router.py:138–156` `test_a_grant_set_replaces_the_grants`): it gives ada
  (librarian) a Prohibition of `delete` and expects tenant `DELETE` → 403. Change the Prohibition to
  `Action.ADMINISTER`, keep the 403 and its message ("the new prohibition forbids deleting the
  tenant").
- **T-5** (new): row 5 — ada (librarian) with a Prohibition of `delete` on the tenant: tenant
  `DELETE` → 204, a book `DELETE` → 403.
- The toy fixture `tests/fixtures/library/library_roles.yaml` does not change (the librarian
  already holds `administer`).
- Docs: `architecture/access-control.adoc` l.103 — `rp:administer` "(change a tenant's grants, or
  delete the tenant)"; `howto/adopt.adoc` ~l.688 (tenant delete) names `administer`; the roles
  example ~l.738–745 gains a `member` line `[read, modify, delete]` with one sentence on what it
  cannot do.
- The commit carries `BREAKING CHANGE:` (DEC-1): a role with `delete` and no `administer` can no
  longer delete a tenant; a `delete` Prohibition no longer stops a tenant delete.

## PD-3 A tenant has one label (#44, DEC-2)

**Rename** (`rdf_persistence/services/tenancy.py`, `rename`):

1. `record, version = await self.get(tenant)`; if `version != if_version` raise `Conflict` before
   anything is written.
2. In the tenant's database (`self._iris.resource_name(tenant)`): read the root with
   `session.get_graph(tenant)` and `self._mapper.from_graph(self._root_class, tenant, …)`, set
   `label`, store it with `_replace_root(name, tenant, principal, root, root_version)` — the
   root's own version, never `if_version` (that is the record's).
3. Set the record's `label` and `description`, `_replaced(..., if_version)` as today; answer its
   version.

**Root replacement** (`rdf_persistence/services/aggregates.py`, `replace`): when `iri == tenant`
(the tenant routes pass `access.tenant` as the IRI, `router.py` ~l.276; aggregate routes always
pass a minted aggregate IRI), call a new `Tenancy` method (e.g. `refuse_label_change(tenant,
triples)`) **before** the session opens. It reads the record and compares the body's value of the
predicate the mapper writes for the root's `label` slot (`Described.label`, required) with
`record.label`; a difference raises `InvalidBody("the label of a tenant is changed through its
label route")`.

Example (toy library; `v1` is the record's ETag):

```text
POST /libraries {"label": "A"}                           → 201, t
PUT  /libraries/t/label {"label": "B"}  If-Match: v1     → 200, ETag v2
GET  /libraries/t                                        → {"label": "B", ...}
PUT  /libraries/t {"label": "C", ...}   If-Match: <root> → 400 invalid-body; root still "B"
PUT  /libraries/t {"label": "B", ...}   If-Match: <root> → 200
PUT  /libraries/t/label {"label": "D"}  If-Match: v1     → 409; record and root still "B"
```

Tests (`tests/unit/services/test_tenancy.py` unless stated):

- **T-6** rename to "B" → record and root read "B".
- **T-7** stale `If-Match` → `Conflict`, and the fake store saw no write to either dataset.
- **T-8** root written, record write fails: `FakeStore.on("update", error, times=1, after=1)`
  (`testkit/fakes.py:46` counts calls per operation, not per dataset; the record write is the
  rename's second `update`) → record "A", root "B"; the same rename retried → both "B".
- **T-9** the record moved between step 1 and 3: inject `Conflict` on that same second `update`
  → 409; record "A", root "B"; re-read the ETag, rename again → both "B".
- **T-10** (`tests/unit/entrypoints/test_router.py`) the example above through the routes,
  including a root `PUT` whose label equals the record's → 200.
- **T-11** a root whose stored label drifted before this change (written directly to the fake
  store): `GET` then `PUT` of the same body → 400; a rename repairs it.

## PD-4 The guard API is public (#45, DEC-3)

`rdf_persistence/testkit/__init__.py`:

- Eager: `assert_models_generated` (`guards`), `model_shape_diff` (`model_shape`) and
  `class_shapes`, `read_snapshot`, `write_snapshot`, `snapshot_diff` (`shape_snapshot`): none of
  these modules loads `pyshacl` or `hypothesis` (checked 2026-11-09); what they do load
  (`linkml_runtime`, `rdflib`, the schema structure) `testkit.fakes` already loads.
- Lazy through `_LAZY_MODULES`, because their modules load `pyshacl` (`conformance`, and through
  it `roundtrip` and `strategies`) or `hypothesis` (`strategies`): `Conformance`,
  `conformance_problems`, `round_trip`, `aggregate`.
- `conformance_problems` is `testkit.conformance.run` under a name that says what it returns.
  `_LAZY_MODULES` therefore maps a public name to `(module, attribute)`; every other entry keeps
  its own name. `conformance.run` stays (the toolkit's own tests use it).
- `TYPE_CHECKING` imports and `__all__` list every new name.

Step 6 of `howto/adopt.adoc` becomes:

```python
from rdf_persistence.testkit import (
    Conformance, aggregate, assert_models_generated, conformance_problems, round_trip,
)
...
    assert conformance_problems(SCHEMA, ROOT / "tests" / "conformance" / "cases.yaml") == []
...
    conformed = Conformance.of(SCHEMA)
```

and the prose at ~l.375 and ~l.397 says `conformance_problems` where it says `conformance.run`.
Step 6 gains a fifth check, *the model's shape changes only on purpose*:

```python
import os
from rdf_persistence.testkit import (
    Conformance, class_shapes, model_shape_diff, read_snapshot, snapshot_diff, write_snapshot,
)

SNAPSHOT = ROOT / "tests" / "model-shape.yaml"

def test_the_model_shape_is_the_reviewed_one():
    current = class_shapes([SCHEMA])
    if os.environ.get("REFRESH_SNAPSHOT"):          # set it once after a deliberate change
        write_snapshot(SNAPSHOT, current)
    assert snapshot_diff(read_snapshot(SNAPSHOT), current) == []

def test_the_generated_classes_follow_the_schema():
    models = {m.__name__: m for m in Conformance.of(SCHEMA).models.values()}
    # the schema's own classes; those it imports from the toolkit are the toolkit's to check
    shapes = [s for s in class_shapes([SCHEMA]) if s.class_name in models]
    assert model_shape_diff(shapes, models.values()) == []
```

The consumer refreshes with `REFRESH_SNAPSHOT=1 uv run pytest tests/test_model.py` (the guide
names no make target of ours). **T-15** proves the snippet is true: it runs the five checks of
step 6, as written in the guide, against the toy library (`tests/fixtures/library`). The filter in
the last test is needed: without it the toy gives 13 "class without a generated model" lines for
the metamodel classes it imports (`Described`, `Grant`, …); with it the diff is `[]` (probed
2026-11-09).

The freshness plugin line (`pytest_plugins = ["rdf_persistence.testkit.freshness"]`) stays: a
string, not an import; `assert_public_imports` reads only import statements.

Other docs naming the old paths: `architecture/generation.adoc` l.496, 498, 514 and
`questions.adoc` l.103 use the public names.

Tests:

- **T-12** (`tests/unit/testkit/`, new): the step 6 imports, as the guide shows them, written to
  `tmp_path`, pass `assert_public_imports`; a file importing `rdf_persistence.testkit.strategies`
  is refused, naming file, line and module (#45 acceptance).
- **T-13** (`tests/unit/test_testkit_lazy_import.py`, extend): every name of `__all__` resolves;
  `import rdf_persistence.testkit` loads neither `hypothesis` nor `pyshacl`.
- **T-14** `make check-docs` stays green (its checklist check reads `__all__`).
- **T-15** as above.

## Anti-patterns (do / don't / why)

| Don't | Do | Why |
|---|---|---|
| Change `AccessRules` or Prohibition scoping for #43 | Change only the action the tenant route asks for | The no-go; the smallest change (DEC-1) |
| Add a test-only role to `library_roles.yaml` | Build the role inside the test | The fixture is the toy's truth, shared by many tests |
| Compare the root's version with `if_version` | Use the root's own version for the root write | `if_version` is the record's ETag |
| Write the root before checking the record's version | Check first (step 1) | A stale rename must change nothing |
| Refuse a root `PUT` inside the open session | Refuse before the session opens | Nothing is read or locked for a refused body |
| Derive or cache the label at read time | Store it in both places | DEC-2 rejected it |
| Widen `assert_public_imports` | Export the names | DEC-3 rejected it |
| Eagerly import `conformance`/`strategies` in `__init__` | Load them on first use | Keeps `pyshacl` and `hypothesis` out of every test run |
| Show a guide snippet no test runs | T-15 runs it | The guide is a contract with consumers |

## Error matrix

| Case | Answer | What stays |
|---|---|---|
| Tenant `DELETE` without `administer` | 403 | tenant, database, bucket |
| Tenant `DELETE` with `administer`, `delete` prohibited | 204 | — |
| Aggregate `DELETE` with `delete`, no `administer` | 204 | the tenant |
| Tenant `DELETE` or rename without `If-Match` | 428, as today | everything |
| Tenant `DELETE` or rename of an unknown tenant | 404, as today | — |
| Rename with a stale `If-Match` | 409 | root and record unchanged |
| Rename: root write conflicts (concurrent root `PUT`) | 409 | record unchanged; retry converges |
| Rename: record moved after step 1 | 409 | root new, record old; re-read ETag, retry converges |
| Rename: record write fails (store error) | 5xx as today | root new, record old; retry converges |
| Root `PUT` with a different label | 400 `invalid-body` | root unchanged |
| Root `PUT` with the record's label | 200 | — |
| Consumer test with step 6 imports | `assert_public_imports` passes | — |
| Consumer test importing `testkit.strategies` | refused | — |
