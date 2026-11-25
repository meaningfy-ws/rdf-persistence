# Design: grant-roles

> Derives from: EPIC `grant-roles` (`proposal.md`: #307, #310). Its DEC-1 to DEC-7 are cited here,
> not restated. The delivery decisions below are D-n, each a heading (`design.md#d-1`, …).

## Context

Code facts, read on `develop` at `f9f6fa74`:

- **Grants.** A grant is an owned part (`grants`, `rp:grant`, inlined) of a tenant's access record,
  in the record's graph in the system database (`rp_tenancy.yaml` l.154).
  - A grant's role is the string literal `rp:role` (`rp_access.yaml` l.108). Its assignee and
    target are IRIs (`schema_structure.py` l.190-193).
  - `grant_key` is unique on assignee, target, role and action (`rp_access.yaml` l.58-65).
    `GrantSet` and `TenantAccess` both refuse duplicate keys when they are built
    (`rp_access_services.py` l.89-96, `rp_tenancy.py` l.127).
  - A grant part is a blank node or a skolem IRI (`mapper.py` l.214), not derived from content.
  - A record that does not decode makes `Tenancy._records` raise for every record
    (`tenancy.py` l.716-726). `_records` feeds `access_records()` (l.733) and `tenants()`, and so
    `migrate_tenants`.
  - Roles are defined per `(RoleLevel, name)`. A grant's level comes from its target: the tenant
    IRI gives the tenant level; an aggregate graph, or the access record's graph, gives the
    aggregate level (`access.py` l.118-120, l.220-224).
- **The system database is migrated with every chain.** `_stamp_of` stamps a database that has
  no stamp yet (`migration_runner.py` l.69-71, l.216-223), so a consumer migration's stamp guard
  matches there.
- **Migrations.**
  - `migration_request(migration, stamps)` builds one request: the steps (`_STEP`, each guarded by
    the `from_version` stamp and skipping registry and loaded graphs), the token rotation when
    there is a step, then the stamp move (`migrations.py` l.232-255).
  - `_request_problem` checks that the request parses into the expected number of operations
    (l.314).
  - The runner calls it at l.159 (`_migrate_in_memory`, for `migrate_dataset`) and at l.259
    (`_apply`).
  - `migrate_shared` migrates the system database, then the application database, with every
    chain (`migration_runner.py` l.62-90; `_shared_databases` l.185).
  - Start-up order: `migrate_shared`, `sweep`, `migrate_tenants` (`service.py` l.190-192).
- **Roles.**
  - `AccessRules._permits` is keyed by `(RoleLevel, name)`.
  - `validate_grants` raises `UnknownRole` on the first grant whose `(level, role)` is undefined
    (`access.py` l.199-217).
  - `defines(role)` looks at the name, at any level.
  - `roles(caller, access, iri)` gives the caller's role grants in scope plus its token roles that
    are defined at system level (l.281-298).
  - `Collaboration` holds `_rules`, `_caller` and `_access` (`collaboration.py` l.58-61).
  - The aggregate read sets `Allowed-Actions` from `rules.allowed_actions` (`router.py` l.141-142;
    `negotiation.py` l.25). `openapi.py` declares it with `_with_allowed_actions` (l.191-196),
    which is applied at l.324 and l.485.
  - `rules.roles` raises `NotFound` for a target outside the tenant (l.345-351).
  - `Discussion.thread` also requires the discussion module (`discussion.py` l.216).

## Goals / Non-Goals

**Goals:** #307's two answers, in code and in the how-to, and #310's acceptance, each as a test
that fails first.
**Non-Goals:** the EPIC's No-gos.

## Decisions

### D-1

The model (DEC-1). `rp_migrations_services.yaml` gains:

- a class `GrantRoles`, with `rename` (a list of `RoleRename {from_role, to_role}`, because LinkML
  has no plain map) and `drop` (a list of strings);
- a `grant_roles` slot (range `GrantRoles`, inlined, optional) on `Migration`.

The YAML file still reads as a map: `load_migration` turns `rename: {old: new}` into the list
before it validates. Then `make generate`.

### D-2

The load checks (DEC-4) go into `_validated` / `_step_problem`'s neighbour `_grant_problem`. Each
message names the file:

- a dropped name that is also a rename source **or** a rename target;
- a rename target that is also a rename source (no chains);
- an empty name;
- a rename to the same name.

Two sources renamed to one target (`{reader: member, viewer: member}`) are allowed: a merge.

### D-3

`migration_request(migration, stamps, *, grants: bool = False)` (DEC-2). When `grants` is true and
the file has `grant_roles`, the grant operations go after the steps and before the rotation. The
rotation is emitted when there are steps **or** grant operations. `_request_problem` builds with
`grants=True`, so the count covers them. Callers:

- The flag is passed through explicitly: `migrate_shared` calls
  `migrate_database(..., grants=(database == tenancy.system_database))`, then
  `_migrate_schema(..., grants=)`, then `_apply(..., grants=)`, then `migration_request`. Each
  gains a keyword `grants: bool = False`.
- `migrate_tenants` and `_migrate_in_memory` pass nothing (False).

### D-4

The grant operations reuse the step guard. `migrations.py` builds each one as a toolkit-written
`MigrationStep` (`where_pattern`, `delete_pattern`, `insert_pattern`) and sends it through the
existing `_step_operation`. So every operation inherits the `_STEP` wrapper:

- the stamp guard;
- `?rp_graph` as the graph variable;
- `FILTER (?rp_graph != $stamps)`;
- the registry and loaded-graph exclusions.

The grant predicates are not in `_OWN_PREDICATES`, so `checked_group` accepts them. The role
names enter as literals made with `term()`, never by string concatenation. The predicate IRIs
come from the access schema view (`rp:grant`, `rp:role`, and the `slot_uri`s of assignee and
target), not typed by hand.

**Order:** one rename's operation 1, then its operation 2, then the next rename, in file order;
the drops last. This order is what keeps a merge (two sources into one target) from leaving
duplicates (T3b). Since a record with a duplicate grant does not decode and would stop
`migrate_tenants`, operation 1 is what keeps start-up alive (RISK-1).

**A rename applies at every level.** A tenant-level grant and an aggregate-level grant naming
`reader` are renamed together (No-gos; the how-to says so).

A rename makes two operations; their patterns, shown inside the `_STEP` wrapper:

```sparql
# 1. a grant whose renamed form exists goes (DEC-3)
DELETE { GRAPH ?g { ?rec rp:grant ?old . ?old ?p ?o } }
WHERE  { GRAPH $stamps { $schema_id $p_stamp $from_version }
         GRAPH ?g { ?rec rp:grant ?old . ?old rp:role $from ; odrl:assignee ?a ; odrl:target ?t .
                    ?rec rp:grant ?new . ?new rp:role $to ; odrl:assignee ?a ; odrl:target ?t .
                    ?old ?p ?o } }
# 2. the rest is renamed in place
DELETE { GRAPH ?g { ?x rp:role $from } } INSERT { GRAPH ?g { ?x rp:role $to } }
WHERE  { GRAPH $stamps { … } GRAPH ?g { ?rec rp:grant ?x . ?x rp:role $from } }
```

(The sketch writes `GRAPH ?g` for readability; the operations use the wrapper's `?rp_graph`.)
A drop deletes `?rec rp:grant ?x` and every `?x ?p ?o` where `?x rp:role $name`.

### D-5

The report (DEC-5). Two new methods on `AccessRules`:

- `undefined_roles(grants: Iterable[Grant], tenant) -> list[tuple[RoleLevel, str]]`: the
  undefined `(level, role)` pairs, in the grants' order. `validate_grants` uses it and raises
  `UnknownRole` for the first pair, with today's message (it names the level), so its behaviour
  is unchanged.
- `administered(grants: Iterable[Grant], tenant) -> bool`: whether any grant gives
  `Action.ADMINISTER` on the tenant (through `_granted`).

A new function, `report_grants(tenancy, rules)`, in `tenancy/services/` beside the runner, does
the following:

1. Read every record once with the existing `Tenancy.access_records()`. If any record fails to
   decode (`StoredDataInvalid`) or the store fails (`PersistenceError`), log it at `ERROR` and
   skip the report.
2. Log `WARNING "grants name undefined roles"` with `extra` (step `check-grants`, `tenant_id`, the
   `level:role` pairs) for each tenant that has any.
3. Log `WARNING "no grant administers the tenant"` for each tenant where `administered` is
   false, with no grant at all included (RISK-2).

`_run_at_startup` calls it right after `migrate_shared`. It never raises.

### D-6

`Collaboration.roles_held(iri) -> frozenset[str]` returns `self._rules.roles(self._caller,
self._access, iri)` after `self._rules.require(..., Action.READ)`. It does **not** require the
discussion module: transitions use the same roles, and a schema without discussion still has
them. A caller who may not read gets the access refusal that `thread` gives after its module
check.

### D-7

The header (DEC-6). `negotiation.py` gains `HELD_ROLES = "Held-Roles"` and
`held_roles_value(roles) -> str` (sorted, comma-separated). The read route sets it beside
`Allowed-Actions`, from `self._kit.rules.roles(caller, access, iri)`. `openapi.py` declares it
wherever `_with_allowed_actions` applies, through one helper that adds both.

## Algorithm / approach

### Stage 1, #307: grants in a migration; the start-up report

Tests first:

- `tests/unit/migrations/test_grant_roles.py` (new): load checks and request building.
- `tests/unit/tenancy/test_migrate_dataset.py`: in-memory, on an rdflib `Dataset` with the
  toolkit chain, the toy's roles and two access records.
- `tests/unit/tenancy/test_grant_report.py` (new): the report, with `caplog`.

| T | Case |
|---|---|
| T1 (#307) | `rename {reader: member}`: every grant naming `reader` names `member`, the part IRIs are unchanged, and the record decodes as a `TenantAccess`. |
| T2 (#307) | `drop [guest]`: the grants naming `guest` are gone with their parts' triples, and the others are untouched. |
| T3 (RISK-1) | One assignee holds `reader` and `member` on one target, and `rename {reader: member}` leaves one `member` grant; the record decodes (no duplicate key). |
| T3b (RISK-1) | Merge: one assignee holds `reader` and `viewer` on one target, and `rename {reader: member, viewer: member}` leaves one `member` grant; the record decodes. |
| T3c | Levels: a tenant-level and an aggregate-level grant naming `reader` are both renamed. |
| T4 | Running the migration twice changes nothing the second time (the stamp has moved). |
| T5 | A tenant database and `migrate_dataset` get no grant operations: the request text has none. |
| T6 | The load checks: each case of D-2 refused, naming the file. A file with only `grant_roles` loads, and its request parses to the expected count. |
| T7 | The tokens rotate: the access record's version changes after a grant-only migration. |
| T8 (RISK-2, RISK-3) | The report. A record naming `reader`, which the definitions lack, logs one warning naming the tenant and `tenant:reader`. A record whose grants give no `administer` (or no grants at all) logs "no grant administers the tenant". Clean records log nothing. |
| T8b | The report's failures: with the store down, or one record that does not decode, it logs `ERROR` and start-up continues. |
| T9 | `validate_grants` is unchanged: the same `UnknownRole`, with the same message, for the same input (its existing tests pass). |

Worked example (`howto/migrate.adoc`):

```yaml
# migrations/library/2.0.0-to-2.1.0.yaml, beside the renamed roles file
schema_id: https://example.org/library
from_version: 2.0.0
to_version: 2.1.0
description: reader becomes member; guest is retired
grant_roles:
  rename: {reader: member}
  drop: [guest]
```

The how-to gives the order: ship the roles file and the migration in one release. At start-up the
migration runs first, then the report confirms that no tenant names an undefined role.

### Stage 2, #310: roles held

Tests first, in `tests/unit/collaboration/test_collaboration_discussion.py` (`roles_held`) and
`tests/unit/api/test_router.py` (the header):

| T | Case |
|---|---|
| T10 (#310) | `roles_held(iri)` equals the roles that decide the audience: a comment with audience R is seen if and only if R ∩ `roles_held` ≠ ∅. Property test over the toy's grants, aggregate grants and token roles. |
| T11 | A caller who may not read `iri` gets the access refusal. With a schema without the discussion module, `roles_held` still answers. |
| T12 | The aggregate GET carries `Held-Roles: editor,reader` (sorted), and an empty value when none is held. |
| T13 | The OpenAPI declares `Held-Roles` on every response that declares `Allowed-Actions`, at both sites (`openapi.py` l.324, l.485). |

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Ask the consumer to write SPARQL over `rp:role` | `grant_roles` in the file | DEC-1: no dependence on internals |
| Rename grants in Python at start-up | Operations in the stamped request | Idempotent by stamp; one atomic request |
| Build the operations by string concatenation | Templates filled with `term()` | Injection; the module's rule |
| Recompute roles for the header | `rules.roles` | One rule (the issue's point) |
| Stop start-up on stale grants | Warn (DEC-5) | Owner's choice |

## Error matrix

| # | Input | Detection | Response | Fallback |
|---|---|---|---|---|
| E1 | rename `a→b`, with no `b` grant beside it | operation 2 | renamed in place | n/a |
| E2 | rename `a→b`, with the same assignee and target already holding `b` | operation 1 | the `a` grant is deleted; one `b` remains | n/a |
| E3 | drop `x` | the drop operation | the grant part and its link deleted | n/a |
| E4 | a name in both rename and drop, a chain, an empty name, a self-rename | `_grant_problem` at load | `InvalidMigration` naming the file; start-up stops (shared database) | fix the file |
| E5 | a migration already applied | the stamp guard | no change | n/a |
| E6 | a grant-only migration on a tenant database | `grants=False` | only the stamp moves | n/a |
| E7 | the roles file lacks the new name (deployed apart) | the report after the migration | a warning naming the tenant and the role | ship both (RISK-3) |
| E8 | a tenant whose grants give no `administer` (none at all included) | the report, `administered` | the warning "no grant administers the tenant" | an operator grants a role |
| E9 | the store fails, or a record does not decode, during the report | `PersistenceError` / `StoredDataInvalid` | logged at ERROR; the report is skipped; start-up continues | fix the record |
| E13 | a merge `{reader: member, viewer: member}`, the assignee holding both | per-rename op1 → op2 order | one `member` grant | n/a |
| E14 | a dropped name that is also a rename target | `_grant_problem` | `InvalidMigration` naming the file | fix the file |
| E15 | `reader` defined at two levels and renamed | none (by design) | both levels renamed | a separate role name per level (how-to) |
| E10 | `roles_held` without read access | `rules.require` | `Forbidden` / `NotFound`, as `thread` | n/a |
| E11 | the caller holds no role | `rules.roles` empty | `Held-Roles:` (empty value) | n/a |
| E12 | a role name with a comma | the roles file's name pattern | cannot happen (names are checked at load); asserted by a test on `load_role_definitions` | n/a |

Idempotency: the grant operations are stamp-guarded, so a second sender changes nothing (E5).
The report and the header only read.

## Risks / Trade-offs

- **RISK-1 (a rename makes duplicates).** This is likely whenever roles are merged. Without
  care, the record would stop decoding. Mitigation: operation 1 runs first, rename by rename (D-4), proved by T3, T3b and E13.
- **RISK-2 (a drop locks a tenant out).** Possible. The tenant has no manager until an operator
  steps in. Mitigation: the report's "no grant administers the tenant" warning (T8), and a
  how-to line saying to rename rather than drop a role that administers.
- **RISK-3 (the roles file and the migration ship apart).**
  - Likely with a manual deploy. Grants and definitions disagree, and `PUT …/grants` is refused
    for those tenants.
  - Mitigation: the report names them (E7). The how-to's order says to ship both in one release.
- **RISK-4 (the header exposes role names).**
  - Certain: the caller sees its own role names, including token roles.
  - The impact is low: they are the caller's own, and the token already carries them.
  - Mitigation: documented in `user-manual/access.adoc`.

## Open Questions

None.

## Delivery decisions

D-8 to D-15 validated by the developer, 2026-11-25: all accepted.

### D-8

Stage 1 impact (lead, at stage start on `71aa56d2`): `migration_request` is HIGH, because the
generator's `lock_problems` reaches it through `load_migration`. D-3 only adds the keyword
`grants: bool = False`, so every existing caller builds the same request as before; T5 and the
unchanged migration tests show it. Taken by the lead, not escalated; shown for validation at the
end (R-0007).

### D-9

Develop moved after the PLAN was read: `Tenancy` now keeps `rules.with_iris(self._iris)`
(consumer-gap-fixes D-4). `report_grants` takes each record's tenant from
`tenancy.tenant_of(record)`, under that IRI policy, and `_level` compares a grant's target with
it, so the report and `set_grants` agree on which roles are undefined. `_run_at_startup` passes
`kit.rules`; no `with_iris` call is needed.

### D-10

The report's warning carries its `level:role` pairs in a new `LogContext` slot,
`undefined_roles` (`rp.grants.undefined_roles`, multivalued) in `rp_core_services.yaml`, then
`make generate` (P-0010, P-0011). D-5 named the attribute but no slot existed for it.

### D-11

Stage 1 review (one pass, L2+L3; `result: stage=1 role=reviewer lens=L2+L3 findings=5 accepted=2`).
Two Warnings re-labelled Critical and fixed, in one fixer pass:

- **R1-W1** (`migration_runner.py`): no test runs `grant_roles` through `migrate_shared`, though the
  spec scenarios say "WHEN start-up migrates the system database". Re-labelled because #307's
  deliverable could silently become a stamp move with every gate green. Fix: a runner test on the
  fake store: the system database's grants change; the application and a tenant database get only
  the stamp.
- **R1-W2** (`tests/integration/store/`): no container test sends a grant operation, though stage 1
  runs `make test-containers` because migrations run on Fuseki. Re-labelled because the gate the
  developer asked for did not test what it was asked for. Fix: one Fuseki test of the merge (T3b)
  and the drop (T2).

Under the floor:

- R1-W3: T8b stubs `Tenancy` with a `SimpleNamespace`; the wrapping of an undecodable record as
  `StoredDataInvalid` is `Tenancy`'s, tested with it.
- R1-S4: the T3b negative control catches any `ValueError`, not only the duplicate grant key.
- R1-S5: no service-level test that a stale role is named at start-up and a request is served after.

### D-12

Stage 2 impact (lead, at stage start on `16030e17`): `_with_allowed_actions` is HIGH, through
`install_service` and `build_router`; its direct callers are `read_root` and `read` in
`openapi.py`. D-7 only declares a second header beside `Allowed-Actions`, through one helper, so
no existing response loses a header; T13 checks both sites. Taken by the lead, not escalated;
shown for validation at the end (R-0007). `AccessRules.roles` (callers `Discussion.thread`,
`Transitions._edge`) and `Collaboration` are LOW.

### D-13

E12 assumed a role name could not hold a comma because names are checked at load. They were
not: `load_role_definitions` accepted `"a,b"`, as the generated `RoleDefinition.role` had no
pattern, so `Held-Roles` could be ambiguous. Developer's decision (2026-11-25, one question
round, P-0019): a comma-free `pattern` on the role name in the `rp_access` LinkML schema, then
`make generate`; the E12 test asserts that a roles file naming `a,b` is refused at load. Role
names come from UML class names, so no known roles file is affected.

Builder decisions in stage 2, kept: `_with_allowed_actions` renamed `_with_caller_headers`, as it
now declares both headers; `Held-Roles` joins with `,` (the spec), `Allowed-Actions` keeps `, `;
the tenant read carries `Held-Roles` too, since it is the same route.

### D-14

Stage 2 review (one pass, L2+L3; `result: stage=2 role=reviewer lens=L2+L3 findings=3 accepted=1`).

- **R2-W1, re-labelled Critical and fixed:** a migration's `grant_roles.rename` could name a
  comma in its target (`{reader: "a,b"}`), rewriting stored grants to a name `Held-Roles` cannot
  carry; start-up only warns (DEC-5). It defeats D-13 through stage 1's path, and the user manual
  says the opposite. Fix: the same comma-free `pattern` on `RoleRename.to_role` (`slot_usage`),
  `make generate`, and an E12 row in `test_grant_roles.py` refusing such a file at load.

Under the floor:

- R2-S1: T12 checks `Held-Roles` on the book read only; the tenant read shares `DocumentApi.read`
  and T13 covers its OpenAPI declaration.
- R2-S2: T11's "answers without the discussion module" assert sits in a test named for the
  lookup error.

### D-15

The acceptance demo (2026-11-25, accepted by the developer) showed the start-up warning listing
`tenant:member` once per stale grant. Developer's decision: `undefined_roles` keeps the first
occurrence of each `(level, role)` pair, in the grants' order, so the warning names each role
once, as the requirement reads. `validate_grants` raises on the first pair and is unchanged.
