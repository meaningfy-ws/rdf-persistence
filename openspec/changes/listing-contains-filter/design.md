<!-- PLAN (design half) of listing-contains-filter. PLAN = this file + tasks.md.
     Facts read on docs/epics-consumer-needs at 4e8d1fe2. -->

> Derives from: EPIC `listing-contains-filter` (`proposal.md`, issue #203), DEC-1, DEC-2.

# Design: listing-contains-filter

## Context

A listing turns the query string into a `ListRequest` (`list_request`,
`rdf_persistence/persistence/services/listing.py:104`), then into a `ListPlan` of typed
`Condition`s (`Listings.plan`, `listing.py:246`), then into one `CONSTRUCT` (`listing_query`,
`listing.py:276`). The count and the page share the `_MATCHING` block (`listing.py:55-59`), where
`$patterns` is `match_patterns("root", condition_pairs(...))` (`core/domain/sparql.py:177`): one
`?root <p> <value> .` per equality, each value rendered by `term()`, the one escaping function
(PD-3 of the foundation). `Filter`, `ListRequest`, `Condition` and `ListPlan` are generated from
`rdf_persistence/model/technical/persistence/rp_persistence_services.yaml`.
`Session.find` (`persistence/services/session.py:1003`) builds `Filter`s with `_filters`
(`session.py:1664`) and pages through `Listings.plan`. The same conditions are rendered twice more:
`Session.matches` (`session.py:985`, template `MATCHES` at `:260`) and
`Transaction._require_match` (`session.py:1430`). The OpenAPI listing parameters are built at run
time by `AggregateOpenApi._query_parameters` (`api/entrypoints/openapi.py:419`), one `_filter`
(`:403`) per listable slot; the TypeScript of the API comes from `openapi-typescript`
(`make typecheck-openapi-ts`), the service types from `rp_service.ts` (generator step 6).

**The `~=` finding (verified with the repository's Starlette, `QueryParams(...).multi_items()`):**

| Query string | Arrives as |
|---|---|
| `title~=dune` | `("title~", "dune")` |
| `title%7E=Dune` | `("title~", "Dune")` |
| `title~=a=b` | `("title~", "a=b")` (split on the first `=`) |
| `title~` / `title~=` | `("title~", "")` |
| `title~=x%26y` | `("title~", "x&y")` |
| `title~=%22%7D%20.` | `("title~", '"} .')` |

So `~=` is not an operator the parser sees: it is a parameter **named** `<slot>~`. `~` is an
RFC 3986 unreserved character, so clients may send it raw or as `%7E`; both arrive the same.

## Goals / Non-Goals

**Goals**
- G-1: `GET /<rp_path>?<slot>~=<text>` and `session.find(cls, <slot>=Contains(text=…))` list the
  aggregates with a value of that string slot containing `text`, ignoring case (spec delta, all
  three scenarios).
- G-2: the page and `total` stay exact: no aggregate counted or listed twice, hidden graphs left
  out of both.
- G-3: the user's text reaches SPARQL only through `term()` (DEC-1).
- G-4: the OpenAPI document shows a `<slot>~` parameter for each string slot, and only for those.

**Non-Goals**
- The EPIC's no-gos (regex, prefix, fuzzy, ranking; non-string slots); a full-text index.
- Contains on the tenant listing (it already refuses every filter, `router.py:262`).
- Contains in reference-collection rules (`rule_filters`, `reference_collections.py:101`, stays
  equality only).

## Decisions

- **PD-1 Parsing.** In `list_request`, a parameter whose name ends in `~` is a contains filter on
  the name without its last `~`: `Filter(slot="label", value="dune", contains=True)`. The value is
  taken as sent (`a=b` stays `a=b`). Any other name is an equality filter, as today. The reserved
  names (`limit`, `offset`, `sort`) are compared before the `~` is stripped, so `sort~=x` is a
  filter on a slot `sort`, which no type offers (400, existing message).
- **PD-2 Model.** One reusable LinkML slot `filter_contains` (`slot_uri: rp:filterContains`,
  `alias: contains`, `range: boolean`, description "Whether the filter matches a substring of
  the slot's text, ignoring case, rather than the value") used by `Filter` and `Condition`, each
  with `slot_usage: {filter_contains: {ifabsent: "false"}}`, as `condition_reference` does
  (`rp_persistence_services.yaml:92`). The descriptions of `Filter`, `ListRequest.filters`,
  `Condition` and `ListPlan.conditions` drop "equality". Then `make generate`. Rejected: an
  operator enum; the no-gos admit no third operator.
- **PD-3 String-ranged.** A slot is string-ranged when it is not an enum, does not hold an IRI
  (`holds_iri`, `schema/services/schema_structure.py:120`) and the URI of its range type
  (default range included) expands to `xsd:string`: exactly the slots `rdf_term`
  (`schema_structure.py:127`) writes as plain literals. A new `holds_text(view, slot)` beside
  `holds_iri` says so. In the toy `Book`: `label`, `description`, `isbn`, `authors` are;
  `published` (date), `genre` (enum), `shelf`, `sequel_of` (references) and `workflow_status`
  (uri) are not. A type derived from string with its own URI (e.g. `sparql_term`,
  `rp:SparqlTerm`) is not. A language-tagged or `xsd:string`-typed value found in the store is
  still matched, since `STR()` drops the tag and type.
- **PD-4 Plan.** `Listings.plan` resolves a contains filter's slot as today (`_slot`, unknown →
  `BadQuery`), then refuses with `BadQuery` a slot that is not string-ranged
  (`"{Class} slot {name!r} is not a string; ~= takes a string slot"`) and an empty text
  (`"~= on {name!r} needs at least one character"`, PD-10). It keeps
  `Condition(predicate=…, value=text, contains=True)`; no `typed_value` call for it.
- **PD-5 Rendering.** `contains_patterns(variable, pairs)` in `core/domain/sparql.py`, pairs of
  `(URIRef, Literal)`, renders for the n-th pair
  `FILTER EXISTS { ?{v} <p> ?{v}_c{n} . FILTER (CONTAINS(LCASE(STR(?{v}_c{n})), LCASE("text"))) }`,
  the predicate through `term(URIRef)` and the text through `term(Literal(text))`, exactly as
  `match_patterns` renders an equality value today (`core/domain/sparql.py:177`). **Reading of
  DEC-1:** "bound as a literal, never spliced" means, in this toolkit, that the text reaches the
  query only as a literal term escaped by `term()` (`sparql.py:68`; quotes, backslashes,
  control characters and `\u` escapes, `sparql.py:47-53`), never as raw text in the template; no
  `VALUES` or protocol binding is added, as equality filters have none. `EXISTS` binds no
  variable in the outer solution, so an aggregate with two matching values is one row (G-2). It
  refuses a non-plain variable and a raw `str` as `match_patterns` does.
- **PD-6 One renderer of conditions.** `condition_patterns(variable, conditions) -> SparqlTerm` in
  `listing.py` joins `match_patterns` over the equality conditions and `contains_patterns` over the
  contains ones. It replaces `match_patterns(v, condition_pairs(c))` at its three uses
  (`listing.py:283`, `session.py:999`, `session.py:1436`), so `matches` and the commit guard agree
  with `find` whatever a condition holds. `condition_pairs` stays for equality conditions only.
- **PD-7 `Contains`, generated (owner, OPEN-2 decided; `inputs/qa.md`).** A LinkML class
  `Contains` in `rdf_persistence/model/technical/persistence/rp_persistence_services.yaml`, beside
  `Filter` (generated into `persistence/services/generated/rp_persistence_services.py`, base
  `RpModel`): `class_uri: rp:Contains`, description "A value of `Session.find` that asks for a
  case-insensitive substring of a string slot rather than its value", one required slot
  `contains_text` (`slot_uri: rp:containsText`, `alias: text`, `range: string`). Then
  `make generate`. Being a pydantic model it is built by keyword: `Contains(text="dune")`, not the
  EPIC's illustrative `Contains("dune")`; a non-`str` text is a pydantic `ValidationError`
  (probed: `Filter(value=19)` refuses). No length rule on the model: the empty text is refused in
  one place, `Listings.plan` (PD-10). `_filters` turns a `Contains` (alone or as an item of a list
  or tuple) into `Filter(slot=name, value=item.text, contains=True)`. Exported in
  `rdf_persistence.__all__`; the public-surface snapshot and `NAMES` (148 → 149,
  `tests/unit/test_public_surface.py:27`) follow with `make refresh-surface`; `rp_service.ts`
  gains `interface Contains` through `make generate` and `make refresh-served-golden`.
- **PD-8 OpenAPI.** For each listable slot that `holds_text`, a query parameter `<name>~`
  right after `<name>`, schema `{"type": "string", "minLength": 1}`, description
  `"Only the {rp_path} whose {name} contains this text, ignoring case. May be repeated: each must
  hold."`, in `openapi.py` beside `_filter`. The served golden is rewritten by
  `make refresh-served-golden`.
- **PD-9 Docs.** `architecture/api.adoc#serving` (Listings and OpenAPI paragraphs),
  `reference/http-api.adoc#listings` (one table row `<slot>~=<text>`), `Session.find`'s and
  `list_request`'s docstrings, the module docstring of `listing.py`.
- **PD-10 Empty text is 400 (owner, OPEN-1 accepted).** `label~=` and `label~` answer 400
  `bad-query`; `find(Book, label=Contains(text=""))` raises `BadQuery`. Both through PD-4.
- **PD-11 `rp-aggregate-store` delta (owner, OPEN-3 accepted).** The change carries
  `specs/rp-aggregate-store/spec.md`, a MODIFIED "A session finds aggregates by slot values" with
  the scenario "a substring in any case" (`find(Book, label=Contains(text="DUNE"))`).
- **PD-12 Scenarios on the toy model.** The spec scenarios name the toy `Book`'s slots: `label`
  (not `title`), `published` (not `year`), `genre` (an equality filter, not `author=<iri>`), so
  each maps to one TC in `tests/audit/scenario-map.csv`:

  | Delta scenario | TC |
  |---|---|
  | rp-service-api: a substring in any case | TC-09a |
  | rp-service-api: a non-string slot | TC-09b |
  | rp-service-api: combined filters | TC-09c |
  | rp-service-api: an empty text | TC-09d |
  | rp-service-api: an item matching on several values is listed once | TC-05 row `authors~=E&limit=2` |
  | rp-service-api: the contract shows a contains parameter per string slot | TC-10 |
  | rp-aggregate-store: a substring in any case | TC-07a |

## Algorithm / approach

Semantics (all in one `WHERE`, so the count and the page see the same filter):

| Case | Result |
|---|---|
| `label~=DUNE` | aggregates with a `label` value containing `dune` in any case |
| multivalued `authors~=e` | an aggregate matches when **any** value contains `e`; listed once |
| `label~=a&label~=b` | both must hold (each may match a different value of a multivalued slot) |
| `label~=u&genre=fiction` | both filters hold (AND), as equality filters do |
| `label=Dune&label~=un` | allowed; both hold |
| hidden graph | out of page and total (unchanged `_MATCHING`) |
| `sort`, `limit`, `offset` | unchanged |

Worked example (toy shelf of `tests/unit/persistence/test_listing_query.py:139-151`: 1 Dune/Herbert,
2 Emma/Austen, 3 Ulysses/Joyce+Herbert, 4 Candide/none, 5 Beloved/Morrison):
`[("authors~","E"),("limit","2")]` → page `[1, 2]`, total 3. Without `EXISTS`, book 3 (Joyce and
Herbert both contain `e`) would give two rows and shift the page. The `$patterns` for
`label~=dune` is:

```
FILTER EXISTS { ?root <http://www.w3.org/2004/02/skos/core#prefLabel> ?root_c0 .
  FILTER (CONTAINS(LCASE(STR(?root_c0)), LCASE("dune"))) }
```

Idempotency: read-only; a retried listing is the same query.

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Format the text into the query (`f'CONTAINS(..., "{text}")'`) | `term(Literal(text))` inside `contains_patterns` | `'"} ; DROP ALL ; #'` would break out (DEC-1) |
| `?root <p> ?v . FILTER(CONTAINS(...))` directly in `$patterns` | `FILTER EXISTS { … }` | a second matching value duplicates the row; `_PAGE_BY_IRI` has no `DISTINCT`, so the page shifts |
| Lower-case the text in Python and send it | `LCASE` on both sides in SPARQL | Python and the store fold some letters differently; one side's rule must decide |
| Filter the page in Python after the query | the filter inside `_MATCHING` | totals and paging go wrong (the EPIC's why) |
| Render conditions separately in `matches` or the commit guard | `condition_patterns` everywhere (PD-6) | a contains condition would silently become an equality |
| Edit `rp_persistence_services.py` or `rp_service.ts` by hand | change the YAML, `make generate` | LinkML is the single source (AGENTS.md principle 2) |
| Strip `~` from any position of the name | only a trailing `~`, once | `ti~tle` is a slot name no type has, 400 |

## Error matrix

| Failure mode | How it is detected | Expected handling |
|---|---|---|
| `published~=19` (date), `genre~=fic` (enum), `shelf~=x` (reference), `workflow_status~=x` (uri) | `Listings.plan`, `holds_text` false | `BadQuery` → 400 `bad-query`, PD-4 message |
| `nope~=x`, `~=x` (empty slot name), `label~~=x` | `_slot` finds no `nope`, `""`, `label~` | `BadQuery` → 400, existing message |
| `label~=` or `label~` (empty text) | `Listings.plan` | `BadQuery` → 400 (PD-10) |
| hostile text: `'"} ; DROP ALL ; #'`, a lone `"`, `\`, `}`, a newline, `"` | `term()` escapes it (PD-5) | matches nothing, store unchanged (TC-04, TC-06, IT-2) |
| `?label~=x` on the tenant listing | `paging.filters` non-empty, `router.py:262` | 400, existing message |
| `Contains(text=19)` in `find` | the generated model | pydantic `ValidationError` |
| `find(Book, published=Contains(text="19"))` | `Listings.plan` | `BadQuery` (no HTTP) |
| a store that evaluates `EXISTS` outside the active graph | IT-1 on Fuseki | test fails; RISK-2 |
| a text the store's `LCASE` folds differently from rdflib's | not detected | accepted (EPIC rabbit-hole; RISK-3) |
| a duplicate row from a multivalued match | TC-05 row `authors~=E&limit=2` | prevented by `EXISTS` (PD-5) |

## Test case specifications

Tier: `unit` unless said. Test names are the implementer's; the file is fixed.

| ID | File | Input | Expected |
|---|---|---|---|
| TC-01 | `tests/unit/persistence/test_listing.py` | `list_request([("label~","dune")])`, `("label","dune")`, `("label~","a=b")`, `("sort~","x")` | `Filter(label, dune, contains=True)`; `contains=False`; value `a=b`; a filter on slot `sort` |
| TC-02 | `tests/unit/schema/test_schema_structure.py` | `holds_text` on each listable `Book` slot | true: label, description, isbn, authors; false: published, genre, shelf, sequel_of, workflow_status (a row per slot, rule 6) |
| TC-03 | `tests/unit/persistence/test_listing.py` | plans of the error matrix's first three rows | `BadQuery` each, parametrized |
| TC-04 | `tests/unit/core/test_sparql.py` | `contains_patterns("root", [(P, Literal(t))])` for each injection text `t` of `'"} ; DROP ALL ; #'`, `'"'`, `'\\'`, `'}'`, `'a\nb'`, `'\\u0022'` (parametrized); empty pairs; raw `str`; variable `"r o"` | each parses inside `ASK { ?root ?p ?o . $patterns }` as one `CONTAINS` whose literal equals `t`; `""`; `SparqlError`; `SparqlError` |
| TC-05 | `tests/unit/persistence/test_listing_query.py` (table at `:166`) | `label~=DUNE` → [1],1; `label~=u` → [1,3],2; `authors~=HER` → [1,3],2; `authors~=E&limit=2` → [1,2],3; `label~=u&genre=fiction` → [1,3],2; `label~=u&genre=nonfiction` → [],0; `authors~=e&authors~=j` → [3],1; `label~=e&sort=-label&limit=2&offset=1` → [2,4],4 (note below) | page and total |
| TC-06 | same file | `("label~", t)` for each TC-04 text `t` (parametrized) | `([], 0)`, store unchanged |
| TC-07 | `tests/unit/access/test_session_find.py` | a: `find(Book, label=Contains(text="DUNE"))`; b: `authors=[Contains(text="her"), "Joyce"]`; c: `Contains(text=19)`; d: `published=Contains(text="19")`; e: `label=Contains(text="")` | a: the Dune IRI; b: book 3 only; c: `ValidationError`; d, e: `BadQuery` |
| TC-08 | `tests/unit/persistence/test_session_guards.py` | `matches(dune_iri, BOOK, [Condition(label, "UN", contains=True)])` and `"zz"` | true; false |
| TC-09 | `tests/unit/api/test_listing_routes.py` (own store) | books Dune (fiction), Children of Dune (nonfiction), Emma; a: `?label~=DUNE`; b: `?published~=19`; c: `?label~=dune&genre=fiction`; d: `?label~=`; e: `/libraries?label~=x` | a: 2 items, total 2; b: 400 `bad-query`; c: Dune only, total 1; d: 400 `bad-query`; e: 400 |
| TC-10 | `tests/unit/api/test_openapi.py` | the books listing operation's parameters | `label~`, `description~`, `isbn~`, `authors~` present with `minLength: 1`; no `published~`, `genre~`, `shelf~` |
| IT-1 | `tests/integration/api/test_listing.py` (`:42` table, Fuseki) | `label~=DUNE` → ["Dune"]; `label~=u&sort=label` → ["Dune","Ulysses"]; `label~=u&sort=label&limit=1&offset=1` → ["Ulysses"] with total 2 | labels in order |
| IT-2 | same file (`:56`) | each `INJECTIONS` value through `label~` | nothing matched, nothing changed |
| IT-3 | `make typecheck-openapi-ts` | the served document | `tsc --strict` passes with `"label~"` keys |

TC-05 note: labels containing `e` are Emma, Ulysses, Candide, Beloved; by `-label` they are
Ulysses(3), Emma(2), Candide(4), Beloved(5); `limit=2&offset=1` → `[2, 4]`, total 4.

## Risks / Trade-offs

- **RISK-1** (certain, low now): a contains filter scans every value of the slot in the tenant.
  Accepted by the EPIC (rabbit-hole); the upgrade is a store full-text index behind the same
  operator.
- **RISK-2** (low, high): Fuseki evaluates `FILTER EXISTS` inside `GRAPH ?graph` against a graph
  other than the active one, so a value in another aggregate's graph would match. rdflib keeps
  the active graph (probed); IT-1 proves Fuseki does.
- **RISK-3** (low, low): `LCASE` folds some non-ASCII letters differently on rdflib (the fake)
  and Fuseki (Java). Accepted (EPIC rabbit-hole); tests use ASCII.
- **RISK-4** (low, medium): a consumer's own code builds `Condition`s and renders them with
  `match_patterns(condition_pairs(...))`; a contains condition would become an equality there.
  `condition_pairs` is not in `rdf_persistence.__all__`; the docstring of `condition_pairs` says
  "equality conditions only; use `condition_patterns`".
- **RISK-5** (low, low): a proxy rewrites `~` as `%7E`. Arrives the same (Context table).

## Open Questions

None open. The owner answered OPEN-1 to OPEN-3 on 2026-11-20 (`inputs/qa.md`): PD-10, PD-7,
PD-11.

## Delivery decisions

Taken by the lead under R-0007, shown to the developer at the end.

- **D-1 The PLAN on the branch.** The gated PLAN was on `docs/epics-consumer-needs`, not yet in
  `develop`. Only this change's folder was copied, unchanged, as the branch's first commit; a
  rebase drops it once that branch merges.
- **D-2 Impact of `list_request` is HIGH.** GitNexus rates it HIGH because every listing route
  passes through it, which is the surface this change targets. The change is additive: a
  parameter `x~` already answered 400 as an unknown slot. Proceeded without a stop.
- **D-3 Parallel builders (developer, 2026-11-20: "work with subagents in parallel").** Task 1.3
  is split into 1.3a (`holds_text`, TC-02; disjoint files) and 1.3b (plan, `condition_patterns`,
  the routes); task 2.1 into 2.1a (the two Antora pages) and the docstrings, which each code task
  updates. 1.1, 1.2, 1.3a and 2.1a run in parallel: 1.1 in the branch's worktree, the
  others each in its own worktree under `.worktrees/` from `3d7dde5e`; the lead commits each
  result there and cherry-picks it. 1.3b follows 1.1, 1.2 and
  1.3a; 1.4 and 1.5 follow 1.1 (same YAML and served golden). Correction after 1.1: nested
  worktrees are not invisible to the lead's gates: `test_no_live_file_still_names_an_old_path`
  scans the tree and fails on their copies. Builders now never run in the branch's worktree, and
  each nested worktree is removed once its commit is picked, so none exists at the full gates.
  Each worktree needs `make install` before its first gate; an edit to a generator input
  (e.g. `schema_structure.py`) needs `make generate`; the lead regenerates once after picking
  results that touched the same manifests (`make check-generated` after 1.1 + 1.3a: fresh).
- **D-4 Wave 2 and the impact of the plan.** GitNexus rates `Listings.plan`, `condition_pairs`
  and `AggregateOpenApi._query_parameters` HIGH: they are on the listing, commit-guard and OpenAPI
  paths this change targets. `condition_pairs` has exactly the three uses PD-6 names.
  `Listings.plan` has two callers the PLAN does not name, `write_guards.prepare` and
  `reference_collections.delete_cascade`; both pass equality filters only (`rule_filters` stays
  equality, Non-Goals), so they are unchanged while equality is, which the full suite covers.
  TC-07 needs the plan of 1.3b, so 1.4 follows 1.3b; 1.3b and 1.5 run in parallel.

### Under the floor

- 1.1: the module docstring of `listing.py` has one line over the page width (lint passes).
- 1.3a: `holds_iri` reads `slot.range` without the default range; harmless for the induced slots
  listings use, which always carry a range.
- 2.1a: two lines of `api.adoc` run past the page's wrap width; the rendered page is the same.
- `shapes.ttl` diffs are large on any model change because c14n blank-node labels renumber
  (1.1: about 1000 lines for one added property). Generator awkwardness, not a defect here.
