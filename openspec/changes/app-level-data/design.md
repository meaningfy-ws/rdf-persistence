> Derives from: EPIC `app-level-data` ([proposal.md](proposal.md)). Type: Implementation.
> Test cases are in [tasks.md](tasks.md); acceptance scenarios are in the spec deltas
> ([rp-tenancy](specs/rp-tenancy/spec.md), [rp-access](specs/rp-access/spec.md),
> [rp-iri-policy](specs/rp-iri-policy/spec.md)).

## Context

Every session today belongs to a tenant. `Session` (`rdf_persistence/services/session.py`) takes a
database name and a tenant IRI and accepts only IRIs that `Iris.is_aggregate(tenant, iri)` accepts;
it knows IRIs, not classes. The classes the generic router and `Session.find` serve come from
`schema_structure.served_roots`: the aggregate roots that carry an `rp_path` and are not annotated
`database: system`. Access is decided by `AccessRules.require`, which adds the caller's grants in a
tenant to what its global roles permit at level `system`. The start-up
(`entrypoints/service.py`, `_run_at_startup`) creates the system database, guards the IRI policy
and sweeps databases named `{prefix}-t-…`.

The EPIC treats the application space as "a tenant whose IRI is the application IRI and whose
`{tenant_id}` is the word `app`" (DEC-5). The plan: `Iris` mints and matches for that one extra
IRI without ever calling it a tenant; the unchanged `Session` is opened on a second database with
it; and the two sets of classes are kept apart at three places (the listing of served roots, the
session's writes, the generation check).

## Goals / Non-Goals

**Goals:** the three spec deltas, through `ServiceKit.require_application`,
`ServiceKit.application_session` and `ServiceKit.application_iri`; the toy library gains one
application class.

**Non-Goals:** the EPIC's no-gos (no routes or OpenAPI paths, no grants, no bucket, no sweep or
dump of the application database, no cross-database read). No new role level (PD-9). No change to
`Session`'s reads, versioning or transactions. No tool that moves stored aggregates of a class
re-annotated from `tenant` to `application` (RISK-7).

## Decisions

PD-5 to PD-11 answer questions the code raised that the EPIC did not cover; the record is
[inputs/questions-2026-11-14.md](inputs/questions-2026-11-14.md). They are the lead's choices
(2026-11-14); the developer may overrule any of them. `A` is the application IRI.

- **PD-1, the model** (DEC-5, DEC-6). In `rdf_persistence/model/rp_core.yaml`, `DatabaseKind`
  gains `application` (`meaning: rp:DatabaseApplication`, title "Application", description "The
  application database, one per deployment, outside every tenant."), and the `database` entry of
  `RpAnnotation` names the three values. In `rdf_persistence/model/service/rp_service.yaml`,
  `IriPolicy` gains the slot `application_template` (`slot_uri: rp:applicationTemplate`, title
  "Application template", `range: string`, `ifabsent: string({base}app)`, pattern
  `^(?:[a-z0-9/:.-]|\{(?:base|deployment|tenant_segment)\})+$`, the form of the other templates:
  the recorded policy and a dump's manifest hold the effective template, with the base written in,
  and are parsed by the same model), listed after `tenant_template`. That `A` is under the base is
  checked by `Iris` (PD-3). The name ends in `_template`, so `effective_policy`,
  `check_iri_policy` (`{deployment}` needs a slug), `policy_differences` and
  `domain/tenant_move.glued_templates` cover it with no code change. A recorded policy without the field
  parses with the default (the generated model gives `ifabsent` as the field default). Consequence:
  a deployment that already has a policy record can use only the default application template
  (RISK-6).
- **PD-2, names** (DEC-1, DEC-5), in `rdf_persistence/domain/iris.py`: the constants
  `APPLICATION_ID = "app"` and `APPLICATION_SUFFIX = "-app"`, and
  `application_database_name(prefix) -> str`, which answers `{prefix}-app` and validates the prefix
  like `system_database_name`. A prefix holds no hyphen (`_PREFIX`), so `{prefix}-app` never starts
  with any deployment's `{prefix}-t-`, and the sweep never lists it.
- **PD-3, `Iris` mints and matches for the application, and never calls it a tenant** (DEC-5).
  All in `Iris`:

  | Member | Change |
  |---|---|
  | `application` (new cached property) | the `application_template` filled with the settings, a `URIRef` |
  | `_reserved` | always holds `APPLICATION_ID`, so no tenant id is ever drawn as `app` |
  | `_id_of(tenant)` (new, private) | `APPLICATION_ID` when `str(tenant) == str(self.application)`, else `self.tenant_id_of(tenant)` |
  | `_fill` | fills `{tenant_id}` from `_id_of`, not `tenant_id_of` |
  | `_pattern(template, types, application=False)` | with `application=True` the group `tenant_id` is `(?:<the id pattern>\|app)`; `_aggregate_re` and `_loaded_re` pass `True`; `_tenant_re` and `_access_re` do not |
  | `_belongs(found, tenant)` | a matched `id` that is a reserved word is refused, as today; a matched `tenant_id` that is a reserved word is refused unless it is `app`; then, when `tenant` is given, the matched `tenant` (if any) must equal it and the matched `tenant_id` (if any) must equal `_id_of(tenant)` |
  | `__init__` | `InvalidIri("the application template mints an IRI that reads as a tenant: …")` when `_tenant_re.fullmatch(A)`; `InvalidIri("the application template mints the toolkit's own IRI: …")` when `A` equals `toolkit_principal_iri(base)` or starts with it and `/`; `InvalidIri("the application template mints an IRI outside the base: …")` when `A` does not start with `settings.base` or equals it |
  | `_require_distinct_graphs` | runs its probe for `A` as well as for the probe tenant |

  The `__init__` checks run in this order, so a value that breaks two rules always gets the same
  message: outside the base, then the toolkit's own IRI, then reads as a tenant, then
  `_require_distinct_graphs`.

  Unchanged, and their answer for `A`: `tenant_id_of(A)` is `InvalidIri` (the tenant pattern is
  not widened, and an id has at least 4 characters, so `app` is never one); `tenant("app")` is
  `NotFound`; `resource_name(A)` is `InvalidIri` (it calls `tenant_id_of`); `tenant_of_access(access(A))`
  is `InvalidIri` (its last guard is `_tenant_re`, and `_access_re` is not widened). The three
  callers of `tenant_id_of` outside `Iris` (`Tenancy.restore`, `tenant_dump.dump`,
  `tenant_dump._check_manifest`) therefore keep refusing `A`. `access`, `meta`, `registry`,
  `mint_aggregate`, `aggregate`, `mint_part`, `mint_loaded_graph`, `is_aggregate`,
  `is_loaded_graph` and `is_aggregate_graph` need no edit: given `A` as `tenant` they follow the
  existing templates through `_fill` and `_belongs`.
- **PD-4, which classes live where**, in `rdf_persistence/services/schema_structure.py`:
  - `database_of(view, cls) -> DatabaseKind`: the `database` annotation of the first class in
    `view.class_ancestors(cls.name, mixins=False)` (the class itself, then its `is_a` parents, as
    `hard._inherited_path` walks them) that carries one; `tenant` when none does. A subclass of an
    application class is an application class; a mixin's annotation does not count.
  - `served_roots(view, database=DatabaseKind.TENANT)`: the aggregate roots with a path whose
    `database_of` is `database`. For `TENANT` the result is today's minus the application classes (and minus an
    unannotated subclass of a `system` class, which now inherits `system`), so `Documents.aggregates`, `Aggregates`, the generic router and the OpenAPI document leave them
    out with no change of their own.
  - `root_class_iris(view, database) -> frozenset[URIRef]`: the expanded class IRIs
    (`view.get_uri(cls, expand=True)`) of the concrete aggregate roots whose `database_of` is
    `database`.
  - `Listings.__init__(view, database=DatabaseKind.TENANT)` in `services/listing.py` passes
    `database` to `served_roots`, so an application session's `find` plans against the application
    classes and a tenant session's `find(Template)` raises the `ValueError` it raises today for a
    class it does not serve.
  - `iri_types` and `Mapper` keep every root: the `{type}` values and the mapper are shared.
- **PD-5, the generation check** (DEC-6, Q-11), in `rdf_persistence/generation/checks/hard.py`,
  called from `_class_problems`, reported under `HardRule.ANNOTATION` (no new rule id). For each
  class of the consumer's schema whose `database_of` is `application`, the first row that holds
  gives one problem:

  | # | The class | Message ends with |
  |---|---|---|
  | 1 | is the tenant root (`graph: meta`) | `an application class cannot be the tenant root` |
  | 2 | is the range of an `owned` slot | `an application class cannot be owned; its owner decides the database` |
  | 3 | is not an aggregate root (abstract and mixin classes are skipped, not reported) | `only an aggregate root can be application-level` |
  | 4 | is a `StoredFile` | `an application class cannot be a stored file: the application space has no bucket` |
  | 5 | has the same class IRI as a root of another database | `an application class cannot share its class IRI with <name>` |

  And one row for mixins, which `database_of` does not walk: a mixin that itself carries
  `database: application` gives `the database annotation is not inherited through a mixin`.

  A missing `rp_path` is already reported by `_path_problems`.
- **PD-6, the session refuses a class of the other space** (DEC-6, Q-7). `Session.__init__` and
  `open_session` gain `refused_types: frozenset[URIRef] = frozenset()` and
  `allowed_types: frozenset[URIRef] | None = None`. `Transaction.add_graph` and
  `Transaction.replace_graph` call `session._refuse_foreign(iri, triples)` first, before `_claim`;
  `Session.add_graph`, `Session.replace_graph` and `UnitOfWork.commit` all write through these
  two. With `types` the objects `t` of the triples `(URIRef(iri), RDF.type, t)`:

  | Session | Raises `InvalidIri` when | Message |
  |---|---|---|
  | tenant (`refused_types` set) | `types & refused_types` | `{iri!r} is an application aggregate and does not belong in a tenant database` |
  | application (`allowed_types` set) | not `types & allowed_types` | `{iri!r} is not an application aggregate` |
  | any other (both unset) | never | — |

  The application session is new, so it takes the allow-list: an untyped root, the tenant root
  class at `A`, and an access record at `access(A)` are all refused. A tenant session keeps a
  deny-list, so what it accepts today it still accepts. The signature is
  `Session._refuse_foreign(iri: str, triples: Iterable[Triple]) -> list[Triple]`: it answers the
  triples as a list, which the transaction uses from then on (an iterable can be read once). Nothing is sent to the store: a
  transaction sends only on `commit`. Not covered, on purpose: reads (nothing of the other space
  is stored, so `get_graph` is `NotFound`); `remove` (it needs a stored graph); `load_graph` (a
  loaded graph has no class, and belongs to an aggregate the session accepts); and
  `Tenancy.restore`, which imports quads after checking graph names only and already says it
  checks structure, not objects (`ServiceKit.restore_tenant`'s docstring).
- **PD-7, the two sessions**, in `Tenancy` (`rdf_persistence/services/tenancy.py`), which already
  owns `_session` and the system database:
  - `tenant_session` passes `refused_types=root_class_iris(view, APPLICATION)`.
  - `application_session(principal) -> AbstractAsyncContextManager[Session]` opens a session with
    `database=application_database_name(prefix)`, `tenant_iri=iris.application`,
    `listings=Listings(view, APPLICATION)` and `allowed_types=root_class_iris(view, APPLICATION)`.
    It raises `LookupError("the schema declares no application class")` when that set is empty, at
    the call, not on entering the context.
  - The sessions `Tenancy` opens for itself through `_session` (access records in the system
    database, the tenant root at creation) pass neither set, as today.
  - `view` is `mapper.view`; the set and the application `Listings` are computed once in
    `__init__`.
- **PD-8, the application database** (DEC-1, Q-10). `Tenancy.ensure_application_database() ->
  bool`: `False` without a store call when the schema has no application class; otherwise creates
  `{prefix}-app` unless `list_datasets` names it, suppressing `Conflict` (another worker created
  it), and answers `True` only when its own `create_dataset` call succeeded (`False` when the
  database was listed or the `Conflict` was suppressed). Safe to call on every start. `_run_at_startup`
  calls it after `guard_iri_policy` and before `sweep`. A consumer with its own start-up calls it
  itself (the how-to says so). The session does not create the database: a missing one is the
  store's `DatabaseGone`, as for a tenant.
- **PD-9, access** (DEC-2, Q-5, Q-6).
  - `AccessRules.require_application(caller, action) -> None` in `services/access.py`: the
    permitted actions are the union of `self._permits.get((RoleLevel.SYSTEM, role), set())` over
    `caller.global_roles or []`; it returns when `action` is among them, or when `action` is
    `read` and any other action is (`_IMPLY_READ`, the existing rule); otherwise
    `Forbidden(f"{action.value} is not permitted on application data")`. Never `NotFound`: that
    the application space exists is not a secret. No grant and no prohibition is read.
  - `ServiceKit.require_application(authorization, action) -> Authorised`: `gate.caller`, then the
    rule above, then `Authorised(principal=caller.principal,
    caller_access=CallerAccess(tenant=A, state=TenantState.ACTIVE), checked_target=A)`.
    `Authorised.principal` is the principal's IRI, a `str`. No store call.
  - `ServiceKit.application_session(principal: str)` wraps `tenancy.application_session`.
  - Consequence, stated in the how-to: a role at level `system` permits its actions in every
    tenant as well, so an application editor can edit every tenant, and a system-level reader that
    already exists can read application data. A role for application data only needs a new role
    level, which is a later change (RISK-1).
- **PD-10, minting an application IRI.** `ServiceKit.application_iri(cls: type[BaseModel]) -> str`
  answers `str(iris.mint_aggregate(A, iri_type_of(c), rp_path))` for `c = view.get_class(cls.__name__)`,
  and raises `InvalidIri(f"{cls.__name__} is not an application class")` when `c` is not in
  `served_roots(view, APPLICATION)`. Without it a consumer would have to know the class's `{type}`
  and path. (Q-8 of the question record, a tenant already named `app`, needs no decision: an id
  has at least 4 characters.)
- **PD-11, old dumps** (Q-9). `tenant_dump._check_manifest` compares
  `effective_policy(manifest.iri_policy, iris.settings)` with `iris.effective_policy`, so a
  manifest without `application_template` reads as the default. Filling in an already effective
  policy changes nothing (its templates hold no `{base}` any more).
- **PD-12, the toy library.** A new module `tests/fixtures/library/templates.yaml`
  (`module_kind: domain`, imported by `library.yaml`) with the class `Template` ("A report
  template shared by every library", `class_uri: lib:Template`, mixins `[AggregateRoot, Described,
  Tracked]`, annotations `rp_path: templates`, `database: application`), and
  `{role: app-editor, level: system, actions: [read, modify]}` added to `library_roles.yaml`.
  `make generate` regenerates `generated/`, `golden/` and `web/`.

## Algorithm / approach

Worked example, base `https://ex.org/`, prefix `lib`, tenant id `7f3c…` (a UUID), object id `9a1b…`.
The flat policy is the one [tasks.md](tasks.md) defines:

| IRI | Default policy | Flat policy |
|---|---|---|
| `A` | `https://ex.org/app` | `https://ex.org/app` |
| a `Template` | `https://ex.org/app/templates/9a1b…` | `https://ex.org/app/template/9a1b…` |
| its graph | `…/app/templates/9a1b…/graph` | `…/app/template/9a1b…/graph` |
| application registry graph | `https://ex.org/app/registry` | `https://ex.org/app/registry` |
| a `Book` of the tenant | `https://ex.org/tenants/7f3c…/books/9a1b…` | `https://ex.org/7f3c…/book/9a1b…` |
| database of the tenant / the application / the system | `lib-t-7f3c…` / `lib-app` / `lib-system` | the same |

One write, end to end:

1. `kit.require_application(header, Action.MODIFY)`: verify the token, union the `system`-level
   permits of its global roles, `Forbidden` unless `modify` is among them.
2. `kit.application_session(principal)`: `LookupError` if the schema has no application class;
   else a `Session` on `lib-app` with `A` as its tenant.
3. `UnitOfWork.add(Template(id=kit.application_iri(Template), label=…))`, `commit()`:
   `Transaction.add_graph` first refuses a root that is not an application class (PD-6), then
   `Session._graph` refuses an IRI that is not the application's (`Iris.is_aggregate`), then the
   transaction is sent as for a tenant.

Idempotency: `ensure_application_database` is safe on every start and under concurrent workers
(PD-8). The policy record needs no migration (PD-1). Writes keep the session's version check;
nothing here retries.

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Open the application session on the system database | `application_database_name(prefix)` only (PD-2, PD-7) | An application write could then reach an access record (DEC-1) |
| Add `if application:` branches to `Session` | Give `Session` `A` as its tenant and the two type sets (PD-6) | The session stays one code path; reads, versions and loaded graphs work unchanged |
| Make `tenant_id_of`, `_tenant_re` or `tenant()` accept `A` or `app` | The private `_id_of` and the `application=True` patterns (PD-3) | Dump, restore and `tenant_of_access` read "this matches a tenant" as "this is a tenant with a database and an access record" |
| Decide the space of a class from its IRI's `{rp_path}` or `{type}` segment | The root's `rdf:type` against `root_class_iris` (PD-4, PD-6) | A policy may write neither segment into an aggregate IRI |
| Read the `database` annotation with `annotation(cls, …)` alone | `database_of(view, cls)` (PD-4) | Annotations are not inherited; a subclass of an application class would silently be a tenant class |
| Call `AccessRules.require` with an empty `CallerAccess` for application data | `AccessRules.require_application` (PD-9) | `require` answers `NotFound` when nothing is permitted; the spec asks for `Forbidden` |
| Hand-write `Template`, its shape or its frame, or edit a golden | Change the YAML and run `make generate` (PD-12) | LinkML is the single source (PD-24 of [toolkit v1](../archive/2026-11-06-toolkit-v1-foundation/design.md)) |
| Add the application class to `served_roots`' default, the router or the OpenAPI document | Leave `served_roots(view)` at `TENANT` (PD-4) | Generic routes for application data are a no-go (DEC-3) |
| Write a migration for the recorded IRI policy | Rely on the model default (PD-1) | An existing deployment must start unchanged (DEC-5) |

## Error matrix

The store and the token verifier are the only external services; their failures
(`StoreUnavailable`, `DatabaseGone`, `InvalidToken`) pass through unchanged, as for a tenant
session. Start-up refusals are logged at `ERROR` by the code that raises them, as
`iri_policy_guard._require_same` does; a refused request is not logged by the toolkit.

| Failure mode | How it is detected | Expected handling |
|---|---|---|
| The caller's global roles do not permit the action | `AccessRules.require_application` | `Forbidden("<action> is not permitted on application data")`; nothing read or written |
| No bearer token, or one the verifier refuses | `Gate.caller` | `InvalidToken`, unchanged |
| `application_session` on a schema with no application class | `Tenancy.application_session` | `LookupError("the schema declares no application class")` at the call |
| `application_iri` for a class that is not an application class | `ServiceKit.application_iri` | `InvalidIri("<name> is not an application class")` |
| Through the application session: a tenant class, the tenant root class, an access record, or a root with no type | `Session._refuse_foreign` (PD-6) | `InvalidIri`; nothing sent |
| An application class written through a tenant session | the same | `InvalidIri`; nothing sent |
| An application-typed root at a tenant's IRI through the application session, or a tenant-typed root at an application IRI through a tenant session | `Session._graph`, unchanged | `InvalidIri`; nothing sent |
| Two replaces of one application aggregate at the same version | the session's version check, unchanged | the second raises `Conflict`; nothing changed |
| The application database is missing (start-up step not run, or dropped) | the store | `DatabaseGone` from the first read or commit; the fix is to call `ensure_application_database` |
| Two workers create the application database at once | `Conflict` from `create_dataset` | suppressed; both go on (PD-8) |
| `A` reads as a tenant IRI, is the toolkit's own IRI or under it, or is not under the base | `Iris.__init__` (PD-3) | `InvalidIri`, the PD-3 messages; the service does not start |
| The application's access, meta or registry IRIs coincide, or one reads as an aggregate | `Iris._require_distinct_graphs` (PD-3) | `InvalidIri`, the existing messages; the service does not start |
| `application_template` uses `{deployment}` and no slug is set | `check_iri_policy`, unchanged | `InvalidIri` |
| The configured `application_template` differs from the recorded policy, or from the default when the record has no such field | `guard_iri_policy`, unchanged | `IriPolicyChanged` naming `application_template`; the service does not start |
| A recorded policy, or a dump's manifest, without `application_template` | read as the default (PD-1, PD-11) | start-up passes; the restore passes when the service uses the default |
| `tenant_id_of`, `resource_name` or `tenant_of_access` asked about `A`; a dump manifest naming `A` as its tenant | unchanged code (PD-3) | `InvalidIri` (the manifest: `InvalidBody`, as for any inconsistent manifest) |
| A schema breaks a PD-5 row | the hard check | generation fails with the row's message |

## Risks / Trade-offs

- **RISK-1, a role cannot be scoped to application data.** Likelihood: certain, by DEC-2. Impact:
  a consumer that wants an application-only editor cannot have one. Accepted (PD-9); the how-to
  says it; a role level `application` is additive later.
- **RISK-2, a downgrade, or a dump read by an older service.** A deployment first started on this
  version records a policy holding `application_template`, and its dumps carry it; an older
  toolkit forbids unknown fields and calls both unreadable. Likelihood: low. Impact: the older
  version does not start, or refuses the dump. Accepted: the how-to says so.
- **RISK-3, dump and restore with short tenant ids.** `domain/tenant_move.rewrite` replaces the old
  tenant id wherever it stands as a delimited token in an IRI under the base, so an application
  IRI that holds that token (possible only with short random ids, never with UUIDs) is rewritten
  on restore. Likelihood: very low. Impact: one dangling reference. Accepted: it is the existing
  limit of `domain/tenant_move.rewrite` ([tenant-dump-restore RISK-3](../archive/2026-11-13-tenant-dump-restore/design.md)); TC-49 pins the UUID case.
- **RISK-4, sessions D and E change the same files** (`kit.py`, `tenancy.py`, `session.py`,
  generated code). Likelihood: high. Mitigation: rebase on `develop` before the PR; on a conflict
  in a generated file take `develop`'s version and run `make generate`.
- **RISK-5, application and tenant IRIs under one path.** A policy may put `A` where it is a
  prefix of tenant IRIs (`{base}tenants`). The two never share a database, and `Iris._belongs`
  compares the tenant exactly, so no check confuses them. Accepted without a further rule.
- **RISK-6, the application template is fixed from the first start.** "Absent means the default"
  (DEC-5, the `rp-iri-policy` delta) means a deployment that already has a policy record cannot
  choose another application template, even before it has application data; and one whose
  existing templates make the default collide (for example `meta_template: "{base}{tenant_id}"`,
  under which the application's meta graph is `A` itself) cannot start on this version.
  Likelihood: low (`{tenant}/meta` is the default and the only form in use). Impact: that
  deployment stays on the previous version until the rule is changed. Accepted for this change;
  the how-to says it. The fix, if it is ever needed, is to let a record without the field take the
  configured template once, which changes the spec sentence and is the developer's call.
- **RISK-7, a class moved from `tenant` to `application`.** Its stored aggregates stay in the
  tenant databases: a tenant session still reads them by IRI and removes them, but no longer
  replaces, finds or serves them. Likelihood: medium (it is how a "settings tenant" is retired).
  Impact: a one-off move the consumer writes (read through the tenant session, add through the
  application session under a new IRI, remove). Accepted: no move tool in this change; the how-to
  gives the steps and TC-41 pins what still works.

## Open Questions

None. Each question of the [record](inputs/questions-2026-11-14.md) has its answer: Q-5 and Q-6
in PD-9, Q-7 in PD-6, Q-8 withdrawn (PD-10), Q-9 in PD-11, Q-10 in PD-8, Q-11 in PD-5, Q-12 in
RISK-6, Q-13 in PD-10, Q-14 in RISK-7. The EPIC's example reads `authorised.principal.id`; the
field is a `str` (PD-9), and the how-to shows the correct call.

## Gate record

- Attack, 2026-11-14: a fresh reviewer, 15 findings; see D-2.
- Clarity gate run 1, 2026-11-14, a fresh scorer: 7.8/10. Nine gaps, the costly one that the
  `application_template` pattern refused the effective template the policy record and a dump's
  manifest hold. All fixed.
- Clarity gate run 2, 2026-11-14, the same scorer: 9.0/10, pass. Its two remaining remarks (the
  mixin row of PD-5, the order of the `Iris.__init__` checks) are worked in.

## Delivery decisions

- **D-1** (lead, 2026-11-14): one stage, one PR into `develop`. The full MEDIUM review set: lenses
  L1, L2, L3 and one pass for L4 with L5 (repository rule), a checker, and the adversarial tester
  right after task 2.1 (the `Iris` change adds the invariants every other task relies on).
- **D-2** (lead, 2026-11-14): the PLAN was attacked by a fresh reviewer before the gate. Accepted
  and worked in: `tenant_id_of` and the tenant pattern stay closed to `A` (PD-3); the `database`
  annotation is inherited (PD-4); a shared class IRI is refused (PD-5 row 5); the application
  session takes an allow-list (PD-6); a kit call mints the IRI (PD-10); RISK-6 and RISK-7. Dropped
  as unfounded on its finding: the check for a tenant already named `app` (an id has at least 4
  characters).
