# Q&A record (secondary, never groomed): shaping session 2026-11-24

Seeds: issue #308 (`seed.md`); the planned, undelivered `consumer-gap-fixes` (`proposal.md`
DEC-5, DEC-6; `design.md` D-1 to D-3). Code read on `origin/develop` at `f12e8675`:
`rdf_persistence/persistence/services/listing.py` (`list_request`, `listable_slots`,
`Listings._filtered`, `condition_patterns`, `listing_query`, `_MATCHING`),
`persistence/services/session.py` (`find`, `_filters`, `_filter`, `matches`, `_require_match`,
`MATCHES`, `_MATCH_GUARD`), `core/domain/sparql.py` (`match_patterns`, `contains_patterns`),
`access/services/access.py` (`hidden_graphs`), `iris/domain/layout.py` (`graph_iri`),
`schema/services/schema_structure.py` (`holds_iri`, `database_of`),
`api/entrypoints/openapi.py` (`_query_parameters`), the services model
`rp_persistence_services.yaml` (`Filter`, `Condition`), the toy `tests/fixtures/library/books.yaml`.

One round. The owner answered: **"accept all recommendations"**.

| # | Question | Answer | → |
|---|---|---|---|
| Q1 | How deep may a path go? | Up to 3 references, a fixed cap, `BadQuery` beyond | DEC-2 |
| Q2 | What may the last segment ask? | Equality and contains (`~=`) | DEC-3 |
| Q3 | `absent=` through a path? | Refused (`BadQuery`); a no-go for now | DEC-3, No-gos |
| Q4 | Several filters through one multivalued reference | Each matches independently (any target per filter); documented | DEC-4 |
| Q5 | A crossed aggregate the caller may not read (listing) | The hop does not match; the root leaves the page and `total`. `find` still ignores prohibitions (PD-6) | DEC-5 |
| Q6 | What a hop may cross | References to aggregate roots in the listing's own database only; owned parts, `uri` slots and the other database refused | DEC-2 |
| Q7 | Next segment under an abstract range | Only the range class's own listable slots | DEC-2 |
| Q8 | The path in `find` | The dotted name, as over HTTP: `find(Book, **{"sequel_of.label": "x"})` | DEC-6 |
| Q9 | OpenAPI | The syntax is described (operation description and `reference/http-api.adoc`); no parameter per path | DEC-7 |
| Q10 | No-gos | No sort through a reference, no reverse paths, no paths fed to keys, guards or `matches`, no correlated semantics, no change to existing filters | No-gos |
| Q11 | Scenarios | S1 to S9 as proposed (one hop, multivalued / abstract range, two hops, hidden target, refusals, contains, unchanged rendering, `find`, dangling reference) | design error matrix |
| Q12 | Risks | Base moves: mitigate (re-read the merged stage 4 at stage start). Query cost: accept (the cap bounds it). The consumer needs more later: accept (a follow-up issue) | RISK-1 to RISK-3 |
| Q13 | Delivery | One stage, one PR | DEC-8 |

Planner's additions after the round (not asked; reviewable in the PR): S10, a statement about the
referenced aggregate made in another aggregate's graph does not match (the listing has the same
guarantee for root slots); a path filter renders as `FILTER EXISTS`, so a multivalued reference
never duplicates a page row (design D-2).
