<!-- PLAN (design half) of aggregate-validators. PLAN = this file + tasks.md.
     Read against develop 4a22f06e. Revised after the fresh reviewer's attack (run 1, C1-C12). -->

# Design: aggregate-validators

> Derives from: EPIC `aggregate-validators` (proposal.md), DEC-1 to DEC-5; issue #240; owner's
> answers in inputs/qa.md.

## Context

Facts that shape this PLAN (develop `4a22f06e`):

- F-1: `RootValidator` (`tenancy/services/tenancy.py:103-105`) is `(old, new, principal) -> None`;
  `_plain` (:909) refuses an async one; `_run_validators` (:920) passes deep copies and maps failures
  (InvalidBody/ValidationError pass; other → `RuntimeError("a validator raised …")`, which does
  **not** name the validator; a value → `TypeError`). It runs on the tenant root only.
- F-2: every add and replace of a root goes through `Transaction.add_graph` / `replace_graph`
  (`persistence/services/session.py:1478`, :1514), which call the session's one `WriteGuard`
  (`prepare(session, iri, triples, stored, allowed_state, *, context)`, async). Its one
  implementation, `WriteGuards` (`collaboration/services/write_guards.py:62`), is built once by the
  kit (`api/entrypoints/kit.py:212`) and handed by `Tenancy._session` (`tenancy.py:204`) to every
  session: tenant, system and application. It runs the collection rule, then `Workflows.keep_state`,
  which may rewrite the triples. Removes never reach it.
- F-3: restore (`import_quads`), migrations and the sweep write with `store.update` and skip the
  guard (DEC-3).
- F-4: the session holds a `Principal` (an IRI) and knows no schema (`session.py:313`); an access
  decision is `AccessRules.may(caller, access, iri, Action.READ)` (`access/services/access.py:271`).
- F-5: the aggregate routes hold the caller and `CallerAccess` (`api/entrypoints/router.py:409-427`)
  but `DocumentApi.create` / `replace` (`router.py:169`, :196) take only `tenant, iri`; the
  tenant-root PUT is `DocumentApi.replace` too (`router.py:267`). `kit.collaboration` (`kit.py:553`)
  opens sessions for transitions, collection edits and comments with a caller and an access record.
  `DocumentApi.set_label` (`router.py:319`) → `Tenancy.rename(tenant, label, if_version, principal)`
  (`tenancy.py:682`) → `_relabel_root` (:704) writes the tenant root.
- F-6: an existing seam, `Readable` (`session.py:309`), carries a caller's check into a transaction,
  but for a different question: which referrers of a root, given referrer rows.
- F-7: `Session.heads(iris)` (:866) reads types and versions from the registry, one query, no access;
  `Session.not_aggregates` answers which IRIs the policy does not mint as aggregates.
  `Mapper.from_graph(cls, iri, graph, graph_iri)` (`mapper.py:220`) decodes a model; tracking slots
  are read from `graph_iri`'s meta (for the tenant root, the meta graph).
- F-8: `aggregate_roots` (`schema/services/schema_structure.py:309`) excludes a tenant root that is
  not an `AggregateRoot` (the toy `Library`, `tests/fixtures/library/library_tenant.yaml:20`);
  `root_classes` (:318) adds it through `is_tenant_root`. `class_ancestors`/`class_descendants`
  include mixins unless `mixins=False`.
- F-9: no PATCH route; `is_service_written` classes have no POST/PUT route.

## Goals / Non-Goals

**Goals**
- G-1: a rule registered for class C runs on every guarded add and replace of a root of C or of a
  class derived from C (`is_a`), and refuses with 422 before anything is written (DEC-3).
- G-2: one signature, sync or async (DEC-1); the reader answers only classes, access-checked when a
  caller is behind the write (DEC-2).
- G-3: start-up refuses a key that is not an application root (the tenant root included) or a
  non-mixin parent of one.
- G-4: with no aggregate validators, no decoding, no read and no behaviour change.

**Non-Goals**: the EPIC's no-gos (PATCH, restore, migrations, deletes, timeouts, changes to
`root_validators`).

## Decisions

- **PD-1 Types and layer.** A new module `collaboration/services/aggregate_validators.py` (the
  guard's layer, which knows the schema view) holds `AggregateValidator =
  Callable[[BaseModel | None, BaseModel, Principal, AggregateReader], Awaitable[None] | None]`, the
  Protocol `AggregateReader` (`async def classes_of(self, iri: str) -> frozenset[str]`),
  `AggregateValidators` (registration, PD-2) and the reader implementation (PD-5). The persistence
  layer gains only `Session.may_read` (PD-4). `AggregateValidator` and `AggregateReader` are
  exported from `rdf_persistence/__init__.py` beside `RootValidator`.
- **PD-2 Allowed keys** (C1, C2). `install_service(..., aggregate_validators: Mapping[str,
  Sequence[AggregateValidator]] = {})`, passed through `ServiceKit` to `WriteGuards(...,
  validators=AggregateValidators(view, mapping))`, built when the kit is built (so a bad key stops
  start-up). The **roots** are `root_classes(view, folder)` with the kit's schema folder (F-8:
  `aggregate_roots` ∪ the tenant root, of the consumer's own modules only); that folder filter
  already leaves out the toolkit's classes (`TenantAccess`, comments, transition records), so a key
  is a "toolkit class" when the view has it and `own_classes(own_schemas(view, folder))` does not. A key is accepted when it is a class of the view, **not a mixin**, not a
  toolkit class, and it or one of its `is_a` descendants (`class_descendants(mixins=False)`) is a
  root. Otherwise `ValueError` naming the key and the reason ("not a class", "a mixin", "a toolkit
  class", "no root derives from it"). A non-callable rule is `TypeError`. The kit precomputes
  `root class IRI → tuple of rules` (PD-3); an empty mapping makes it empty (G-4).
- **PD-3 Which rules run** (C3). For the root being written, take **every** `rdf:type` of the root
  subject in the triples that is a root (PD-2). With none, no rule. If they are not on one `is_a`
  chain (e.g. `Shelf` and `Book`), and any of them has rules, refuse with `InvalidBody("<iri> has
  root types on two lines: A, B")`, so a client cannot pick a type that escapes a rule. Otherwise
  the most specific type is the model class; the rules are those of its `is_a` ancestors and itself
  (`class_ancestors(mixins=False)`), from the most general key to the class itself, each key's list
  in order; the first refusal stops.
- **PD-4 Who the reader answers for** (C10). `open_session` / `Tenancy.tenant_session` / the
  session take an optional keyword `may_read: Callable[[str], bool] | None = None`, exposed as
  `Session.may_read`. Passed by every entry point that holds a caller: `DocumentApi.create` /
  `replace` (gain the `CallerAccess` argument; the tenant-root PUT included) through
  `Aggregates.create` / `replace`; `kit.collaboration` (transitions, collection edits, comments over
  HTTP); `Tenancy.rename` (gains a keyword `may_read`, passed by `DocumentApi.set_label`, which
  holds the caller and access, and handed to the session `_relabel_root` opens). Each passes `lambda iri: rules.may(caller, access, iri, Action.READ)`.
  Comments are judged by `rules.may` too, not by their thread (`readable_referrers`), so a rule may
  see a comment as unknown that the thread would show; accepted, documented. A session opened without
  it (a bus handler, an `on_commit` handler, the consumer's own unit of work, the toolkit's own
  writes) reads every class, as every session read already does (F-7). Rejected: reusing `Readable`
  (F-6: it judges referrers over rows, not one IRI); fail closed without a caller (the consumer's own
  code would see every reference as unknown); reading the access record in the guard (the token's
  global roles are not in the session, F-4).
- **PD-5 The reader** (C6, C7, C8, C11). Built per `prepare` call, from `session`, `context` and the
  view's class IRI → name map. `classes_of(iri)`: if `may_read` is set and answers false → empty;
  if `session.not_aggregates([iri])` is non-empty → empty, no query; if `iri` is in
  `context.collected` → the root types of those triples (a change collected earlier in the same
  transaction; a later one is not visible); else `session.heads([iri])` → the names of its types
  (unknown type IRIs dropped). Empty for no aggregate. It answers the aggregate's own types, not
  their ancestors. Store errors (`StoreUnavailable`, `DatabaseGone`) pass through unwrapped (PD-7).
- **PD-6 Where in the guard, and decoding** (C4, C5). `WriteGuards.prepare` runs the rules **last**,
  on the triples it is about to return (after `keep_state`). `new = mapper.from_graph(cls, iri,
  graph_of(triples), None)`: it carries no tracking slots (the session adds them after the guard).
  `old` is `None` when `stored is None`; else `(graph, graph_iri, _) = await session.get_graph(iri)`
  and `old = mapper.from_graph(cls_of_stored, iri, graph, graph_iri)`, where `cls_of_stored` is
  chosen from the stored root's types by PD-3's rule (most specific root type on one chain; stored
  types on two lines → the `RuntimeError` below, as undecodable) (tracking included; for the
  tenant root from the meta graph), read only when a rule applies. A `ValueError` decoding `new`
  becomes `InvalidBody` (as `_decoded` does); one decoding `old` (legacy data no longer valid) becomes
  `RuntimeError("the stored <iri> does not decode: …")`, a 500, since the client cannot fix it.
- **PD-7 Running a rule** (C8, C9). `run_aggregate_validators(rules, old, new, principal, reader)`:
  for each rule, inside one `try`: call it with deep copies of `old` and `new`; if the result is
  awaitable, await it. `InvalidBody` and `ValidationError` pass; the store errors of PD-5
  (`StoreUnavailable`, `DatabaseGone`) pass; any other exception becomes `RuntimeError("aggregate
  validator <name> raised <type>: <message>")` chained to it, where `<name> = getattr(rule,
  "__qualname__", repr(rule))` (new: `root_validators` does not name its validator); a non-`None`
  result after awaiting is `TypeError`. DEC-4.
- **PD-8 The tenant root.** `root_validators` run where they run today (before the session, F-1);
  then, if the tenant root's class has aggregate validators, they run in the guard. Both run; a
  refusal by either is 422. On tenant create, the root is written by `_add_root` after the database
  and bucket exist (`tenancy.py:458-466`); a rule's refusal there leaves them, as any guard refusal
  does today; the start-up sweep removes them (`rp-tenancy` "The start-up sweep finishes interrupted
  work"). Stated in the docs; root rules that must leave nothing belong in `root_validators`.
- **PD-9 Conflicts.** `Transaction.replace_graph` compares the stored version with `if_version`
  only at commit; it turns only a guard's `Forbidden` into `Conflict` on a stale version. A rule's
  `InvalidBody` is left as it is: a stale PUT whose body a rule refuses answers **422**, and a stale
  PUT the rules accept answers 409 at commit, as today. Rejected: mapping a refusal to 409 when
  stale (a refused body is refused at any version). The `old` a rule sees is the version stored now.

## Concrete examples

```python
def one_of_each_kind(old, new, who, reader):            # sync: ignores the reader
    kinds = [kind_of(i) for i in new.has_part or []]
    if len(kinds) != len(set(kinds)):
        raise InvalidBody("A shelf holds at most one collection of each kind.")

async def members_differ_in_class(old, new, who, reader): # async: reads classes
    seen = [await reader.classes_of(i) for i in new.has_part or []]
    known = [c for c in seen if c]
    if len(set(known)) < len(known):
        raise InvalidBody("two members of one class")

install_service(app, ..., aggregate_validators={"Shelf": [one_of_each_kind, members_differ_in_class]})
```

## Error matrix

| Case | Result |
|---|---|
| Rule raises `InvalidBody` on POST / PUT | 422 `invalid-body` with its message; nothing written |
| Rule raises `InvalidBody` in a unit of work / bus handler / transition | `InvalidBody` from `commit`/`transition`; nothing written |
| Rule raises `KeyError` (a bug); rule is a `functools.partial` | `RuntimeError` naming the rule (qualname or repr) → 500 |
| Rule returns `True`; async rule returns `1` | `TypeError` → 500 |
| Async rule raises after an `await` | mapped as a sync one (same `try`) |
| Reader hits `StoreUnavailable` / `DatabaseGone` | passes unwrapped → 503 / as today |
| PUT with a stale `If-Match` whose body a rule refuses | 422 (PD-9); nothing written |
| PUT with a stale `If-Match` whose body the rules accept | 409 at commit, as today |
| Root typed `Shelf` and `SpecialShelf` (one chain) | rules of `SpecialShelf` and its ancestors |
| Root typed `Shelf` and `Book` (two lines), a rule applies | 422 naming both types |
| Stored `old` no longer decodes | `RuntimeError` naming the aggregate → 500 |
| `new` does not decode (non-API caller) | `InvalidBody` |
| Reader: IRI the writer may not read | empty, same as no aggregate |
| Reader: literal / foreign / malformed IRI | empty, no query |
| Reader: member added earlier in the same unit of work | its types (from `context.collected`) |
| Reader: member added later in the same unit of work | empty (order limit, documented) |
| Reader: member removed earlier in the same unit of work | its stored types (the store before the commit; documented) |
| Key `Nope`; a mixin (`Described`); a toolkit class (`TenantAccess`); a leaf class no root derives from | start-up `ValueError` naming the key and reason |
| Key = an abstract parent of a root; the tenant root class (`Library`) | accepted |
| Rule refuses the tenant root on tenant create | 422; database and bucket left for the sweep (PD-8) |
| Delete, restore, migration | no rule runs |
| No `aggregate_validators` | no decode, no read; behaviour and query count unchanged |

## Anti-patterns

| Don't | Do | Why |
|---|---|---|
| Decode `new` or read `old` when no rule applies | look up the precomputed map first | G-4: no cost for consumers without rules |
| Write a second decoder for the rule's models | `mapper.from_graph` with the generated classes | one decoding path |
| Let the reader tell hidden from absent | the same empty set for both | DEC-2: no leak |
| Select rules by the first `rdf:type` found | all root types, refused when on two lines | a client could pick a type that escapes a rule |
| Accept mixin or toolkit-class keys | refuse them at start-up | they would run on the toolkit's own writes |
| Query the store for a non-aggregate IRI | `not_aggregates` first | a malformed IRI must not be a 500 |
| Wrap store errors from the reader as a rule bug | let them pass | an outage is 503, not a validator bug |

## Test coverage

Unit tier, `tests/unit/collaboration/test_aggregate_validators.py` (toy `Shelf`, `Library`,
in-memory store as the existing guard tests); `Session.may_read` alone in
`tests/unit/persistence/test_session_may_read.py`; API tier
`tests/unit/api/test_aggregate_validators_api.py` with `tests/toy_service.py` gaining the keyword.

| Id | Tier | Input | Expected |
|---|---|---|---|
| T-1 | unit | keys `Nope`, `Described`, `TenantAccess`, a leaf non-root | `ValueError` naming key and reason |
| T-2 | unit | keys abstract parent of `Shelf`; `Library` (tenant root) | accepted; rules selected for `Shelf` / `Library` |
| T-3 | unit | rules on parent and on `Shelf`, three in all | run parent first, list order, first refusal stops |
| T-4 | unit | sync/async refusal, `ValidationError`, `KeyError`, partial, value returned, async raise after await | as the matrix |
| T-5 | unit | root typed `Shelf`+`SpecialShelf`; `Shelf`+`Book` | rules of `SpecialShelf`; 422 naming both |
| T-6 | unit | reader with `may_read` false / true; literal; absent; collected earlier; collected later; removed earlier | empty / types / empty no query / empty / types / empty / stored types |
| T-7 | unit | reader's store raises `StoreUnavailable` | passes unwrapped |
| T-8 | unit | no rules; a replace | no extra `get_graph` / `heads` call (spy) |
| T-9 | unit | rule on a class under workflow | sees the state `keep_state` kept |
| T-10 | unit | stored `old` made undecodable | `RuntimeError` naming the aggregate |
| T-11 | unit | stale replace refused / accepted | `InvalidBody` / `Conflict` at commit |
| A-1 | API | spec "a refused create" | 422 with the message; listing unchanged |
| A-2 | API | spec "a refused replace" | 422; ETag unchanged |
| A-3 | API | spec "a derived class", "an async rule reads a referenced class" | 422 |
| A-4 | API | spec "a reference the writer may not read" | the rule sees empty |
| A-5 | API | spec "a write that is not the generic API" (a unit of work) and a transition through `kit.collaboration` | `InvalidBody`; the transition's reader judged by the caller |
| A-6 | API | spec "a class name that is not a root" | the app refuses to build, naming it |
| A-7 | API | spec "no validators"; tenant-root PUT with a rule on `Library` | as before; 422 |

No `.feature` file: root-validator coverage is unit tier today, and this change follows it.

## Risks / Trade-offs

- **RISK-1** (owner accepted, DEC-4): a broken rule blocks every write of its class, transitions and
  bus handlers included. Likelihood medium, impact high for the consumer. The error names the rule.
- **RISK-2**: a write with no caller reads every class (PD-4); a rule's message could then name a
  class the human behind a bus message may not read. Likelihood low. Accepted; documented.
- **RISK-3**: `heads` per reader call is one query; N members make N queries. Accepted at this
  appetite; a batch method is a follow-up if measured.
- **RISK-4**: system and application sessions share the guard; a rule on an application-level root
  runs there too. Intended; documented.
- **RISK-5**: a rule refusing the tenant root on create leaves a database and bucket for the sweep
  (PD-8). Accepted; documented with the advice to use `root_validators` for such rules.

## Delivery decisions

Taken by the lead during delivery (R-0007); the developer may overrule any of them.

- **D-1** The reader asks `session.not_aggregates` before `may_read`, not after (PD-5's order).
  Both answer the same empty set; this way the caller's check is never called on a literal or a
  malformed IRI.
- **D-2** The API tier does not test "a derived class" (A-3): the toy schema has no abstract
  parent of a root, and adding one is a schema change for one test. The unit tier proves it (T-2,
  T-5, on a small inline schema `Item` > `Shelf` > `SpecialShelf`). Recorded under the floor.
- **D-3** Shapes the PLAN left open: `AggregateValidators(view, mapping, folder)` with `folder`
  required (the root and toolkit checks need it; the kit passes `schema.parent`);
  `select(root_iri, type_iris) -> (class name, rules) | None`; `model_class(type_iris)` for the
  stored `old`, chosen by PD-3's rule whether or not the stored class has rules;
  `ServiceKit.readable_by(caller, access)` builds the `may_read` the router and
  `kit.collaboration` pass; `kit.collaboration` opens `tenancy.tenant_session(..., may_read=)`
  directly, since `kit.session` takes no `may_read`.
- **D-4** `install_service`'s default for `aggregate_validators` is `{}`, as `stores` already is;
  it is never mutated.
- **D-5** Review: one L2+L3 pass, as `tasks.md` §2 sets for this one-stage SMALL EPIC (P-0005).
- **D-6** Four test doubles of `Tenancy.tenant_session` under `tests/unit/api` gained the
  `may_read` keyword. Nothing flags a stale double when a port gains a keyword; a shared double is
  a follow-up, not this EPIC.
- **D-7** Review (one L2+L3 pass): 0 Critical, 1 Warning, 4 Suggestions. The lead raises W1 to
  Critical C1: the reader named only the consumer's own root classes, so a readable aggregate of a
  toolkit class (a comment) answered empty, against the spec's "SHALL give the classes of a stored
  aggregate" and PD-5's "the view's class IRI → name map". Fixed in one pass: the reader maps over
  every class of the view.
- **D-8** Under the floor (not fixed in this EPIC):
  - S1: `_decoded_stored` narrows `self._validators` with an `assert`; harmless while its one
    caller checks first.
  - S2: the T-6 row "a member added later in the same unit of work" is tested only as "absent"; the
    code path is the same (nothing collected, nothing stored).
  - S3: with an empty mapping the kit still builds `AggregateValidators`, so each guarded write
    scans its triples for root types; no decode and no read (G-4 holds).
  - S4: no test for a rule refusing the tenant root on create (PD-8, RISK-5); the refusal path is
    the guard's, tested by A-7's tenant-root PUT.
- **D-9** Automated security review flagged the reader's fail-open when a session has no
  `may_read`. That is PD-4 and RISK-2, accepted by the owner: every HTTP write that holds a caller
  passes `may_read` (create, replace, tenant-root PUT, rename, `kit.collaboration`), and the
  sessions opened without it only read, remove (no rule runs), or write as the toolkit. No change.
  It flagged too that, after C1, the reader reports any stored class, so a client might assert a
  type to fool a rule. It cannot over HTTP: `Documents` refuses a root with an `rdf:type` outside
  the route class's family, and a tenant session refuses application types; code that writes
  through a unit of work is the consumer's own, trusted. No change.

### After the merge: the floor fixed (follow-up PR, the developer's "fix everything")

- **D-10** S1 to S4 of D-8 are fixed. S1: `_decoded_stored` takes the narrowed validators, no
  `assert`. S2: two real tests of a root added later and earlier in one unit of work (a plain
  reference, since a collection root refuses unstored members). S3: `AggregateValidators.has_rules`
  lets the guard return before reading root types when the mapping is empty. S4's test found
  PD-8, RISK-5 and the error-matrix row wrong: a rule refusing the tenant root on create is a 422
  and `Tenancy.create` drops the database and bucket it made (its `_drop_made` cleanup); only a
  drop that itself fails leaves them for the start-up sweep. The code was right; the test and
  `user-manual/access.adoc` now say so, and PD-8, RISK-5 and that row are superseded by this
  entry.
