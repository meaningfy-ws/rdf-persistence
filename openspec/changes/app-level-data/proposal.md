<!-- Parents: openspec/specs/rp-tenancy (the system database); the developer's need in
     inputs/seed.md. -->

# EPIC: Application-level data beside the tenants

> Candidate EPIC, shaped 2026-11-10. Not planned: the PLAN waits for the developer's answers to the
> open questions below.

**Golden-thread parent:** capability `rp-tenancy`: the system database holds only access records.

## Appetite

**MEDIUM.** One new capability: the application's own aggregates, outside any tenant, through the
same session, mapper and generic routes; tenancy and access touched.

## Why

An application that governs projects also has data of its own (settings, catalogues, templates
shared by all projects). The toolkit offers no place for it: the system database holds only access
records, and every session belongs to a tenant.

## Solution outline

The application stores its own aggregates in an application-level space, with the same models,
versions and access checks as tenant data, and its own roles.

## Key decisions

None yet.

## Open questions

- Q-1: The system database itself, or a separate application database?
- Q-2: Who may read and write it: global roles from the token only, or grants too?
- Q-3: Generic routes for it (e.g. `/app/{rp_path}`), or Python only?
- Q-4: Can tenant data refer to application data by IRI?

## Rabbit-holes

- Keeping the access records out of reach of the application's own writes.

## No-gos

- Moving the access records out of the system database.

---

## What Changes

- An application-level session and its storage; access rules for it.

## Capabilities

### Modified Capabilities

- `rp-tenancy`: application-level data (ADDED requirement).

## Impact

- New public operations; the IRI policy gains an application-level template.
