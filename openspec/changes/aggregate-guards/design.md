# Design: aggregate-guards

> Derives from: EPIC `aggregate-guards` (`proposal.md`: #305, #309). Its DEC-1 to DEC-7 are cited
> here, not restated. The delivery decisions below are D-n, each a heading (`design.md#d-1`, …).

## Context

Code facts, read on `develop` at `f9f6fa74` and checked by the gate's attack (run 1):

- **The reader.** `AggregateReader` (`aggregate_validators.py` l.29) has `classes_of` only.
  - `_Reader` (l.119) holds the session, the context and the class names. It has no mapper.
  - It answers from `GuardContext.collected` first, then from `session.heads`.
  - An IRI that `may_read` refuses is answered as unknown, and an IRI foreign to the tenant is
    answered without a query.
  - `AggregateValidators.reader(session, context)` builds a new reader for each guarded write.
- **Decoding.** `WriteGuards` holds the mapper and the models (`write_guards.py` l.81-82).
  - `_decoded_new` decodes a write's triples with no tracking (l.149).
  - `_decoded_stored` (l.154) decodes a stored root from `session.get_graph(iri)`, which gives
    the graph, its tracking and its version. That version is the same token the commit's
    version guards and `heads` use.
- **The context.** `GuardContext` (`session.py` l.521) is a frozen dataclass with `collected`
  (adds and replaces only) and `rely_on`.
  - `_rely_on` raises `Conflict` if the same graph is already relied on at another version
    (l.1343-1345).
  - Relying on a graph that the same transaction later replaces or removes adds a consistent
    guard (l.1763-1765).
- **Removes.**
  - `Transaction.add` and `Transaction.replace` call `session._write_guards.prepare(...)` when the
    session has guards (l.1384, l.1420). `Transaction.remove` (l.1465) never calls it.
  - `_stored` returns the version and the first class only (l.705).
  - Replace answers a stale `If-Match` that a guard refuses as a version conflict, not as the
    guard's refusal (PD-32, l.1430-1434).
- **Who removes through a transaction:**
  - the generic route: `Aggregates.remove` (`aggregates.py` l.140-163) opens `tenant_session`
    **without `may_read`**, while add and replace pass it (l.93, l.130; `router.py` l.182, l.217
    vs l.237)
  - file removal (`file_removal.py` l.51)
  - a unit of work (`mapper.py` l.490)
  - a collection's cascade (`reference_collections.py` l.265-269)
  - the system database's access records (`tenancy.py` l.931), whose session carries the guards
    (l.207, l.918)
  - Comment records are dropped inside `remove_parts` (`_DROP_DEPENDENTS`, l.203-210), with no
    `Transaction.remove`.
- **No session.** Restore and migrations open no session: migrations write with `store.update`
  (`migrations.py` l.421), and `tenant_dump.py` opens none.
- **The port's implementers.** `WriteGuards`, and the test double `Recording` in
  `tests/unit/persistence/test_session_transaction.py` (l.650-658), whose test at l.661-669 removes
  with it set. `WriteGuard` and `GuardContext` are not public exports. `testkit/fakes.py` only
  passes `guards=` through (l.363, l.389).
- **Errors.** `run_aggregate_validators` lets `InvalidBody`, `ValidationError`, `StoreUnavailable`
  and `DatabaseGone` pass, and wraps anything else, `Conflict` included, in `RuntimeError`
  (l.173-178). `problems.py` maps `Conflict` to 409 and keeps the message (l.96, l.258).

## Goals / Non-Goals

**Goals:** the issues' acceptance criteria and the owner's four edge scenarios (`inputs/qa.md`),
each as a test that fails first.
**Non-Goals:** the EPIC's No-gos.

## Decisions

### D-1

`_Reader.aggregate(iri)` (DEC-1, DEC-6) works in this order:

1. `not_aggregates`, or `may_read` refuses: return None, with no query.
2. The IRI is in `context.removed`: return None.
3. The IRI is in `context.read_cache`: return a deep copy of the cached model.
4. The IRI is in `context.collected`: decode the collected triples with no tracking, as
   `_decoded_new` does, under the model class of their root types.
5. Otherwise, `session.get_graph(iri)`; `NotFound` gives None. Decode with the tracking, then
   call `context.rely_on(iri, version)`.
6. Cache the result under the IRI and return a deep copy.

Decoding reaches the reader as a function. `WriteGuards` builds the reader as
`validators.reader(session, context, decode)`, where
`decode(name, iri, graph, tracked) -> BaseModel` wraps `mapper.from_graph` and `models.named`.
`AggregateValidators.reader` and `_Reader.__init__` gain that parameter.

### D-2

`GuardContext` gains two fields (DEC-3, DEC-6). Both live on the `Transaction` and are passed
into the context by `_context()`:

- `removed: frozenset[str]`: the roots this transaction has collected as removals so far.
- `read_cache: MutableMapping[str, BaseModel]`.

`Transaction.add`, `replace` and `remove` pop the IRI's cache entry when they collect it.
`classes_of` answers empty for a removed IRI too, so the two reads agree.

### D-3

A model that cannot be decoded raises `RuntimeError` (500), whether it is stored or collected:

- a stored aggregate, because the client cannot fix stored data;
- collected triples, because they come from a write this transaction already made, so it is a bug
  in the caller's code.

An IRI whose types name no single root class gives None, as an unknown aggregate does.

### D-4

`run_aggregate_validators` also lets `Conflict` pass. A `rely_on` clash inside a rule (E6b) is then
the 409 it is, not a 500. The write rules' contract is otherwise unchanged.

### D-5

The `WriteGuard` port gains `async def prepare_remove(session, iri, if_version, context) -> None`
(DEC-4, DEC-5). `Transaction.remove` calls it when the session has guards, after `_claim` and
`_stored` and before `remove_parts`, so a refusal collects nothing. `WriteGuards.prepare_remove`
works in this order:

1. Return at once when there are no delete validators or they have no rules. No read: G-4, and
   the system database's removes.
2. Otherwise, `session.get_graph(iri)` once. Its root types select the rules, through
   `DeleteValidators.select` (the same chain logic as `AggregateValidators`).
3. When a rule applies, decode the same graph as `old`, build the reader (D-1), and call
   `run_delete_validators(rules, old, principal, reader)`.
4. If a rule raises `Conflict` and the stored version is not `if_version`, raise the version
   conflict instead (`changed_text`), as PD-32 does for replace (E17).

`run_delete_validators` lets `Conflict`, `StoreUnavailable` and `DatabaseGone` pass. Anything
else, `InvalidBody` included, is `RuntimeError` naming the rule. A non-None result is a
`TypeError`.

The test double `Recording` gains a `prepare_remove` that records the call. `WriteGuard` is not
public, so no consumer implements it.

### D-6

`DeleteValidators` shares the key checks and the chain building with `AggregateValidators`,
through the existing module functions (`_checked_roots`, `_chain`, `_gather`). There is no base
class.

- `DeleteValidator = Callable[[BaseModel, Principal, AggregateReader], Awaitable[None] | None]`.
- `ServiceKit` and `install_service` take
  `delete_validators: Mapping[str, Sequence[DeleteValidator]] = {}`.
- `WriteGuards` takes `delete_validators=DeleteValidators(...)`.
- Start-up refuses a bad key, naming it.

### D-7

The generic delete passes the caller's read access. `Aggregates.remove` takes
`may_read: Callable[[str], bool] | None = None` (the type `add` and `replace` use) and opens its `tenant_session` with it, and the route passes
`self._kit.readable_by(caller, access)`, as add and replace do. A delete rule's reader then hides
what the caller may not read (E2).

### D-8

Comment records dropped inside `remove_parts` run no delete rules (DEC-5's exemption). They are
toolkit `Annotation` records, which no key can name.

## Delivery decisions

### D-9

Stage 1 impact (lead, 2026-11-24): GitNexus rates `GuardContext` CRITICAL (80 direct), but every
edge is an import of `session.py`. Three sites construct it: `Transaction._context` and the test
helpers in `test_aggregate_validators.py` and `test_write_guards.py`. `removed` and `read_cache`
take defaults (an empty frozenset, a fresh dict), so the helpers stay valid. Not escalated.

### D-10

`_Reader.__init__` takes `model_class` (the bound `AggregateValidators.model_class`) besides
`decode`, so D-1 step 4 can name the class of collected triples without the reader holding the
schema view. An IRI added back after a remove in the same transaction leaves `removed`
(lead-fixed in the stage 1 commit).

### D-11

Stage 1 review (L2+L3, one pass): 8 findings, 0 Critical as labelled. Accepted:

- **R1-W1, re-labelled Critical:** the old test
  `test_an_aggregate_removed_earlier_in_the_transaction_still_answers_with_its_stored_types`
  asserted the `classes_of` contract the spec delta replaces, passing only because its helper
  builds an empty context. A suite that asserts a withdrawn contract misleads its readers. Deleted
  (lead-fixed), and its scenario-map row with it; T5 covers the new behaviour.

Under the floor:

- R1-W2: no test that a replace drops the read cache entry.
- R1-W3: no test for add, remove, add of one IRI (the D-10 discard).
- R1-W4: no test for E5 (types that name no single class) or E8 (a remove after a read).
- R1-W5: T4 asserts on `Transaction._relied`, private state.
- R1-S6: D-1 named one new `_Reader` parameter; D-10 records the second.
- R1-S7: `access.adoc` could say a missing aggregate is not cached and its absence not relied on.
- R1-S8: `_Reader` mutates the context's `read_cache` by design (D-2); no action.

## Algorithm / approach

### Stage 1, #305: the reader hands over an aggregate

Tests first, in two files:

- `tests/unit/collaboration/test_aggregate_validators.py`: the reader, with an in-memory session,
  as its existing tests use.
- `tests/unit/api/test_aggregate_validators_api.py`: through the kit and the generic route, on
  the toy.

| T | Case |
|---|---|
| T1 (issue) | A rule on `Loan` reads the `Book` it names, `(await reader.aggregate(b)).title`, and refuses when the title is "forbidden". The create gets 422; another book gets 201. |
| T2 (issue) | The writer may not read the book: `aggregate` gives None, as for a missing book. |
| T3 (issue) | The existing `classes_of` tests pass unchanged. |
| T4 | The book was added in the same unit of work: `aggregate` gives it as collected, and no `rely_on` is recorded. |
| T5 | The book was removed earlier in the same transaction: `aggregate` gives None, and `classes_of` gives empty. |
| T6 | Stale read: the rule reads the stored book at v1, and the book is replaced (v2) before the commit applies. The commit fails with the `Conflict` naming the book. Unit test, plus one integration test in `tests/integration/store/test_transaction.py`. |
| T6b | A nesting collection guard relied on a book at one version, and the rule reads a newer one: 409, not 500 (D-4). |
| T7 | Two rules read the same book in one write: the store is read once (a counting fake). |
| T7b | Collected triples that do not decode: `RuntimeError` (D-3). |

Worked example, in the toy's terms:

```python
async def due_after_publication(old, new: Loan, who, reader):
    book = await reader.aggregate(new.lends)
    if book is not None and book.published and new.due < book.published:
        raise InvalidBody("a loan cannot be due before the book was published")
```

### Stage 2, #309: delete rules

Tests first, in `tests/unit/collaboration/test_write_guards.py` (`prepare_remove`),
`tests/unit/api/test_aggregate_validators_api.py` (the kit and the route) and
`tests/unit/persistence/test_session_transaction.py` (`Recording`):

| T | Case |
|---|---|
| T8 (issue) | A delete rule on `Book` refuses while `old.status == "on_loan"`. `DELETE` gets 409 with the rule's message, and the book is still stored at its version. |
| T9 | A book with any other status: `DELETE` gets 204. |
| T10 | A rule registered on a parent class runs for a derived root. |
| T11 (cascade) | A collection's members are removed through a unit of work, and one member's rule refuses: the whole commit is refused and nothing is removed. |
| T12 | A rule raises `InvalidBody`: `RuntimeError` naming the rule. A rule returns a value: `TypeError`. |
| T13 | A bad key (not a class, a mixin, a toolkit class, or no root derives from it) stops start-up, naming the key. |
| T14 | With no delete rules, a remove reads nothing (a counting fake), including the system database's remove. |
| T15 | The caller may not read a book the rule asks about: the reader gives None on the delete path too (D-7). |
| T16 | A stale `If-Match` and a refusing rule: the version conflict wins (D-5, E17). |
| T17 | `Recording` sees `prepare_remove`, and the existing remove test still passes. |

Worked example:

```python
from rdf_persistence import Conflict

def not_while_on_loan(old: Book, who, reader):
    if old.status == "on_loan":
        raise Conflict(f"{old.id} is on loan; return it before deleting it")
```

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Hand a rule raw triples or a dict | The generated model | PD-24 |
| Read B through a new session | The writer's session and transaction | Access, and the issue's "same transaction" |
| Pass `new=None` to the write rules | A separate delete registry | DEC-4: no breaking change |
| Check delete rules in the route | `Transaction.remove` | DEC-5: every remove, cascades included |
| `getattr(guard, "prepare_remove", None)` | Extend the port and its implementers | The port is internal; a soft call hides a missing implementation |
| A class hierarchy for the two registries | Shared module functions | One implementation each |

## Error matrix

| # | Input | Detection | Response | Fallback |
|---|---|---|---|---|
| E1 | `aggregate(iri)` foreign to the tenant | `not_aggregates` | None, no query | n/a |
| E2 | `aggregate(iri)` the writer may not read (write and delete paths) | `may_read` (D-7) | None | n/a |
| E3 | `aggregate(iri)` of a missing aggregate | `get_graph` → `NotFound` | None | n/a |
| E4 | stored or collected B does not decode | `from_graph` `ValueError` | `RuntimeError` → 500 (D-3) | fix the data or the code |
| E5 | B's types name no single root class | `model_class` None | None | n/a |
| E6 | B changes after the read, before the commit | `rely_on` guard at commit | `Conflict` 409 naming B; nothing written | the client retries |
| E6b | B already relied on at another version in this transaction | `_rely_on` raises `Conflict` | passes `run_aggregate_validators` → 409 (D-4) | retry |
| E7 | B removed earlier in the transaction | `context.removed` | None | n/a |
| E8 | B removed later in the transaction, after A's rule read it | none (DEC-3) | A is committed | RISK-5 |
| E9 | a rule mutates the model it got | deep copy | no effect elsewhere | n/a |
| E10 | a delete rule refuses | `Conflict` from the rule | 409 with its message; nothing removed | change the state first |
| E11 | a delete rule raises anything else | `run_delete_validators` | `RuntimeError` naming the rule → 500 | fix the rule |
| E12 | a delete rule returns non-None | as E11 | `TypeError` | fix the rule |
| E13 | a cascade part refuses | as E10, inside the cascade's transaction | the whole commit refused, with the part's message | RISK-2 |
| E14 | a bad `delete_validators` key | `_check_key` at start-up | `ValueError` naming the key | fix the key |
| E15 | a remove with no delete rules | `has_rules` false | nothing read | n/a |
| E16 | the store is down while a rule reads | `get_graph` | `StoreUnavailable` passes (503) | retry |
| E17 | a stale `If-Match` and a refusing rule | stored version ≠ `if_version` (D-5) | the version conflict (409), not the rule's | re-read, retry |
| E18 | comment records dropped with their resource | not a `Transaction.remove` (D-8) | no rule runs | n/a |

Idempotency: the guards read and refuse; they never write. A refused commit leaves nothing, so a
retry is a fresh attempt. A conflicted commit (E6, E17) is safe to retry once the client has
re-read.

## Risks / Trade-offs

- **RISK-1 (a hot B causes 409s).**
  - Likely where many As name one B and B is edited often. The cost is extra client retries; no
    data is at risk.
  - Mitigation: E6's conflict names B, and the docs say that a rule reading B makes A's write
    depend on B's version.
- **RISK-2 (a cascade is blocked).**
  - Possible where a consumer puts a delete rule on a part class. The parent's delete is then
    refused for a reason about the part.
  - Mitigation: the docs say a rule's message names its root, and T11 proves the behaviour.
- **RISK-3 (inverse edits are not rerun).**
  - Certain by design (No-gos): the order can be broken from B's side.
  - Mitigation: the docs show the symmetric rule on B.
- **RISK-4 (decode cost).**
  - Possible for rules that read many aggregates.
  - Mitigation: the per-transaction cache (D-1, D-2) and T7.
- **RISK-5 (a remove after a read).**
  - Unlikely: it needs a unit of work that writes A and then removes B.
  - Accepted (DEC-3), and documented in the reader's docstring.

## Open Questions

None.
