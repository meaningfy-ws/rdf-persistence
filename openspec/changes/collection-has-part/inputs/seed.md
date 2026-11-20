<!-- Secondary input, never groomed: GitHub issue #199 (meaningfy-ws/rdf-persistence), fetched 2026-11-20. The EPIC (../proposal.md) supersedes it. -->

# #199 Reference collections with an application-chosen membership property (e.g. dct:hasPart)

## Summary

A reference collection always states its members with `prov:hadMember` (`rp_collections.yaml`,
slot `had_member`) and is typed `prov:Collection`. An application whose vocabulary policy keeps PROV
for provenance only, and models part-whole membership with `dct:hasPart`, cannot use the toolkit's
collections without either breaking that policy or rebuilding collections itself.

## Context

- Consumer: Mapping Workbench 2, change `domain-model-v2` (decision S6-4, confirmed by the product
  owner on 2026-11-20: "keep prov for provenance information only, and use dct and skos for domain
  modelling") and `v2-02-model-from-ea`, `v2-03-project-and-resources`.
- Toolkit read at `origin/develop` `c671fefb`. Related: #198 (nesting collections).

## Current behaviour

```yaml
ReferenceCollection: {class_uri: prov:Collection, mixin: true, slots: [member_class, had_member, membership_rule]}
had_member: {slot_uri: prov:hadMember, range: uri, multivalued: true}
```

`members`, `collections_of`, `delete_cascade`, `referrers` and the access counting all read
`prov:hadMember`. LinkML does not let a consumer change a slot's `slot_uri` through `slot_usage`.

## Proposed capability

The membership property (and optionally the collection's RDF type) is chosen per collection class
by the application, defaulting to today's PROV terms:

```yaml
TestDataCollection:
  mixins: [AggregateRoot, ReferenceCollection]
  annotations:
    rp_path: test-data-collections
    member_property: dct:hasPart      # default prov:hadMember
```

The generated class writes and reads members through `member_property`; every collaboration service
(members, collections_of, delete_cascade, referrers, rules) uses the property of the collection's
class. The schema lock records the choice, so changing it later is a migration.

## Why it belongs in rdf-persistence

Collections, their services and access counting are the toolkit's; which vocabulary an application
uses for part-whole is the application's modelling policy, and DCAT/DCT-based applications commonly
use `dct:hasPart`.

## Acceptance

- **Given** a collection class without `member_property`, **then** members are stated with
  `prov:hadMember` as today.
- **Given** a collection class with `member_property: dct:hasPart`, **when** a collection is saved
  with two members, **then** its graph states `dct:hasPart` twice and no `prov:hadMember`, and
  `members`, `collections_of`, `delete_cascade` and `referrers` find them.
- **Given** two collection classes with different member properties in one schema, **then** each
  service uses the property of the collection's own class.

## Impact on the consumer

The consumer's collections (test data, SPARQL queries, SHACL shapes, vocabulary mappings,
ontologies) wait for this before they are generated with the toolkit's collection mixin; it builds
no collection mechanism of its own meanwhile.


## Comments

