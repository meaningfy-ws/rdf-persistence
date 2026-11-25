# Design: reference-filters

> Derives from: EPIC `reference-filters` (`proposal.md`, #308). Its DEC-1 to DEC-8 are cited here,
> not restated. The delivery decisions below are D-n. It builds on `consumer-gap-fixes` DEC-5, DEC-6
> and its design D-1 to D-3, which must have merged before task 1.1 starts (RISK-1).

## Context

The code facts were read on `origin/develop` at `f12e8675`. `consumer-gap-fixes` stage 4 was
planned there but not yet delivered.

- `list_request` (`listing.py` l.113) makes each non-reserved parameter a
  `Filter(slot=name minus "~", value, contains)`. A dotted name already arrives as
  `Filter(slot="a.b")`. `RESERVED` is compared on the whole name.
- `Listings._filtered` (l.269) resolves one filter with `_slot(cls, name)`, which looks in
  `listable_slots` and raises `BadQuery` "<Class> has no slot '<name>' to filter or sort on". It
  then types an equality value with `typed_value(view, slot, text)` or builds a contains condition
  with `_contains(cls, slot, text)`.
- `listable_slots` (l.144) drops the identifier, bookkeeping, `internal` slots, owned parts and
  reserved names. A reference to another aggregate is listable (equality on its IRI).
- `condition_patterns(variable, conditions)` (l.217) is the one renderer. Its output goes inside
  `GRAPH ?graph { ?root a $target . $patterns }` in the listing (`_MATCHING`, l.66, for both the
  page and the count), inside `MATCHES` (`session.py` l.282) and inside `_MATCH_GUARD` (l.286).
  The page `SELECT ?root ?graph` has no `DISTINCT`, so a pattern that binds several rows per root
  repeats the root. `contains_patterns` avoids that with `FILTER EXISTS`
  (`core/domain/sparql.py` l.184).
- The hidden graphs (`AccessRules.hidden_graphs`, a caller's read Prohibitions) reach the listing
  as `ListPlan.hidden_graphs` and are applied to `?graph` only (`_MATCHING`).
- An aggregate's named graph is `f"{root}/graph"` (`iris/domain/layout.py` `graph_iri`, l.46,
  PD-4). It is a pure function of the root IRI, so a query can compute it.
- `Session.find` → `_filters` → `_filter(name, item)` → `Filter(slot=name, …)`. A dotted keyword
  passed as `**{"a.b": v}` already reaches `_filtered` unchanged. `find` plans with no hidden
  graphs (PD-6).
- `database_of(view, cls)` (`schema_structure.py` l.336) gives a class's database, and
  `Listings._database` holds the listing's.
- The toy (`tests/fixtures/library/books.yaml`) has these references:
  - `Book.written_by → Author` and `Book.sequel_of → Book` (two hops:
    `sequel_of.written_by.label`).
  - `Display.features → Book`, multivalued.
  - `Loan.lends → LendingItem`, an abstract range (`mixins: [AggregateRoot]` only). `Magazine`
    and `Pamphlet` have `is_a: LendingItem` and add `Described` (so `label`). `LendingItem`
    itself declares no `label`.
  - `templates.yaml` has a class with `database: application`.

## Goals / Non-Goals

**Goals:** S1 to S10 (the error matrix), each a test that fails first; one renderer; a path-less
condition renders byte for byte as before.
**Non-Goals:** the EPIC's No-gos.

## Decisions

- **D-1 (DEC-1): `condition_via` on `Condition`.**
  - The slot: `slot_uri: rp:conditionVia`, `alias: via`, `range: uri`, `multivalued: true`, and
    not required. It holds the predicate IRIs of the hops, in order. `None` (or empty) means the
    condition is on the root.
  - `condition_predicate` and `condition_value` keep their meaning: the last segment's predicate
    and value.
  - `Filter` is unchanged; its `filter_slot` carries the dotted name. Then `make generate`.
- **D-2: `hop_patterns` renders the hops, `condition_patterns` dispatches.**
  `core/domain/sparql.py` gains
  `hop_patterns(subject: str, predicate: URIRef, target: str, suffix: str, hidden: Sequence[URIRef], inner: SparqlTerm) -> SparqlTerm`,
  which renders:

  ```
  ?{subject} <predicate> ?{target} .
  BIND (IRI(CONCAT(STR(?{target}), "{suffix}")) AS ?{target}_g)
  FILTER (?{target}_g NOT IN (<h1>, …))        # only when hidden is non-empty
  GRAPH ?{target}_g { {inner} }
  ```

  - `subject` and `target` are checked against `_VARIABLE`, as `match_patterns` does.
  - `suffix` is passed in, because `core/domain` does not import `iris`. `layout.py` gains
    `GRAPH_SUFFIX = "/graph"`, and `graph_iri` and `root_of_graph` use it. `.importlinter`
    makes `core` the lowest theme.
  - `suffix` is rendered through `term(Literal(suffix))`; the hidden IRIs go through `term`.

  `condition_patterns(variable, conditions, hidden: Iterable[str] = ())` lives in `listing.py`,
  which already imports `iris.domain.layout`. It imports `GRAPH_SUFFIX` itself and hands it to
  `hop_patterns`. On entry it turns `hidden` into a `list[URIRef]` once, so every hop gets the
  whole list (a generator would otherwise give `NOT IN` to the first hop only). It then changes as
  follows:
  - It splits the path conditions (`via` non-empty) from the rest.
  - The rest render exactly as before: equal, contains and, after stage 4, absent.
  - Path condition *n* (numbered from 0 among the path conditions) with hops `p1…pk` renders as
    `FILTER EXISTS { <hop 1 wrapping hop 2 … wrapping last> }`.
    - Hop *j*'s target variable is `{variable}_p{n}_{j}`.
    - The innermost `inner` is the last segment, rendered on `{variable}_p{n}_{k}` with the
      existing `match_patterns` (equality) or `contains_patterns` (contains).
  - `FILTER EXISTS` keeps one row per root (Context). The per-condition numbering keeps the
    conditions' variables apart, which gives DEC-4's independence.
- **D-3: `listing_query` passes `plan.hidden_graphs` to `condition_patterns`.**
  - `matches` and `_require_match` pass nothing, so a guard or a `matches` call renders no hidden
    filter.
  - Since a path-less condition set never calls `hop_patterns`, the hidden list changes nothing
    for it (E14).
  - The root's own `?graph NOT IN` filter stays in `_MATCHING`.
- **D-4 (DEC-2, DEC-3): hop-by-hop resolution in `_filtered`.** A filter whose slot holds `.` is a
  path:
  1. `names = slot.split(".")`. An empty name gives `BadQuery` "'<slot>' has an empty segment".
     More than `MAX_HOPS = 3` hops (`len(names) - 1`) gives `BadQuery` "a filter crosses at most 3
     references".
  2. For each name but the last:
     - `ref = self._slot(current, name)`: an unknown slot or an owned part already gives
       `BadQuery`.
     - `self._hop(current, ref)` checks three things:
       - `ref.range` is a class with `AGGREGATE_ROOT` in `view.class_ancestors(range)`. Abstract
         ranges are allowed; `aggregate_roots` is not used, because it drops abstract classes.
       - The range is not the tenant root (`is_tenant_root`). Its graph is the meta graph, not
         `<root>/graph`, so a hop there could never match.
       - The range's `database_of` equals `self._database`.

       If either of the first two fails, it raises `BadQuery` "<Class> slot '<name>' is not a
       reference to an aggregate; a filter crosses references only". If the database differs,
       it raises `BadQuery` "<Class> slot '<name>' refers to the <database> database; a filter
       stays in one database".
     - `ref`'s predicate is appended to `via`, and `current` becomes the range class.
  3. The last name is resolved on `current` exactly as a root slot is today: `typed_value` or
     `_contains(current, …)`. The resulting `Condition` gets `via`.
  4. After stage 4, an absence filter whose slot holds `.` gives `BadQuery` "absent takes a slot
     of <Class>, not a path". `_filtered` checks this first, before stage 4's absent branch calls
     `_slot`, so the message is this one and not "has no slot". `sort=a.b` is refused already: `_sort` → `_slot(cls, "a.b")` →
     "has no slot".
- **D-5 (DEC-6): `find` needs no code.** The docstring gains the dotted keyword and DEC-4. A
  `None` value with a dotted name (stage 4 turns `None` into absence) is refused by D-4 step 4.
- **D-6 (DEC-7): one sentence in the listing's OpenAPI description** (`AggregateOpenApi.listing`,
  `openapi.py` l.458).
  - Today `route_options` (l.243) takes a `summary` only. `RouteDocs` carries no description, and
    `_OPERATION_PARTS` (l.97) does not include one; the served golden has no listing description.
  - So `route_options` gains an optional keyword `description: str | None = None`. `RouteDocs`
    keeps it, and `add_to` passes it to `add_api_route(description=…)`.
  - Only `AggregateOpenApi.listing` sets it. The sentence reads: "A filter may go through up to
    three references: `<reference>.<slot>=<value>` or `<reference>.<slot>~=<text>`."
  - No parameters are added. The served OpenAPI golden (`tests/unit/api/test_openapi_served.py`,
    rewritten with `make refresh-served-golden`) gains that one `description` per aggregate
    listing operation and nothing else. The TypeScript golden does not change
  at all.

## Algorithm / approach

Worked example: `GET /books?sequel_of.written_by.label~=herbert`, with a caller hiding `<H>/graph`.

1. `list_request` gives `Filter(slot="sequel_of.written_by.label", value="herbert", contains=True)`.
2. `_filtered`:
   - `sequel_of` resolves on `Book`; its range `Book` is in the tenant database, so it is a hop.
   - `written_by` resolves on `Book`; its range `Author` is a hop.
   - `label` resolves on `Author` and is text, so it is a contains.
   - The result is `Condition(predicate=skos:prefLabel, value="herbert", contains=True, via=[lib:sequelOf, lib:writtenBy])`.
3. `condition_patterns("root", [c], hidden=["<H>/graph"])`:

   ```sparql
   FILTER EXISTS {
     ?root <…sequelOf> ?root_p0_1 .
     BIND (IRI(CONCAT(STR(?root_p0_1), "/graph")) AS ?root_p0_1_g)
     FILTER (?root_p0_1_g NOT IN (<H/graph>))
     GRAPH ?root_p0_1_g {
       ?root_p0_1 <…writtenBy> ?root_p0_2 .
       BIND (IRI(CONCAT(STR(?root_p0_2), "/graph")) AS ?root_p0_2_g)
       FILTER (?root_p0_2_g NOT IN (<H/graph>))
       GRAPH ?root_p0_2_g { FILTER EXISTS { ?root_p0_2 skos:prefLabel ?root_p0_2_c0 .
         FILTER (CONTAINS(LCASE(STR(?root_p0_2_c0)), LCASE("herbert"))) } }
     }
   }
   ```

   The real output is on one line. Whitespace is illustrative.
4. The page and the count both use it, so `total` agrees with the page.

### Tests first (all RED before the code)

- **Unit, `tests/unit/core/test_sparql.py`, beside the `contains_patterns` tests:**
  - `hop_patterns` output, with hidden and without.
  - A bad variable name gives `SparqlError`.
  - A hostile suffix or IRI stays one term.
- **Unit, `tests/unit/persistence/test_listing.py`:** the resolution rows S2b, E2 to E13, E16 and the
  `via` of S1 and S3 (the `Condition` a filter resolves to), using `Listings(view)` on
  `TOY_SCHEMA`. E9 is written once stage 4 has merged (it needs `absent`).
  - E11 and E16 build their schema in the test, never in the fixture. Load a fresh
    `load_schema(TOY_SCHEMA)`, then `view.add_slot(SlotDefinition(name, range=<class>))`, then
    append the name to `Book.slots`, then `view.set_modified()`. E11 uses the `application`
    class in `templates.yaml`; E16 has two cases: the tenant root class `Library`, and a non-owned slot with
    `range: Chapter` (a class that is not an aggregate root).
- **Unit, `tests/unit/persistence/test_listing_query.py`** (in-memory store, the existing pattern):
  S1, S2, S3, S3b, S6, S9, S10 and E14.
  - E14 has two parts. First, the path-less rendering of an equal, a contains and an absent
    condition set is compared with the strings `condition_patterns` returned before the change.
    Second, the whole `listing_query` text for a path-less plan **with** hidden graphs is compared
    with the text it returned before the change. Both are captured as literals in the test at
    task 1.3, from the code merged by stage 4.
- **Unit, `tests/unit/api/test_listing_routes.py`:** S4 through `GET`, with `total`.
  - The `Shelf` helper (`listing_shelf.py`) seeds books with the string slot `authors` only, so
    the test adds a helper that POSTs an `Author` and a book with `written_by` pointing to it.
  - It then prohibits `<author>/graph` the way
    `test_a_book_the_caller_is_prohibited_from_reading_is_not_listed_or_counted` does (l.46), with
    `prohibitions=[…]` on the caller's access record.
- **Integration, `tests/integration/api/test_listing.py`** (Fuseki): S1 and S3b through `GET`, with
  `total`. This proves Fuseki evaluates the nested `GRAPH` with `BIND`.
- **Integration, `tests/integration/store/test_session.py`:** S8, `find` with a dotted keyword.

Idempotency: a read only. Nothing is written.

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Render a hop as a plain triple join in the root's patterns | `FILTER EXISTS` around the hops | A multivalued reference would repeat the root and break paging |
| Match the target's value in any graph (`GRAPH ?g` unbound) | Bind `?g` to `<target>/graph` | A statement about the target in another aggregate's graph would match (S10) |
| Join the registry graph per hop | Compute the graph IRI (PD-4) | No registry inside `matches` or the guard; one less join |
| A second renderer or a `PathFilter` model | `via` on `Condition`; dispatch in `condition_patterns` | One code path (DEC-1) |
| Post-filter or compose listings in Python | Filter in SPARQL | Paging and `total` would be wrong (#308) |
| Add an OpenAPI parameter per path | Describe the syntax once | The parameters would multiply per reference (DEC-7) |

## Error matrix

| # | Input (toy) | Detection | Response | Fallback |
|---|---|---|---|---|
| S1 | `GET /books?written_by.label=Frank Herbert` | `_filtered` → `via=[writtenBy]` | the books by that author, with `total` | n/a |
| S2 | `GET /displays?features.written_by=<A>`, a display featuring two books both by A (ISBNs are unique, so not `isbn`) | `FILTER EXISTS` | the display listed once, `total` 1 | n/a |
| S2b | `GET /loans?lends.label=X` (abstract range; only the subclasses declare `label`) | `_slot(LendingItem, "label")` | 400 "LendingItem has no slot 'label'…" (DEC-2, Q7) | filter on a slot the range declares |
| S3 | `GET /books?sequel_of.written_by=<author iri>` | one hop; the last segment is a reference equality | the sequels of that author's books | n/a |
| S3b | `GET /books?sequel_of.written_by.label=Frank Herbert` (two hops) and `?sequel_of.sequel_of.written_by.label=…` (three hops, the cap) | two and three nested hops | the matching books; three hops is accepted | n/a |
| S4 | as S1; the caller has a read Prohibition on the author | `NOT IN` inside the hop | the book is not listed; `total` excludes it | n/a |
| S6 | `GET /books?written_by.label~=herb` | contains on the last hop | as S1, by substring | n/a |
| S8 | `find(Book, **{"written_by.label": "Frank Herbert"})` | same path | the IRIs; prohibitions ignored (PD-6) | n/a |
| S9 | a book whose author was deleted (dangling IRI) | no `<author>/graph` | not matched | n/a |
| S10 | another aggregate's graph states `<author> skos:prefLabel "X"` | the hop's graph is bound | not matched | n/a |
| E2 | `?nosuch.label=x` | `_slot(Book, "nosuch")` | 400 `bad-query` "Book has no slot 'nosuch'…" | fix the name |
| E3 | `?isbn.x=1` | `_hop` | 400 "Book slot 'isbn' is not a reference to an aggregate…" | n/a |
| E4 | `?chapters.number=1` (owned part) | `_slot`: not listable | 400 "Book has no slot 'chapters'…" | n/a |
| E5 | `?sequel_of.sequel_of.sequel_of.sequel_of.isbn=1` (4 hops) | `len(names) - 1 > 3` | 400 "a filter crosses at most 3 references" | n/a |
| E6 | `?written_by..label=x`, `?written_by.=x`, `?.label=x` | empty name | 400 "has an empty segment" | n/a |
| E7 | `?written_by.id=<iri>` (the range's identifier) | `listable_slots` drops the identifier | 400 "Author has no slot 'id'…"; filter on `written_by=<iri>` instead | n/a |
| E8 | `?written_by.label~=` (empty text) | `_contains` | 400, as today | n/a |
| E9 | `?absent=written_by.label` | D-4 step 4 | 400 "absent takes a slot of Book, not a path" | n/a |
| E10 | `?sort=written_by.label` | `_sort` → `_slot` | 400 "has no slot 'written_by.label'" | n/a |
| E11 | a hop whose range lives in the application database | `_hop` (`database_of`) | 400 "Book slot '<name>' refers to the application database; a filter stays in one database" | n/a |
| E16 | a hop whose range is the tenant root, or a class that is not an aggregate root | `_hop` (`is_tenant_root`, `AGGREGATE_ROOT` ancestry) | 400 "not a reference to an aggregate…" | n/a |
| E12 | `?written_by.published=notadate` (wrong slot class) | `_slot(Author, "published")` | 400 "Author has no slot…" | n/a |
| E13 | `?written_by.label=x&written_by.label=y` | two path conditions, p0 and p1 | both must hold, each by any target (DEC-4) | n/a |
| E14 | any condition set with no path (listing, `matches`, guard) | `condition_patterns` | renders exactly as before | n/a |
| E15 | a hostile value or IRI in a path filter | `typed_value` / `term` | `BadQuery` or one literal; no injection (as the existing injection tests) | n/a |

## Risks / Trade-offs

- **RISK-1 (the base moves).** `consumer-gap-fixes` stage 4 may land differently from its D-1 to
  D-3: different names in `condition_patterns`, or a different absence field.
  - Likelihood: medium. Impact: the D-2 and D-4 code sketches are stale, but not the decisions.
  - Mitigation (owner, Q12): task 1.1 re-reads the merged `condition_patterns`, `_filtered` and
    the services model. A divergence is a PLAN revision, made before code.
- **RISK-2 (query cost).** Each path filter adds an `EXISTS` with up to three hops per candidate
  root. It is slow on large tenants if Fuseki does not substitute the bound `?g` into `GRAPH ?g`.
  - Accepted (owner, Q12): the cap of 3 bounds it, and no SLA exists. S1 and S3b on Fuseki prove
    correctness, not speed.
  - A follow-up issue is opened if the consumer reports slowness.
- **RISK-3 (the consumer needs more).** Sort through a reference, or correlated filters.
  - Accepted (owner, Q12): a follow-up issue when asked. DEC-4's independence is documented in
    `reference/http-api.adoc` so that nobody relies on correlation.
- **RISK-4 (lock drift).** The consumer gets nothing until a release.
  - Mitigation: after the merge, ask for a release and comment on #308 with the version.

## Open Questions

None.

## Delivery decisions

Taken by the lead during delivery (R-0007), for the developer to validate at the end.

- **D-7 (task 1.1, RISK-1):** the merged stage 4 code (`condition_patterns`, `_filtered`,
  `Filter.absent`, `Condition.absent`) matches D-2 and D-4; no revision was needed.
- **D-8 (task 1.1, impact):** GitNexus rated `graph_iri` CRITICAL and `Listings._filtered` HIGH,
  both by fan-out (12 and 8 callers). The change keeps `graph_iri`'s output byte for byte (only
  `GRAPH_SUFFIX` is extracted) and leaves a filter without a dot on the old path, so the lead went on
  without stopping; the full gates are the check.
- **D-9 (D-6 correction):** the served TypeScript golden does change, once, by the new optional
  `via` field of `Condition` (task 1.2), not by D-6. The shape snapshot gains the same field.
- **D-10 (task 1.4):** `condition_patterns` was split into `_root_patterns` and `_path_patterns` to
  keep its Xenon rank at B; `hop_patterns` carries `# noqa: PLR0913`, its six parameters being the
  ones D-2 fixes.
- **D-11 (task 1.6):** the empty-segment check applies only to a name holding a dot, so `absent=`
  and a bare `~` keep their existing "has no slot" message.
