<!-- Secondary input, never groomed: GitHub issue #197 (meaningfy-ws/rdf-persistence), fetched 2026-11-22, label `enhancement`, state OPEN, no comments. The EPIC (../proposal.md) supersedes it. -->

# #197 Mint provenance activity IRIs through the IRI policy

## Summary

Provenance activities are minted as `urn:uuid:{uuid}` (`rdf_persistence/provenance/services/provenance.py`,
`ID_PREFIX`, `new_activity_id`), outside the configured IRI policy. Every other IRI the toolkit mints
for a tenant (roots, parts, graphs) follows the policy; activities are the exception.

## Context

- Consumer: Mapping Workbench 2, change `v2-01-toolkit-upgrade` (upgrade from `6bf3471` to v0.7.0,
  `origin/develop` `c671fefb`), finding F-1 of its PLAN.
- The consumer's URI policy requires every IRI it stores to start with its base (portable project
  data). Since 0.3.0 every commit writes a `<tenant>/provenance` graph whose activities are
  `urn:uuid:` IRIs, so a tenant's data now holds IRIs outside the policy.

## Current behaviour

```python
from rdf_persistence import ...  # any commit through a session
# <tenant>/provenance now holds:  <urn:uuid:5f0c…> a prov:Activity ; prov:wasAssociatedWith <…> .
```

The IRI policy (`user-manual/iri-policy.adoc`) has templates for roots, parts and graphs but none for
activities, so a consumer cannot place them under its base.

## Expected behaviour / proposed capability

An `activity` template in the IRI policy, defaulting to today's form so nothing changes for existing
consumers:

```yaml
iri_policy:
  activity: "urn:uuid:{uuid}"          # default, as today
  # a consumer may choose:  "{base}{tenant}/activity/{id}"
```

`new_activity_id()` mints through the policy; `is_activity_id()` accepts what the policy mints. The
policy fingerprint includes the template, so a deployment refuses to start under a changed one
(as for the other templates).

## Why it belongs in rdf-persistence

Activities are written by the toolkit on every commit; only the toolkit can mint them. Any
application with a URI policy for portable data has the same need.

## Acceptance

- **Given** the default policy, **when** a commit writes its activity, **then** the activity IRI is
  `urn:uuid:` and a UUID (unchanged).
- **Given** a policy with `activity: "{base}{tenant}/activity/{id}"`, **when** a commit writes its
  activity, **then** the activity IRI starts with the base and the tenant, and transitions, comments
  and provenance reads still find it.
- **Given** a deployment started with one activity template, **when** it restarts with another,
  **then** it refuses to start, naming the field that changed.

## Impact on the consumer

Not blocking: the upgrade proceeds and the consumer's URI-policy check does not yet test the
provenance graph. The consumer's policy requirement stays as written; it is met once this lands.


## Comments

None (2026-11-22).
