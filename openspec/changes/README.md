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

1. **`release-pipeline`**: cheap, and it lets consumers pin a version before later EPICs change the
   public API.
2. **`test-profiling`**: cheap; knowing where the 5 minutes go keeps every later EPIC's checks fast.
3. **`live-tenant-sweep`**: small, self-contained, and closes a known data leak inside tenants.
4. **`cross-aggregate-unique-keys`**: medium, contained in the commit; it states the atomicity a
   store must offer, which `second-store` then puts into its descriptor.
5. **`second-store`** before **`schema-migrations`** and **`aggregate-events`**: both rely on what a
   store guarantees (atomic multi-operation updates), and doing the store first avoids writing them twice.
6. **`schema-migrations`**: needed as soon as consumers hold data across schema changes.
7. **`typescript-client`**, **`graphql-read-api`**, **`aggregate-events`**: each waits for a named
   client need (their seeds ask for one first).
8. **`fine-grained-access`** last: it must cover every read path that exists (REST, GraphQL, events),
   and its OpenFGA stage reopens D-4, the developer's call.
