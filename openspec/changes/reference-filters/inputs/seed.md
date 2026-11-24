# Seed (secondary, never groomed): issue #308, verbatim

**Listing filter through a reference (e.g. has_source.has_source_version=<iri>)**

## Summary

The generic listing filters only on a root's own slots (`<slot>=<value>`, `<slot>~=<text>`). It cannot filter through a reference, e.g. list the aggregates whose referenced aggregate has a given value.

## Context

Consumer: MWB2, change `v2-06-conceptual-mapping` (rdf-persistence v0.9.0). The CM list must be filterable by source version: a `ConceptualMapping` points to an element (`has_source`), and the element holds its versions (`has_source_version`). The filter needed is `has_source.has_source_version=<version IRI>`.

## Expected behaviour / proposed capability

A listing filter through one or more references, for example `?has_source.has_source_version=<iri>`, applying the caller's access to every aggregate it crosses, paged like any listing.

## Why it belongs in rdf-persistence

Filtering a root by a property of what it references is common in model-driven applications. A consumer composing two listings itself cannot page or sort the result correctly.

## Impact on the consumer

MWB2 offers the source-version filter only once this lands (`v2-06-conceptual-mapping` finding T-1); it does not compose listings itself.

## The owner's framing (session 2026-11-24)

Backlog row 17, MEDIUM, depending on `consumer-gap-fixes` stage 4. Build on its DEC-5, DEC-6
and design D-1 to D-3 (the absent filter, the Filter/Condition model, the one renderer
`condition_patterns`).
