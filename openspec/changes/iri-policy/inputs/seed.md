<!-- SECONDARY INPUT: preserved, never groomed. The EPIC (../proposal.md) is the shaped truth. -->

# Seed: a configurable IRI policy, independent of API paths

## Seed text

GitHub issue #26 and its comment of 2026-11-07, copied in `issue.md`. The consumer (MWB2, ADR-013)
has a persistent URI policy: short opaque lowercase ids, flat object IRIs (not nested under their
owner), a deployment segment on deployment-local things only, and IRIs that do not change when the
API changes. The comment splits each tenant into a portable tenant root and a deployment-local
access record, so a tenant database can later be attached to another deployment.

## What was read

- `rdf_persistence/domain/iris.py`: every IRI and resource name the toolkit derives.
- Minting callers: `services/tenancy.py` (tenant, access record, resource names),
  `services/aggregates.py` (aggregates), `services/documents.py` and `services/mapper.py`
  (`new_part`, owned parts), `services/session.py` (loaded graphs).
- Checking callers: `services/session.py` (`_graph`, `_check_commit`), `services/access.py`
  (`is_aggregate_iri`), `entrypoints/kit.py` and `entrypoints/auth.py` (path id → IRI),
  `entrypoints/router.py` (`_last_segment`: IRI → path id).
- Nesting assumptions not named in the issue: `services/listing.py:_owner` walks up the IRI path to
  find a subject's root; `services/documents.py:_inside` treats "below the root's IRI" as "a part".
- `adapters/jwks.py` (principal IRI), `services/sweep.py` (resource-name prefix),
  `entrypoints/problems.py` (problem types under `base`).
- `rdf_persistence/model/service/rp_service.yaml` (`ServiceSettings`),
  `rdf_persistence/model/rp_annotations.yaml` (`rp_path`).
- Specs: `rp-aggregate-store`, `rp-tenancy`, `rp-identity`, `rp-service-api`.
- Docs: `howto/adopt.adoc` (steps 3 and the tenancy section), `architecture/index.adoc`.

## Questions and answers (developer, 2026-11-08)

1. **What guards against changing the policy after data is stored?** Options: record the policy in
   the system database and refuse to start on a different one (recommended), or document only.
   **Answer: record and refuse.**
2. **One EPIC or several?** Options: one EPIC in two stages (recommended), two EPICs, one EPIC in
   one PR. **Answer: one EPIC, two stages.**

## Leader's choices while shaping (recorded, not asked; the developer may overturn any)

- Each kind of IRI has its own template (tenant, access record, meta graph, registry graph,
  aggregate root, owned part, loaded graph, principal); the defaults are today's shapes, which need
  the extra variables `{tenant}`, `{root}`, `{rp_path}` and `{issuer}`.
- Problem types and the JSON-LD context stay under `ServiceSettings.base`; with `{deployment}` a
  separate setting, `base` is already deployment-independent (the issue's `vocabulary_base`
  becomes unnecessary).
- A loaded graph fills `{type}` with the fixed word `content` (today's segment).
- Object ids (13 characters, about 67 bits) are not checked for clashes; tenant ids (7 characters,
  about 36 bits) are, and re-drawn.
- Ownership of parts and loaded graphs comes from the aggregate's graph and the registry, not from
  IRI nesting, under every policy.
- The toolkit principal `{base}toolkit` and the recorded policy beside it are not templated
  (proposal DEC-9).

## Clarity-gate round 1 (independent reviewer, 2026-11-08)

Scored 6/10. Findings accepted and folded into the PLAN: the annotation belongs to the
`RpAnnotation` enum in `rp_core.yaml`; the access record has no `tenant` slot (the tenant is read
back by matching the access template instead, so stored records need no migration); the listing
query returns no graphs; a loaded graph is unregistered until its commit; the part rule and the
`{type}` restriction were undefined; the tenant-id clash check could miss an orphan dataset;
`fake_session`, `JwksTokenVerifier` and `access._validate_ends` were not reached; the spec named an
"object template" the design splits into three.

## Clarity-gate round 2 (same reviewer, 2026-11-08)

Scored 8/10; five text gaps, all fixed: the loaded-graph `{type}` in the spec, where the flat part
rule runs (`Aggregates.replace` after `get_graph`), the nested rule kept for the default policy (no
behaviour change without a policy), `is_aggregate` keeping the tenant root and access record, and
the orphan-dataset re-draw in the spec.

## Clarity-gate round 3 (same reviewer, 2026-11-08)

**9/10, passes.** One minor gap fixed after scoring: `parse` returns the subjects the body names,
so `Aggregates.replace` can tell them from parts minted in the request (design PD-7).
