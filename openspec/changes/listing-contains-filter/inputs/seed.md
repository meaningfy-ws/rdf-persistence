<!-- Secondary input, never groomed: GitHub issue #203 (meaningfy-ws/rdf-persistence), fetched 2026-11-20. The EPIC (../proposal.md) supersedes it. -->

# #203 Listings: a case-insensitive contains filter on string slots

## Summary
Listings: a case-insensitive "contains" filter on string slots.

## Context
Consumer: MWB2 change `v2-05-target-and-fragments` (catalogue search, DEC-15); toolkit locked at `c671fefb` (v0.7.0).

## What is missing
Generic listings and `Session.find` support equality filters only (`architecture/api.adoc`). Searching a catalogue by part of a text slot needs a substring match.

## Proposed capability
`GET /books?title~=dune` and `session.find(Book, title=Contains("dune"))`: a case-insensitive substring match on a string-ranged slot, combinable with other filters; paging and totals unchanged. A non-string slot answers 400 `bad-query`. The OpenAPI shows one extra query parameter per string slot.

## Why it belongs in rdf-persistence
Text search on listings is needed by any application on the generic API; filtering in memory after paging is wrong, and a consumer SPARQL query is a workaround.

## Acceptance
- Given books "Dune", "Children of Dune" and "Emma", When listing `title~=DUNE`, Then two books, total 2.
- Given `year~=19`, Then 400 `bad-query`.
- Given `title~=dune&author=…`, Then both filters apply.

## Impact on the consumer
MWB2's catalogue search waits.


## Comments

