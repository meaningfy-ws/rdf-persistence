<!-- PLAN, design half. Derives from: EPIC `mwb2-adoption-fixes` (proposal.md, DEC-1 to DEC-4);
     answers in inputs/seed.md. Decisions are cited, not restated. -->

# Design: mwb2-adoption-fixes

Ten issues in four stages (proposal.md, "Solution outline"): **Stage 1** PD-1 to PD-6, **Stage 2**
PD-7, **Stage 3** PD-8 and PD-9, **Stage 4** PD-10. Each PD names its files, the algorithm, a
worked example, the tests (with ids `T-n`) and its traps. Code facts were read at `develop` `f38a11a` (2026-11-09) and
checked by an independent review the same day (see "Clarity gate" in tasks.md).

# Stage 1

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
PUT  /libraries/t {"label": "C", ...}   If-Match: <root> → 422 invalid-body; root still "B"
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
  store): `GET` then `PUT` of the same body → 422; a rename repairs it.

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

## PD-5 `install_service` takes an `id_source` (#46, DEC-7)

- `rdf_persistence/entrypoints/service.py` `install_service(..., id_source: IdSource | None = None)`
  passes it to `ServiceKit`, which builds `Iris(settings, *iri_types(view), id_source=...)`
  (`entrypoints/kit.py:62`) only when it is given; `None` keeps `Iris`'s default `draw_id`
  (`domain/iris.py` ~l.282, `secrets`). `Tenancy` and `Aggregates` already take `iris=self.iris`,
  so both draw through it (`kit.py:84-86`; `mint_tenant` draws through `id_source`, `iris.py:478`;
  the start-up probe uses `draw_id` directly, l.470, so it does not consume a test's draws).
  `IdSource` is the alias at `iris.py:278`; export it from `rdf_persistence` beside `Iris` and
  `IdSpec` (it is not exported today).
- Docstring: "for tests that need to force a clash; leave it out in a running service".
- **T-16** (`tests/unit/entrypoints/test_service_kit.py`): `draws = iter([existing, existing,
  fresh])` — the second tenant create is answered with `fresh`, and the first tenant is unchanged.
- **T-17**: without `id_source`, two creates draw different ids of the policy's length (the
  default path is still `draw_id`).

## PD-6 The root read carries the record's version (#50, DEC-5)

- `add_tenant_routes` `read_root` (`router.py` ~l.268): after `root.read(...)`, read
  `_, version = await kit.tenancy.get(access.tenant)` and set `Record-ETag: etag_of(version)`
  (`negotiation.etag_of`, the same form as `ETag`). The constant `RECORD_ETAG = "Record-ETag"`
  lives in `entrypoints/negotiation.py` beside `ETAG`.
- OpenAPI (`TenantOpenApi.read_root()`): document the header: "the access record's version; send
  it as `If-Match` to rename the tenant".
- `howto/adopt.adoc` (tenant routes, ~l.680–700): a reader with `modify` renames with it; a web app
  on another origin must expose `ETag`, `Record-ETag` (and in stage 4 `Allowed-Actions`) in its
  CORS settings.
- Example: `GET /libraries/t` → `ETag: "r7"`, `Record-ETag: "v2"`; `PUT /libraries/t/label
  If-Match: "v2"` with `modify` only → 200; with `If-Match: "v1"` → 409.
- **T-18** (`test_router.py`): a caller with `[read, modify, delete]` reads the root, renames with
  its `Record-ETag` → 200; renames with an older one → 409.
- **T-19**: `Record-ETag` equals the `ETag` of `GET …/grants` for an administrator.

# Stage 2

## PD-7 Consumer validators on tenant writes (#49, DEC-6)

Types (`rdf_persistence/services/tenancy.py`, exported from `rdf_persistence`):

```python
GrantValidator = Callable[[GrantSet, GrantSet, Principal], None]          # old, new, who
RootValidator = Callable[[BaseModel | None, BaseModel, Principal], None]  # old (None on create), new, who
```

A validator refuses by raising `InvalidBody` (422 `invalid-body`, its message is the problem's
`detail`); any exception other than `InvalidBody` or pydantic `ValidationError` (also 422, through the existing handler) is a bug and propagates (500). Validators run in the order given;
the first refusal stops the write.

Wiring: `install_service(..., grant_validators=(), root_validators=())` → `ServiceKit` →
`Tenancy(..., grant_validators=..., root_validators=...)`.

Where they run (each before the conditional write, so nothing is written on refusal):

| Write | Old | New | Runs |
|---|---|---|---|
| `Tenancy.set_grants` | the record's grants and prohibitions, as read | the body | grant validators |
| `Tenancy.create` | `None` | the new root | root validators, before the database is created |
| `Tenancy.rename` | the stored root | the root with the new label | root validators, in step 2: after the root is read, before it is written |
| `Aggregates.replace` when `iri == tenant` | the stored root | the body decoded with the mapper | the label check of PD-3, then root validators |

For the last row, `Tenancy` gets one method, e.g. `vet_root(tenant, triples, principal)`, holding
both the PD-3 label check and the validators; `Aggregates.replace` calls it before the session
opens, as PD-3 says.

Atomicity: the write is the existing conditional update (`session.replace_graph`: the update
carries `if_version`, then an ASK confirms the new token), so two writes at one version cannot both
land. Example (MWB2's rule):

```python
def keep_an_owner(old: GrantSet, new: GrantSet, who: Principal) -> None:
    if not any(g.role == "owner" for g in new.grants or []):
        raise InvalidBody("a project keeps at least one owner")
```

```text
grants {ada: owner, bob: owner} at v1
PUT grants {ada: owner} If-Match v1   ┐ both pass keep_an_owner
PUT grants {bob: owner} If-Match v1   ┘ one → 200 (v2), the other → 409
PUT grants {} If-Match v2             → 422 "a project keeps at least one owner"; record at v2
```

Tests (`tests/unit/services/test_tenancy.py`, `tests/unit/entrypoints/test_router.py`):

- **T-20** a grant validator refuses → 422 through the route, record unchanged (same ETag after).
- **T-21** two concurrent `set_grants` at one version (`asyncio.gather` on the fake store), each
  passing the validator → exactly one `Conflict`; an owner remains.
- **T-22** root validators on create (`old is None`; refusal → no database, no bucket, no record),
  on rename (refusal → root and record unchanged), on root `PUT` (refusal → root unchanged).
- **T-23** a validator raising `RuntimeError` → 500 `internal-error`, nothing written; one raising
  pydantic `ValidationError` → 422 (the existing handler, `problems.py:130`), nothing written.
- **T-24** no validators given → every existing tenancy and router test passes unchanged.
- Docs: `howto/adopt.adoc`, a short section "Enforce your own rules on tenant writes" with the
  example above; `architecture/access-control.adoc` one paragraph.

# Stage 3

## PD-8 `rp_service.ts` for TypeScript targets (#47, DEC-8)

- `rdf_persistence/generation/extensions/typescript.py` `render(schema_path)`: after
  `generator.files()` for the consumer's schema, render the toolkit's
  `PACKAGE_DIR / "model" / "service" / "rp_service.yaml"` with the same `ToolkitTypescriptGenerator`
  and the metamodel import map, keep the files whose names the consumer's run did not write
  (`rp_service.ts`; `rp_core.ts` etc. are already there), and render `index.ts` once over the union
  of module names. When the schema being rendered *is* `rp_service.yaml`, nothing is added.
- The files are ordinary outputs of the step, so the manifest, the freshness check and
  `make check-generated` cover them with no change.
- The toy's `tests/fixtures/library/web/src/domain/generated/` gains `rp_service.ts` on
  `make generate`; `make typecheck-ts` (`tsc --noEmit --strict`, wildcard over that folder) checks it.
- **T-25** (`tests/unit/generation/`): rendering the toy schema yields `rp_service.ts` holding
  `AccountSummary`, `TenantSummary`, `TenantCreate`, `Page`, `Problem`, `GrantSet`, `LabelUpdate`,
  with `root: unknown` in `TenantCreate` and `items: unknown[]` in `Page`, no `interface Any`; and
  `index.ts` exports it once.
- **T-26** `make typecheck-ts` passes with the regenerated toy (needs Node; it runs in the CI
  "types" job).
- **`linkml:Any` becomes `unknown`.** Rendered as is (probed 2026-11-09), `rp_service.ts` holds all
  seven types and passes `tsc --strict`, but `Any` comes out as an empty `interface Any {}` and the
  slots ranging over it fall through to `string` (`typescript.py:59-60`: a class range that is not
  owned becomes `"string"`), so `TenantCreate.root: string` and `Page.items: string[]` — wrong, and
  tsc cannot see it. Fix in `range()`: a class whose `class_uri` is `linkml:Any` maps to `unknown`
  (and no `interface Any` is emitted). Only the toy target sets `typescript` (the toolkit's own
  targets in `pyproject.toml`, including `rp_wire.yaml`, which also uses `linkml:Any`, render no
  TypeScript), so the toy's generated TS is the only output that changes, and only where `Any` is used.
- Never hand-edit `rp_service.ts`.

## PD-9 Technical classes are exempt from ownership (#48, DEC-9)

- `rdf_persistence/generation/checks/boundary.py` `_ownership_problems`: skip a class whose own
  module is annotated `module_kind: technical`. Pair each class with its schema where
  `own_classes` already iterates the schemas (`schema_structure.py:176`), and read the kind with
  `annotation()` (lower-cased), as `FORBIDDEN_FOR_DOMAIN` is checked (`boundary.py:76-78`). Domain
  and access modules keep the rule.
- Nothing else changes: frames are made only for roots, so a technical class gets none; it is
  generated in Python and TypeScript like any class; its shape is harmless and stays.
- **T-27** (`tests/unit/generation/test_boundary_check.py` or its neighbour, with `toy_copy`): add a
  module `api.yaml` (`module_kind: technical`) with `Account {account_id, active}`, imported from
  the toy's root `library.yaml` (which has no `module_kind`; a domain module may not import a
  technical one) → `rp-generate` succeeds; `Account` is in the generated Python and TypeScript.
- **T-28** the same class in a domain module → still `[ownership] Account: is neither an aggregate
  root nor owned by any root`.
- Docs: `howto/adopt.adoc` (where `module_kind` is explained): a technical module may hold the
  request and response shapes of your own routes.

# Stage 4

## PD-10 Permitted actions on reads (#51, DEC-10)

- `ACTIONS = (Action.READ, Action.MODIFY, Action.DELETE, Action.ADMINISTER)` — the header's order.
- Tenant root read (`read_root`) and aggregate read (`add_aggregate_routes` `read`, which has
  `checked.caller_access` and `checked.checked_target`): `Allowed-Actions: read, modify, delete`,
  the actions `kit.rules.may(caller, access, target, a)` allows, joined by `", "`. The constant
  `ALLOWED_ACTIONS` lives in `entrypoints/negotiation.py`.
- `model/service/rp_service.yaml` `TenantSummary`: add slot `allowed_actions` (range `Action`,
  multivalued, optional); `make generate`; `Tenancy.visible_tenants` fills it from the same
  `rules.may` over `ACTIONS` with the record's access it already builds. `create` and `rename`
  leave it empty.
- OpenAPI: the header on both read operations; the slot comes with the regenerated component.
- **T-29** a member `[read, modify, delete]` reads the tenant → `Allowed-Actions: read, modify,
  delete`; a librarian → all four; a reader → `read`.
- **T-30** a reader with a Prohibition of `read` on one book is refused as today (no header); a
  member with a Prohibition of `delete` on a book reads it with `read, modify`.
- **T-31** `GET /libraries` items carry `allowed_actions` equal to the header a read of that tenant
  gives.
- **T-32** `make check-generated` and the model snapshot pass after `make generate`
  (`make refresh-snapshot` once, reviewed: one added slot).

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
| Run a validator after the conditional write | Run it before; refuse with `InvalidBody` | Nothing may be written on refusal |
| Lock or re-read to make validators "safe" | Rely on the conditional write | It is already atomic; a lock adds a failure mode |
| Hand-write or edit `rp_service.ts` | Generate it in the TypeScript step | LinkML is the single source |
| Put `allowed_actions` in the framed document | A header on reads, a slot on summaries | DEC-10: the document stays access-free |
| Patch `secrets.choice` in tests | Pass `id_source` | DEC-7: the public seam |

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
| Root `PUT` with a different label | 422 `invalid-body` | root unchanged |
| Root `PUT` with the record's label | 200 | — |
| Consumer test with step 6 imports | `assert_public_imports` passes | — |
| Consumer test importing `testkit.strategies` | refused | — |
| Rename by a `modify` role with the `Record-ETag` | 200 | — |
| Two grant writes at one version, both valid | one 200, one 409 | the first write |
| Validator raises `InvalidBody` or pydantic `ValidationError` | 422 | nothing written |
| Validator raises anything else | 500 `internal-error` | nothing written |
| `rp-generate` with a technical non-root class | succeeds | — |
| Same class in a domain module | `[ownership]` problem | nothing generated |
| Read refused (403/404) | no `Allowed-Actions` header | — |
