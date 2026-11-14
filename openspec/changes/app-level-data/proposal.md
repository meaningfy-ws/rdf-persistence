<!-- Parents: openspec/specs/rp-tenancy (the system database holds only access records and the IRI
     policy record), rp-access (global roles from the token, role level `system`), rp-iri-policy;
     the developer's need in inputs/seed.md. -->

# EPIC: Application-level data beside the tenants

> Shaped 2026-11-10; open questions answered by the leader on 2026-11-12 (inputs/seed.md, "Leader's
> recommendations"); the developer may overrule any DEC marked "leader's choice". Second of the four
> tenancy candidates. Not planned: the PLAN is derived at the start of its epic session.

**Golden-thread parent:** capability `rp-tenancy` (the system database holds only access records and
the IRI policy record), `rp-access` (global roles from the token at role level `system`), and the
developer's need (2026-11-10): "an application has one database for application metadata and
control ... we cannot distinguish between app-project, and space within app governance".

## Appetite

**MEDIUM.** One new capability: one application space (a database of its own) for aggregates the
schema marks as application-level, through the same session, mapper and versioned writes, with
access from global roles. IRI policy and access touched; no files, no routes, no grants.

## Why

An application that governs projects also has data of its own: settings, catalogues, templates
shared by every project. The toolkit offers no place for it: every session belongs to a tenant, and
the system database holds access records that the application's writes must never reach. Today a
consumer fakes it with a "settings" tenant, which then shows up among the projects.

## Solution outline

A schema marks a class `database: application` (the annotation `TenantAccess` already uses with
`system`). Its aggregates live in one application database, `{prefix}-app`, created at start-up when
the schema has such a class. `kit.application_session(principal)` opens the same `Session` on it, so
reads, versioned writes, `find`, `UnitOfWork` and loaded graphs work unchanged. Who may do what is
decided from the caller's global roles alone.

```yaml
classes:
  Template:                      # shared by every project
    mixins: [AggregateRoot]
    annotations: {database: application, rp_path: templates}
```

```python
authorised = await kit.require_application(authorization, Action.MODIFY)   # global roles only
async with kit.application_session(authorised.principal.id) as session:
    work = UnitOfWork(session, mapper)
    work.add(Template(id=..., label="Default report"))
    await work.commit()
```

## Key decisions

- **DEC-1** (Q-1; leader's choice, 2026-11-12, the developer may overrule): a **separate application
  database** `{prefix}-app`, never the system database. Reason: the application's writes then cannot
  reach the access records by construction (the rabbit-hole of the first shape), the start-up sweep
  ignores it (no `-t-` in its name), and the system database keeps its one job. Rejected: the system
  database (every write path would need a guard against touching records).
- **DEC-2** (Q-2; leader's choice): access to application data is decided from the caller's **global
  roles in the token** only, through the role definitions at level `system` and the same
  `AccessRules`; Prohibitions and grants do not apply. Reason: no record exists to hold grants
  outside a tenant, and application data is administered by application-wide roles. Rejected: grants
  on the application space (needs an application access record and its routes; a later change).
- **DEC-3** (Q-3; leader's choice): **Python only**: `ServiceKit.require_application` and
  `ServiceKit.application_session`; the consumer routes them. Reason: the same choice as the
  collaboration EPIC and `loaded_graphs`; the generic router stays tenant-shaped. Rejected: a generic
  `/app/{rp_path}` router (doubles the router's paths, OpenAPI and tests; a later change if asked).
- **DEC-4** (Q-4; leader's choice): tenant data **may refer** to application aggregates by IRI, and
  application data to tenant aggregates, as plain IRI values: no integrity check, no read across
  databases, no reverse references across the boundary. A tenant dump keeps such IRIs unchanged
  (they carry no tenant id). Reason: references are already plain IRIs inside a tenant.
- **DEC-5** (IRIs; leader's choice): the IRI policy gains an `application` template, default
  `{base}app`; the application space is minted like a tenant whose IRI is the application IRI and
  whose `{tenant_id}` is the reserved word `app`, so its aggregates, parts, `meta`, `registry` and
  loaded graphs follow the existing templates. `app` becomes reserved for tenant ids; building `Iris`
  refuses a policy whose application IRI reads as a tenant IRI. A recorded policy without the field
  compares as the default, so existing deployments start unchanged. Rejected: a second set of
  templates for application objects (twice the policy surface).
- **DEC-6**: a class is application-level only through the schema annotation; the session on the
  application database refuses tenant classes, and a tenant session refuses application classes,
  with `InvalidIri` before anything is sent (`rp-iri-policy` "Only IRIs the policy would mint").
  Generation fails for an application class that is the tenant root or owned by a tenant class.
  LinkML stays the single source (D-13, PD-24).

## Rabbit-holes

- **The policy record.** Adding a field to the recorded effective policy must not make every existing
  deployment fail its start-up check (DEC-5: absent = default).
- **Several application spaces.** One per deployment; a second one is a tenant.
- **The toolkit principal** writes nothing in the application database except what the consumer asks.

## No-gos

- Moving the access records out of the system database.
- Files (a bucket) for application data; the application's loaded graphs are allowed, its blobs not.
- Grants, prohibitions or per-aggregate permissions on application data.
- Generic HTTP routes or OpenAPI paths for application data.
- A live sweep or a dump of the application database (`tenant-dump-restore` covers tenants only).
- Queries that join application and tenant data.

---

## What Changes

- `rdf_persistence/model/`: the `application` template in the IRI policy; the `database:
  application` annotation documented; regenerated code.
- `rdf_persistence/domain/iris.py`: the application IRI, `app` reserved, the new policy checks.
- `rdf_persistence/services/`: the application database at start-up, `application_session`, the class
  checks of DEC-6, the access decision of DEC-2.
- `rdf_persistence/entrypoints/kit.py`: `require_application`, `application_session`.
- `rdf_persistence/generation/`: the DEC-6 generation check.
- `tests/fixtures/library/`: one application-level class (a shared template of the toy library).
- Docs: a how-to and a `questions.adoc` entry ("Where does data that belongs to no project go?").

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rp-tenancy`: application-level data outside every tenant (ADDED requirement).
- `rp-access`: application data is decided by global roles (ADDED requirement).
- `rp-iri-policy`: the application space's IRIs (ADDED requirement).

## Impact

- New public operations; a new policy field (backwards compatible); one more database per
  deployment whose schema declares an application class.
- `schema-migrations` must migrate the application database as well as each tenant;
  `aggregate-events` must emit for it (noted in both).

## As built (2026-11-14)

Delivered in one stage, one PR into `develop`; the solution outline and every DEC held. Where the
result differs from the text above, or adds to it (each is a recorded decision in
[design.md](design.md), and the spec deltas say the same):

| Above | As built | Decision |
|---|---|---|
| The example: `Template(id=...)`, `authorised.principal.id` | The kit mints the IRI, `kit.application_iri(Template)`; `Authorised.principal` is the principal's IRI, a `str`, so the session is `kit.application_session(authorised.principal)` | PD-9, PD-10 |
| DEC-3: two kit operations | Three: `require_application`, `application_iri`, `application_session`; and `Tenancy.ensure_application_database()`, which `install_service` calls at start-up and a consumer with its own start-up calls once | PD-8, PD-10 |
| DEC-2: "from the caller's global roles … at level `system`" | Holds. Its consequence, not said above: a role at level `system` also permits its actions in every tenant, so an application editor can edit every tenant, and a system-level reader that already exists can read application data. A role for application data only needs a new role level | PD-9, RISK-1 |
| DEC-2: "the same `AccessRules`" | The same class, a method of its own, `require_application`: it answers `Forbidden`, never `NotFound`, and reads no grant. `Authorised.caller_access` is filled with the application IRI, state `active`, no grants | PD-9 |
| DEC-5: "minted like a tenant whose IRI is the application IRI" | Minted and matched like one, but the application IRI never answers as a tenant: `tenant_id_of`, `tenant("app")`, `resource_name` and `tenant_of_access` refuse it, so dump, restore and the access lookup cannot take it for one | PD-3 |
| DEC-5: "refuses a policy whose application IRI reads as a tenant IRI" | Also refused when `Iris` is built: an application IRI outside the base or on the toolkit's own IRI; application access, meta or registry IRIs that coincide; and templates under which an aggregate, part or loaded graph of the application reads as a tenant, or a tenant as one of its aggregates (found by the adversarial tests) | PD-3, D-4 |
| DEC-5: "a recorded policy without the field compares as the default" | Holds, and so the application template is fixed from the first start: a deployment that already has a policy record can use only the default `{base}app`. A dump written before this change is read the same way and still restores | PD-1, PD-11, RISK-6 |
| DEC-6: "application-level only through the schema annotation" | The annotation is read along the `is_a` chain, so a subclass of an application class is one; a mixin's annotation does not count and generation refuses it | PD-4, PD-5 |
| DEC-6: the sessions refuse the other space's classes | By the root's `rdf:type`, on every write, because an IRI policy may write no class into an IRI. A tenant session refuses application classes; the application session takes application classes only, so an untyped root is refused there too. Reads are not checked: nothing of the other space is stored | PD-6 |
| DEC-6 (not said) | The application has no root object and no access record, so its session refuses the application IRI itself and its access IRI as an aggregate IRI; a restore refuses a dump that holds an object typed as an application class (review of the PR) | D-6 a, b |
| DEC-6: generation fails for the tenant root or a class owned by a tenant class | Also for an application class that is not an aggregate root, is a stored file (no bucket), or shares its class IRI with a root of another database | PD-5 |
| Rabbit-holes (not said) | A class moved from `tenant` to `application` leaves its stored aggregates in the tenant databases: still readable by IRI and removable there, no longer replaceable, findable or served. The how-to gives the three steps of the move; there is no move tool | RISK-7 |
| What Changes: "the access decision of DEC-2" in `services/` | As listed, plus `services/schema_structure.py` (`database_of`, `served_roots` by database, `root_class_iris`), `services/listing.py` (listings per database) and `services/tenant_dump.py` (old manifests) | PD-4, PD-11 |

Not built, as the No-gos say: no routes or OpenAPI paths, no grants, no bucket, no sweep or dump of
the application database, no cross-database read. An older toolkit version cannot read the policy
record or a dump written by this one (RISK-2).
