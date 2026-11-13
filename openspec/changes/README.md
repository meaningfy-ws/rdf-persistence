# In-flight changes

Each in-flight unit of work is a directory `openspec/changes/<id>/` carrying the spine artifacts:

| File / dir | Meaningfy noun | Authored with |
|---|---|---|
| `proposal.md` | **EPIC** (the Shape-Up work shape) | `/opsx:propose` (or `/opsx:explore` first) |
| `design.md` + `tasks.md` | **PLAN** (clarity gate scores the pair ≥9/10) | `/opsx:propose` / `epic-planning` |
| `specs/<cap>/spec.md` | normative requirements (SHALL + GWT deltas) | the proposal's Capabilities |
| `inputs/` | **seed inputs** (briefs, notes, codebase analysis) | preserved, never groomed |

Implement with `/opsx:apply` (tracks `tasks.md`). `/opsx:sync` / `/opsx:archive` merge the spec
deltas into `openspec/specs/` (the durable truth) and move the change under `archive/`.

**Golden thread (cite your parent):** `tasks.md` cites its EPIC id on the first line; specs cite
their capability; commits reference the change id.


## The backlog, in order (reshaped 2026-11-12)

Reshaped by the lead on 2026-11-12, with the developer away and asked to decide: the open issues
come first (#72, #76, #78–#81, #83), then the candidate EPICs. Each EPIC owns one concern; where
two met, one now names the other as a dependency and the shared piece lives in exactly one of them
(the table's last column). Delivered work is under `archive/`; `test-profiling` was deleted
(superseded by `test-lanes`, 2026-11-09).

"PLAN" means `design.md` + `tasks.md` exist. "Gated" means a fresh reviewer scored the PLAN ≥9/10
after an attack; until then it is the planner's own score.

| # | Id | Appetite | Issues | PLAN | Depends on | Owns (and nobody else) |
|---|---|---|---|---|---|---|
| 1 | `boundary-owned-hint` | TINY | #72 | yes | none | the REFERENCE problem's fix text |
| 2 | `release-pipeline` | SMALL | none | yes | none | versioning, release notes, the 0.2.0 cut |
| 3 | `atomic-commit` | MEDIUM (2 stages) | #83, #76 | yes | none | `Session.transaction()`: one guarded update request for many aggregates; `UnitOfWork.remove`/`version`; the root limit and batch mode; the tenant-root comparison |
| 4 | `collaboration-and-reference-collections` | LARGE (4 stages) | #78, #79, #80, #81 | yes | 3 | reverse references, reference collections, discussion, workflow, the `annotate` action |
| 5 | `cross-aggregate-unique-keys` | MEDIUM | none | yes | 3 | key guards added to the transaction; `KeyConflict` |
| 6 | `tenant-dump-restore` | MEDIUM | none | yes | none | the dump format (manifest with schema version), restore into a new tenant |
| 7 | `app-level-data` | MEDIUM | none | no | none | the application database and its aggregates |
| 8 | `tenant-stores` | MEDIUM | none | no | 6 (copies are dump + restore) | several wired stores; the access record names a tenant's store |
| 9 | `message-bus` | MEDIUM | none | no | 3 (events leave only after the all-or-nothing commit) | `Event`/`Command` models, `MessageBus`, handlers, `bootstrap`, the unit of work's events (in process) |
| 10 | `aggregate-events` | LARGE | none | no | 3, 9 (outbox = one more transaction operation; stores 9's events) | outbox, relay, `EventBus` port on FastStream (Redis Streams first), incoming events into the bus, SSE |
| 11 | `schema-migrations` | LARGE | none | no | 6 (reads the dump's schema version) | schema version per tenant, automatic migrations |
| 12 | `second-store` | MEDIUM | none | no | 3, 5 (the descriptor states their atomicity need) | GraphDB (confirmed), the capability descriptor |
| 13 | `typescript-client` | LARGE | none | no | 2 | the generated client |
| 14 | `fine-grained-access` | VERY LARGE (staged) | none | no | 10 | OpenFGA, property- and triple-level access |
| — | `graphql-read-api` | LARGE | none | no | — | deferred by the developer (2026-11-06) |

### Why this order

1. **#72 and the release first, as fillers.** Both are independent and small. Cutting 0.2.0
   (pending since 2026-11-10) before `atomic-commit` gives consumers a version tag from before the
   commit behaviour change.
2. **`atomic-commit` before every other feature.** MWB2's v2-02 waits on it, and three EPICs write
   several aggregates at once: the collaboration EPIC (cascade delete, a transition with its
   record and comment, delete with comments), unique keys (their guard joins the transaction's
   guard) and events (the outbox insert joins the transaction). Issue #76 is folded in: it fixes
   the same hub (`Session._graph`), so one impact gate covers both.
3. **The collaboration EPIC next**: the consumer's shaped model waits on it. Its stage order was
   changed to reverse references, collections, discussion, workflow, because a transition posts
   its comment into the thread. The version token on read (its former DEC-8) moved to
   `atomic-commit`.
4. **Unique keys** after it: no consumer is waiting for them, and they reuse the transaction.
5. **Tenant governance** (dump/restore, application data, several stores): the developer's own need
   of 2026-11-10, in the order that lets each reuse the one before.
6. **Message bus, events, then migrations.** The developer confirmed the events need on
   2026-11-13 and widened it to event-driven applications as in Cosmic Python, so the in-process
   layer (`message-bus`) comes first and the broker layer (`aggregate-events`) builds on it;
   migrations become pressing once consumers keep data across schema changes. Dump/restore's
   manifest records the schema version that migrations will read.
7. **`second-store`, the client, fine-grained access** last: no consumer need yet.

### Readiness and what the developer reviews (2026-11-13)

Every PLAN below was attacked and clarity-gated by a reviewer who did not write it; the findings
are recorded in the PLAN's last gate PD. "Ready" means it can go to an epic session now; the
review items are decisions the lead took on the developer's behalf and the developer may overrule.

| Change | Gate | Ready? | Review first |
|---|---|---|---|
| `boundary-owned-hint` | 9 | ready | none |
| `release-pipeline` | 8 → 9 | ready | PD-1: `main` is moved to the tag by hand after each release (`GITHUB_TOKEN` cannot push workflow changes); PD-4: CHANGELOG kept by hand, release-please writes only the notes; PD-5: PyPI jobs removed; PD-9: 0.2.0 cut by the first run |
| `atomic-commit` | 8 → 8.5 → fixed | ready | DEC-4: default limit 500 roots and batch mode built now; the all-or-nothing behaviour change ships without a flag; #76 folded in |
| `cross-aggregate-unique-keys` | 8 → 9 | ready after `atomic-commit` | PD-2: an unscoped `unique_keys` declared on a root now fails generation; PD-11: duplicates are found by an operator call `key_duplicates()`, not by generation (generation never sees data); PD-8/PD-9: 409 `key-conflict`, version conflicts reported first |
| `tenant-dump-restore` | 7.5 → 9 | ready | DEC-1: restore always into a new tenant; DEC-2: the tenant id is rewritten in every IRI, policies that glue the id to other characters are refused; DEC-4: grants not dumped, the restorer is the only grantee |
| `collaboration-and-reference-collections` | 8 → 8.5 → fixed | ready after `atomic-commit` | a `Collaboration` service opened from the kit (not `session.*` methods); comments and transition records are toolkit-written aggregates no generic route serves; replies target the aggregate; undefined transition → `Conflict`, state changed by a plain write → `Forbidden`; deleting a resource deletes its comments and records |

Shaped, not planned (PLAN at the start of their epic session): `app-level-data`, `tenant-stores`,
`second-store`, `message-bus`, `aggregate-events`, `schema-migrations`, `typescript-client`,
`fine-grained-access`. Their open questions are answered as leader's choices in each proposal and
`inputs/seed.md`. The three that needed the developer were answered on 2026-11-13:

- Restore under the original tenant IRI or across IRI policies: not now (`tenant-dump-restore`
  DEC-1 confirmed).
- GraphDB Free as the second store: yes (`second-store` DEC-5 confirmed).
- Events: yes, and more broadly event-driven applications as in Cosmic Python, adopting libraries
  where needed. `aggregate-events` was split: `message-bus` (in process, hand-rolled as in the
  book) and `aggregate-events` (outbox, FastStream with Redis Streams first, SSE). Review the
  library choices: `message-bus` DEC-4, `aggregate-events` DEC-6.
