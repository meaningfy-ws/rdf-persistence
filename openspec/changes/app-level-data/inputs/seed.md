# Seed (secondary; never groomed)

Raised while shaping `tenant-root-loads` (see its inputs/seed.md):

> "an application has one database for application metadata and control, but then it has other
> databases under its governance and each database represents a project ... we cannot distinguish
> between app-project, and space within app governance, which includes also other
> databases/triplestores ... we shall be able to simply provide a triplestore dump as nquads, for
> example, and then you load it into a new project and restore its state." (developer, 2026-11-10)

The developer chose to record this need as a candidate EPIC (2026-11-10).

## Leader's recommendations (2026-11-12)

The developer was away and had accepted recommendations by default; the leader answered each open
question. Each answer is a DEC in `../proposal.md` marked "leader's choice"; the developer may
overrule any of them.

- Q-1 (system database or a separate one) -> a separate application database `{prefix}-app`
  (DEC-1): the access records stay out of reach by construction.
- Q-2 (global roles or grants) -> global roles from the token only, through role definitions at
  level `system` (DEC-2); grants on application data are a later change.
- Q-3 (generic routes or Python) -> Python only: `require_application`, `application_session`
  (DEC-3).
- Q-4 (tenant data referring to application data) -> yes, as plain IRIs, no integrity, no
  cross-database reads (DEC-4).
- Added: IRIs from a new `application` template, default `{base}app`, `app` reserved as a tenant id
  (DEC-5); a class is application-level by the schema annotation `database: application` (DEC-6).

Order: second of the four. It needs nothing from the others; it names the "app versus project"
distinction the developer raised first; `tenant-stores` then only has to say that the application
and system databases stay on the default store.

## Test scenarios the EPIC must prove

- An application aggregate is stored, read, listed and replaced through an application session and
  never appears in a tenant's listing.
- Two replaces at the same version: the second is a conflict.
- A tenant class through the application session, and an application class through a tenant
  session, are refused with `InvalidIri` and nothing is written.
- A global role permitted at level `system` allows a modify; a tenant owner without it is
  `Forbidden`.
- No application session can write a graph of the system database (the access records are
  unchanged after any application write).
- The start-up sweep leaves the application database alone; a schema without application classes
  creates no application database.
- The default application IRI is `{base}app/...`; an existing deployment's recorded policy still
  passes the start-up check; `app` is never drawn as a tenant id.
- A tenant aggregate holding an application IRI keeps it through a dump and restore.
- On Fuseki: the toy library's shared template round-trips through an application session.
