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

## As built

Reconciled at the close of the change, in its one PR before it merges (P-0004). Delivery
decisions are design D-1 to D-10.

| Stage | PR | As shaped | As built |
|---|---|---|---|
| 1 the contains filter | this PR | DEC-1, DEC-2, PD-1 to PD-12 | Delivered as shaped: `GET /<path>?<slot>~=<text>` and `find(cls, slot=Contains(text=…))` match a case-insensitive substring of a string slot through `FILTER EXISTS { … CONTAINS(LCASE(STR(…)), LCASE("text")) }`, the text only through `term()`; a non-string slot or an empty text is 400 `bad-query`; one renderer of conditions (`condition_patterns`) serves the listing, `Session.matches` and the commit guard; the OpenAPI shows `<slot>~` per text slot. Built differently: the EPIC's illustrative `Contains("dune")` is `Contains(text="dune")`, a generated model (PD-7, the owner's answer). Added beyond the shape: a Fuseki probe that a matching value in another graph does not make an aggregate match (D-7; RISK-2 did not materialise); the public-surface snapshot refreshed whole, correcting 79 stale module paths (D-8). TC-05's last row corrected (D-5). Tasks run in three parallel waves of builders (D-3, D-4). The stage's `make check-all` exposed a pre-existing overflow on a huge `offset` (a 500 on the in-memory store); `offset` is now bounded at 2^53 − 1 in the model, a 400 beyond (D-9). The one L2+L3 review pass found 8 findings: the red gate (fixed by D-9) and the "listed once" scenario's test not discriminating, re-labelled Critical and fixed with an `offset=3` row (D-10); 6 under the floor. Delivery decisions D-1 to D-10 |

### What Changes, Capabilities and Impact as delivered

- **What Changes** holds as written. Also changed: the LinkML model of listings (`Filter` and
  `Condition` gain `contains`; a new class `Contains`), `holds_text` beside `holds_iri`, and
  `Session.matches` and the commit guard, which now render conditions as listings do.
- **Capabilities** as shaped: `rp-service-api` adds the requirement "Listings filter by a
  case-insensitive substring"; `rp-aggregate-store` modifies "A session finds aggregates by slot
  values". The spec deltas are true of the code; every delta scenario has its test in
  `tests/audit/scenario-map.csv`.
- **Impact** as shaped, plus `reference/http-api.adoc`, the generated public-API partial and the
  public surface (149 names, `Contains` added), and one change beside the shape: a listing's
  `offset` above 2^53 − 1 is now 400 `bad-query` (D-9). Nothing the shape promised is missing.
