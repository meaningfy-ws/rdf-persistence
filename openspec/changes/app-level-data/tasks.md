> Derives from: EPIC `app-level-data` (proposal.md). One stage, one PR into `develop`.
> Type: Implementation.

`PD-n` is a decision of [design.md](design.md). `A` is the application IRI, `T` a tenant of the toy
library, `Tpl` a `Template` (the application class of PD-12), `B` a `Book` (a tenant class).

- **Default policy:** base `https://ex.org/`, prefix `lib`, no `iri_policy`.
- **Flat policy:** the same settings with `tenant_template: "{base}{tenant_id}"` and
  `aggregate_template: "{base}{tenant_id}/{type}/{id}"`; every other template and both id specs
  are the defaults.
- **A schema with no application class:** the metamodel itself; a `Tenancy` built on
  `services.access._access_mapper()` has none.

Unit tests use the fakes (`rdf_persistence/testkit/fakes.py`); integration tests use the Fuseki
container. Every task is test first, and its gates are `make test-changed`, `make check-quality`
and `make clean-code` unless it names others.

## 1. The model and which class lives where

- [x] 1.1 PD-1: `DatabaseKind.application` in `model/rp_core.yaml`, `application_template` in
  `model/service/rp_service.yaml`; `make generate`; `make refresh-snapshot` and read its diff.
  Tests in `tests/unit/domain/test_iri_policy_model.py`. Gates: `make test-fast`,
  `make check-quality`, `make check-generated` (after the lead's commit).

| ID | Input | Expected |
|---|---|---|
| TC-01 | `IriPolicy()` | `application_template == "{base}app"` |
| TC-02 | `application_template` of `{base}{deployment}/app`, `{base}{tenant_segment}-app` | accepted |
| TC-03 | `application_template` of `{base}{tenant_id}`, `{base}App`, `""`, `{tenant}/app` | each a `ValidationError` |
| TC-04 | `IriPolicy.model_validate_json` of a policy JSON without the field; of one holding the effective `"https://ex.org/app"` | both parse; the first holds the default |

- [x] 1.2 PD-4 and PD-5: `database_of`, `served_roots(view, database)`, `root_class_iris` in
  `services/schema_structure.py`; `Listings(view, database)` in `services/listing.py`; the
  application rows of the hard check in `generation/checks/hard.py`. Tests in
  `tests/unit/services/test_schema_structure_databases.py` (schemas written to `tmp_path`) and
  `tests/unit/generation/test_hard_check.py`. Gates: `make test-fast`, `make check-quality`,
  `make clean-code`.

| ID | Input | Expected |
|---|---|---|
| TC-05 | a schema with roots `Book` (no annotation), `Shelf` (`database: tenant`), `Tpl` (`application`) and a root annotated `system` with a path | `served_roots(view)` names `Book`, `Shelf`; `served_roots(view, APPLICATION)` names `Tpl`; neither names the `system` root |
| TC-06 | the same schema | `root_class_iris(view, APPLICATION)` is `{Tpl's class IRI}`; `root_class_iris(view, TENANT)` holds the IRIs of `Book` and `Shelf` only |
| TC-07 | `Listings(view).served_root("Tpl")`; `Listings(view, APPLICATION).served_root("Book")` | each a `ValueError` |
| TC-08 | `ReportTpl is_a Tpl` with its own `rp_path` and no `database` annotation | `database_of` is `APPLICATION`; `served_roots(view, APPLICATION)` and `root_class_iris(view, APPLICATION)` hold it |
| TC-09 | hard check, one schema per PD-5 row (the five rows and the mixin row), parametrized; the row-1 schema also breaks row 3 | exactly one problem per schema, rule `annotation`, message ending as its row says; plus a test that every PD-5 row has a case |
| TC-10 | hard check of a valid application root with `rp_path`, and of an abstract class annotated `application` | no problem |
| TC-11 | hard check of `database: elsewhere` | the existing "is not one of" problem, now listing three values |

- [x] 1.3 PD-12: `tests/fixtures/library/templates.yaml`, the import in `library.yaml`, the role in
  `library_roles.yaml`; `make generate`; a builder `template(iri)` in `tests/toy.py`. Fix the tests
  the new class or role breaks (counts of classes or roles). Gates: `make test-fast`,
  `make check-quality`, `make check-generated` (after the lead's commit).

| ID | Input | Expected |
|---|---|---|
| TC-12 | the toy service's OpenAPI document (`tests/unit/entrypoints/test_openapi.py`) | no path holds `templates`; no component is named `Template` |
| TC-13 | `GET /tenants/{t}/templates` on the toy app | `404`, as for any unknown path |
| TC-14 | the generated models of the toy library | `Template` exists with `label`, and round-trips through the toy mapper |

## 2. The application's IRIs

- [x] 2.1 PD-2 and PD-3 in `domain/iris.py`. Tests in `tests/unit/domain/test_iris_application.py`,
  each row under the default and the flat policy unless it names one, on
  `Iris(settings, root_types=frozenset({"template", "book"}), owned_types=frozenset({"chapter"}))`. Gates: `make test-fast`,
  `make check-quality`, `make clean-code`. The lead runs the adversarial tester right after this
  task.

| ID | Input | Expected |
|---|---|---|
| TC-15 | default policy; `iris.application`; `iris.mint_aggregate(A, "template", "templates")` | `https://ex.org/app`; `https://ex.org/app/templates/` + a UUID |
| TC-16 | flat policy; the same mint; `meta(A)`, `registry(A)` | `https://ex.org/app/template/` + a UUID; `https://ex.org/app/meta`, `https://ex.org/app/registry` |
| TC-17 | a minted `Tpl` IRI `x`, a part and a loaded graph `g` minted for it | `is_aggregate(A, x)`, `is_aggregate_graph(A, x + "/graph")`, `is_loaded_graph(A, g, x)` and `is_loaded_graph(None, g)` true; `is_aggregate(T, x)` and `is_loaded_graph(T, g)` false |
| TC-18 | a `B` IRI `b` of `T` | `is_aggregate(A, b)` false |
| TC-19 | `tenant_id_of(A)`; `tenant("app")`; `resource_name(A)` | `InvalidIri`; `NotFound`; `InvalidIri` |
| TC-20 | an `id_source` that answers `app`, then a UUID | `mint_tenant()` ends in the UUID |
| TC-21 | flat policy | `Iris` is built; `tenant_id_of("https://ex.org/app")` is `InvalidIri` |
| TC-22 | flat policy with `tenant_id` of 7 random characters and `application_template: "{base}x7k2m9p"` | `InvalidIri`, message holds "reads as a tenant" |
| TC-23 | default policy with `meta_template: "{base}{tenant_id}"` (so `meta(A) == A`) | `InvalidIri` from the distinct-graphs probe |
| TC-24 | `application_template` of `{base}toolkit`, `{base}toolkit/app`; of `app`, `https://other.org/app`, `{base}` | `InvalidIri`, message holds "the toolkit's own IRI"; "outside the base" |
| TC-25 | `application_database_name("lib")`; of `"Lib"`; of `"a-b"` | `"lib-app"`; `InvalidIri`; `InvalidIri` |
| TC-26 | `effective_policy(None, settings)` and of a policy with `application_template="{base}app"` | equal; the template reads `https://ex.org/app` |
| TC-27 | `tenant_of_access(access(A))` | `InvalidIri` |
| TC-28 | the existing `tests/unit/domain/test_iris_policy.py`, `test_iris.py` and `tests/unit/services/test_iri_policy_*.py` | green without an edit to their expectations |

## 3. The sessions

- [x] 3.1 PD-6, PD-7, PD-8: the two type sets in `services/session.py`; `tenant_session`,
  `application_session`, `ensure_application_database` in `services/tenancy.py`. Tests in
  `tests/unit/services/test_application_session.py`, on a world like `make_world` of
  `tests/unit/services/test_tenant_sweep.py` with one tenant `T`. "No update sent" is
  `store.sent("update")` unchanged. Gates: `make test-fast`, `make check-quality`, `make clean-code`.

| ID | Input | Expected |
|---|---|---|
| TC-29 | add `Tpl` through an application session; `get` it through another; `find(Template)`; list the books of `T` | read back equal; `find` answers its IRI; the listing of `T` does not hold it; the fake store holds its graph in `lib-app` only |
| TC-30 | two units of work read `Tpl` at one version, both change the label and commit | the first succeeds, the second raises `Conflict`; the stored label is the first's |
| TC-31 | parametrized, each through `UnitOfWork.commit` and through `Session.add_graph`: (`B` at an `A` IRI, application session), (the tenant root class at `A`, application session), (an access record at `access(A)`, application session), (triples that give the root no type, application session, `add_graph` only), (`Tpl` at a `T` IRI, tenant session) | `InvalidIri`; no update sent |
| TC-32 | (`Tpl`-typed root at a `T` IRI, application session); (`B`-typed root at an `A` IRI, tenant session) | `InvalidIri` from `Session._graph` (message holds "not an aggregate IRI"); no update sent |
| TC-33 | `replace_graph` of a stored `Tpl` with triples typed as `B` | `InvalidIri`; the stored graph unchanged |
| TC-34 | a `Tpl` committed, then `load_graph` and `loaded_graphs` through the application session | the loaded graph's IRI is under `Tpl`'s; listed |
| TC-35 | after TC-29 to TC-34 | every graph of `lib-system` is isomorphic to its state before |
| TC-36 | `ensure_application_database()` twice on the toy schema; on a fresh store with `create_dataset` set to raise `Conflict` | `True` then `False`, one `lib-app`; `False` and no error |
| TC-37 | a schema with no application class: `ensure_application_database()`; `application_session(p)` | `False` and no store call; `LookupError` |
| TC-38 | the start-up `sweep` with `lib-app` holding `Tpl` and no access record naming it | `lib-app` listed afterwards, `Tpl` readable |
| TC-39 | a schema with no application class; a tenant session commits a root | succeeds (nothing is refused) |
| TC-40 | `Tenancy.create` of a tenant and `set_grants` on the toy schema | succeed (the sessions `Tenancy` opens for itself refuse nothing) |
| TC-41 | a `Tpl`-typed graph put straight into `T`'s database (a class moved to `application` after it had data) | the tenant session's `get_graph` reads it and `remove` removes it; `replace_graph` is `InvalidIri` |

## 4. Access, the kit and the start-up

- [x] 4.1 PD-9, PD-10, PD-11: `AccessRules.require_application`; `ServiceKit.require_application`,
  `application_session` and `application_iri`; the `ensure_application_database` call in
  `entrypoints/service.py`; the manifest comparison in `services/tenant_dump.py`;
  `tests/unit/test_public_api.py` if a public name is added; the existing tests that pin the
  datasets after the toy lifespan (`tests/unit/entrypoints/test_service_kit.py`,
  `test_router.py`). Tests in `tests/unit/services/test_access_application.py`,
  `tests/unit/entrypoints/test_kit_application.py`, `tests/unit/services/test_iri_policy_guard.py`
  and `tests/unit/services/test_tenant_dump.py`. Gates: `make test-fast`, `make check-quality`,
  `make clean-code`.

| ID | Input | Expected |
|---|---|---|
| TC-42 | `AccessRules` built from the definitions `admin` (system, `[read]`), `app-editor` (system, `[read, modify]`), `writer` (system, `[modify]`), `librarian` (tenant, all four actions); parametrized over every `Action` and callers whose global roles are: none; `admin`; `app-editor`; `writer`; `librarian`; `ghost` (no definition) | allowed exactly when the action is in the caller's system permits, or is `read` and another action is; else `Forbidden`, never `NotFound` or `KeyError` |
| TC-43 | a caller granted `owner` on `T`, no global role; `require_application(header, MODIFY)` | `Forbidden`; no store call |
| TC-44 | `require_application` with `app-editor` | `Authorised` whose `checked_target` and `caller_access.tenant` are `A`, state `active`, no grants |
| TC-45 | `require_application` with no header; with a refused token | `InvalidToken` |
| TC-46 | `kit.application_iri(Template)`; `kit.application_iri(Book)` | an IRI `is_aggregate(A, …)` accepts; `InvalidIri` |
| TC-47 | the toy app's lifespan on empty fakes | `lib-system` and `lib-app` exist; a second start changes nothing. With TC-37 this proves "a schema without application classes creates no application database": the lifespan calls the one function TC-37 tests |
| TC-48 | a system database whose recorded policy JSON has no `application_template`; start with the default; start with `application_template="{base}application"` | passes; `IriPolicyChanged` naming `application_template` |
| TC-49 | `B` of `T` written with one extra triple whose object is `Tpl`'s IRI (raw triples through `Session.add_graph`; UUID ids); dump `T`; restore | the restored `B'` holds the same `Tpl` IRI |
| TC-50 | a dump whose manifest policy lacks `application_template`; restore on a default-policy service | restored |

## 5. The proof and the docs

- [ ] 5.1 `tests/feature/application_data.feature` with its steps in
  `tests/feature/test_application_data.py`, on the fakes: one scenario per scenario of the
  [rp-tenancy](specs/rp-tenancy/spec.md) and [rp-access](specs/rp-access/spec.md) deltas, in their
  words. The `rp-iri-policy` scenarios are covered by TC-15, TC-21, TC-22 and TC-48. Gates:
  `make test-changed`, `make check-quality`.
- [ ] 5.2 `tests/integration/tenancy/test_application_data.py` on Fuseki, a fresh prefix per test
  (`unique_prefix`), datasets dropped afterwards (`drop_databases`). Gates: `make test-containers
  TEST_PATH=tests/integration/tenancy/test_application_data.py`, `make check-quality`.

| ID | Flow | Verification |
|---|---|---|
| IT-01 | start the toy service; add `Tpl` through an application session; read it through a new one | equal; the dataset `{prefix}-app` exists |
| IT-02 | two replaces of `Tpl` at the same version | the second raises `Conflict` |
| IT-03 | create `T` and a `B`; add `Tpl`; list `T`'s books; run the start-up sweep | the listing holds only `B`; `{prefix}-app` and `Tpl` survive the sweep |
| IT-04 | commit `B` through the application session | `InvalidIri`; `{prefix}-app` holds no graph of `B` |

- [ ] 5.3 Docs: the how-to `docs/modules/ROOT/pages/howto/application-data.adoc` in the nav, with:
  when to use it; the schema annotation; `require_application`, `application_iri`,
  `application_session` in one example; the start-up call for a consumer without
  `install_service`; who may do what (PD-9 and RISK-1); references across the boundary (DEC-4);
  moving a class that already has data (RISK-7, the three steps); the limits (RISK-2, RISK-6, the
  no-gos). The question "Where does data that belongs to no project go?" in
  `docs/modules/ROOT/pages/questions.adoc`. In the architecture pages, one sentence each, in
  toolkit terms: the `Tenancy` row of the components table in `architecture/index.adoc` (it also
  keeps the application database), the start-up paragraph of `architecture/api.adoc` (the
  application database is created after the policy guard), and the "Limits" line of
  `architecture/data-flows.adoc` (nothing spans a tenant and the application database either).
  The durations table in `develop/index.adoc` if a check's time moved. Gates: `make check-docs`,
  `make check-quality`.

## Docs stage

Covered by 5.3; `evidence/docs-owed.md` records it.

## Close

Acceptance (the demo offered to the developer, the verdict in `evidence/acceptance.md`), then
`openspec archive app-level-data --yes`.
