<!-- Parents: issue #203 (inputs/seed.md); openspec/specs/rp-service-api (listings);
     docs/modules/ROOT/pages/architecture/api.adoc (equality filters). Serves: MWB2
     v2-05-target-and-fragments task 4.4 (D-12). Seeds: inputs/seed.md. Consumer triage in
     ../uml-to-linkml/inputs/qa.md. -->

# EPIC: A case-insensitive "contains" filter on listings

## Appetite

**SMALL.** One more filter operator on the existing listing query and on `Session.find`.

## Why

Listings filter by equality only. Searching a catalogue by part of a title needs a substring
match, and filtering in memory after paging is wrong. The consumer's search box needs this before
`v2-05`'s search task.

## Solution outline

`GET /books?title~=dune` and `session.find(Book, title=Contains("dune"))` match case-insensitively
on a substring of a string-ranged slot. The filter combines with the other filters, and paging and
totals are unchanged. A non-string slot answers `400 bad-query`. The OpenAPI shows one extra query
parameter per string slot.

## Key decisions

- **DEC-1:** SPARQL `CONTAINS(LCASE(str(?v)), LCASE(?q))` inside the existing listing query. The
  user's text is bound as a literal, never spliced into the query. Rejected: a full-text index,
  which is store-specific.
- **DEC-2:** `~=` is the query-string operator, as the issue proposes. Rejected: `title__contains`.

## Rabbit-holes

- Speed on large tenants: it is a scan, accepted for now. The upgrade path is a store full-text
  index, behind the same operator, in a later change.
- Unicode case folding beyond `LCASE` is left to the store.

## No-gos

- No regex, prefix or fuzzy operators. No full-text ranking.
- No contains filter on non-string slots.

---

## What Changes

- Listing query builder and `Session.find`: the `Contains` operator.
- Generated API: `<slot>~` parameters on string slots; `400 bad-query` on others.

## Capabilities

### Modified Capabilities

- `rp-service-api`: listings support a case-insensitive contains filter.
- `rp-aggregate-store`: `Session.find` supports `Contains`.

## Impact

Listing adapter (SPARQL), generated routes and OpenAPI, the TypeScript types, `api.adoc`.
