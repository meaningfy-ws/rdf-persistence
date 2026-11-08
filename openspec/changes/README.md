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

## Planned EPICs (from GitHub issues)

Shaped and planned on 2026-11-08 from the consumer's (MWB2) issues; the developer answered the open
questions (each change's `inputs/seed.md`). Each has its PLAN (`design.md` + `tasks.md`).

| Id | Issue | Appetite | Why, in one line | Depends on |
|---|---|---|---|---|
| `iri-policy` | #26 | LARGE (two stages) | IRIs have one fixed shape tied to the API path; MWB2's persistent URI policy cannot be expressed. Blocks MWB2's first build EPIC. | none |

**Order:** `iri-policy` stage 1, then stage 2. `testkit-wait-until` (#24) and `generation-fix-hint`
(#25) were delivered and archived on 2026-11-08 (`archive/2026-11-08-*`).

## Candidate EPICs

Shaped on 2026-11-06 from the v1 future list (`docs/modules/ROOT/pages/questions.adoc`, "What could
strengthen it in the future"), `docs/modules/ROOT/pages/architecture/open-decisions.adoc`, and the
No-gos and Rabbit-holes of the archived `toolkit-v1-foundation` proposal. Each holds a
`proposal.md` (the EPIC), its spec deltas, and `inputs/seed.md` with the open questions. None is
planned: no `design.md` or `tasks.md` exists until the developer answers its questions.

| Id | Appetite | Why, in one line | Depends on |
|---|---|---|---|
| `release-pipeline` | SMALL | The release workflow exists but has never released (it looks for releases on `main` while running on `develop`); consumers can only install `develop`. | none |
| `test-profiling` | TINY | The check timings are rough wall-clock times; nobody knows which tests take the 5 minutes. | none |
| `live-tenant-sweep` | SMALL | Loaded graphs no commit names and blobs no aggregate names stay in a live tenant until it is deleted. | none |
| `cross-aggregate-unique-keys` | MEDIUM | `unique_keys` hold only inside one aggregate; two concurrent creates with one key both commit. | none; shares the atomic-update question with `second-store` |
| `second-store` | LARGE | The `Store` port assumes Fuseki's database-per-tenant administration; Oxigraph or Virtuoso cannot back it. | soft: after `cross-aggregate-unique-keys` (its guard sets an atomicity need the descriptor must state) |
| `schema-migrations` | LARGE | No schema version is stored; data under an old schema surfaces only when a replace fails its shapes. | soft: `second-store` (migrations should run on every supported store) |
| `aggregate-events` | LARGE | Nothing records that a commit happened; a reaction to a change can only poll. | soft: `second-store` (the outbox relies on atomic updates) |
| `typescript-client` | LARGE | Types and the OpenAPI document are generated, but every client hand-writes its calls, versions and problem handling. | soft: `release-pipeline` (a versioned client pairs with a versioned server) |
| `graphql-read-api` | LARGE | Nested reads across aggregates take one REST call per aggregate; option C is the API's declared backup. | none |
| `fine-grained-access` | VERY LARGE (staged) | Access is per tenant and per aggregate; no property can be hidden, and OpenFGA is deferred by D-4. | soft: after `graphql-read-api` and `aggregate-events`, so property filtering covers every read path once |

### Suggested order, and why

Revised after the developer's answers (2026-11-06; recorded in each `inputs/seed.md`):

1. **`test-profiling`**: cheap, and the developer chose parallel tests and a fast/full CI split;
   every later EPIC's checks benefit.
2. **`live-tenant-sweep`**: small, self-contained, and closes a known data leak inside tenants
   (an operator command, a dry run by default).
3. **`cross-aggregate-unique-keys`**: medium, contained in the commit (a guard in the commit's own
   update); it states the atomicity a store must offer, which `second-store` then puts into its
   descriptor.
4. **`second-store`**: Tentris, Oxigraph and GraphDB compared behind a capability descriptor,
   before **`schema-migrations`** and **`aggregate-events`**, which both rely on what a store
   guarantees.
5. **`schema-migrations`**: automatic, on Strapi-inspired rules; needed as soon as consumers hold
   data across schema changes.
6. **`aggregate-events`**: an outbox, an `EventBus` port (Redis or RabbitMQ), and in-process
   plumbing (domain events and a message bus).
7. **`typescript-client`**: generated from the OpenAPI document.
8. **`fine-grained-access`**: stage 1 is OpenFGA per aggregate (D-4 reopened by the developer);
   property and triple level are later stages.
9. **`release-pipeline`**: consumers keep installing from `develop` for now, so it waits; v0.1.0
   was tagged by hand.

**Deferred:** `graphql-read-api`, by the developer. The preference is remembered in its seed.
