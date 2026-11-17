<!-- Parents: openspec/specs/rp-events ("Server-sent events respect access"); openspec/specs/rp-messages
     ("Every commit records one activity with its PROV events", "Activity records are kept");
     openspec/specs/rp-access ("Access is decided per tenant and per aggregate"); archived
     aggregate-events DEC-3, DEC-9, DEC-10 and message-bus DEC-10; archived soa-python-rdf-orm DEC-5
     (the reuse bar). Seeds: inputs/seed.md, ../manual-revision-notes/inputs/improvements.md (H),
     ../manual-revision-notes/inputs/analysis.md (§4.2, §4.3 item 5, §6 Q-4),
     ../manual-revision-notes/inputs/keep.md ("Live event delivery over SSE"),
     ../manual-revision-notes/inputs/answers-2026-11-17.md (Q-4). -->

# EPIC: A Linked Data Event Stream view of a tenant's history

> Shaped 2026-11-17 by the leader from the manual-revision-notes initiative (improvement H-1,
> question Q-4). The developer's answer to Q-4: "shape the epic, but this is low priority". Every DEC
> below is a leader's choice the developer may overrule. **EPIC only, not planned:** the PLAN
> (design.md, tasks.md) is derived at the start of its own epic session. Position: after the
> initiative's five changes (`manual-revision-notes`, `technical-models`, `otel-observability`,
> `generator-package`, `thematic-structure`); low priority; it depends on none of them and none
> depends on it. If it runs after `technical-models`, its new setting lands in the generated settings
> that change introduces; if it runs after `thematic-structure`, its modules go to the events theme.

**Golden-thread parent:** capability `rp-events` (a reader follows a tenant's changes, seeing only
what it may read) and `rp-messages` (one PROV activity per commit, kept). This EPIC adds a second
way to read the same history: a pull view a harvester walks page by page, beside the live push.

## Appetite

**MEDIUM.** One new read capability: a set of tenant routes publishing the provenance graph as an
LDES over TREE pages, its member class and shape in LinkML, an opt-in setting, and its tests up to
an end-to-end harvest. Neighbours touched lightly: the route installer, the settings, the docs. No
change to the commit, the relay, the outbox or server-sent events.

## Why

A tenant's history leaves the service in one way only: server-sent events, push with a 7-day
resume window (`rp-events`), then `event: reset`. A client that was away longer, or that wants the
whole history, has no route. European public-sector consumers replicate and synchronise datasets
with SEMIC's Linked Data Event Streams (LDES 1.0.0, 9 May 2026), built on the TREE hypermedia
specification (Draft CG Report, 20 June 2025); the research never considered it (analysis §4.2).
The history needed is already stored and kept forever (`rp-messages`), so the view costs no new
write. Python has no LDES library that passes the reuse bar (inputs/seed.md), so the toolkit
honours the specification with rdflib, as it does SPARQL and JSON-LD.

## Solution outline

A consumer turns the view on with one setting. Each tenant then publishes an `ldes:EventStream`
at `{public_url}{prefix}/{tenant_segment}/{t}/rp-ldes`. A harvester holding a token with `read`
on the tenant fetches the stream, follows its `tree:view` to a root node, and walks time-ordered
pages; each page lists the members of one hour. Each member says that one aggregate was created,
updated or removed by one activity at one time, with the version token, the class and the
activity: references only, never the aggregate's content. The harvester reads the content through
the existing routes, with its own rights. Pages older than a settle delay are immutable and
cacheable; the newest pages carry an `ETag` and a polling interval. Server-sent events stay as
they are, for live clients.

```text
GET /libraries/t1/rp-ldes                 ldes:EventStream, tree:view </libraries/t1/rp-ldes/view>,
                                          tree:shape, ldes:timestampPath, ldes:versionOfPath
GET /libraries/t1/rp-ldes/view            root node: one GreaterThanOrEqualTo/LessThan pair per day
GET /libraries/t1/rp-ldes/2026-11-17      day node: one pair per hour that has members
GET /libraries/t1/rp-ldes/2026-11-17T09   page: the members of 09:00 to 10:00 UTC the caller may
                                          read; ldes:immutable true once settled
```

## Key decisions

- **DEC-1** (leader's choice): **a view, computed on read**. The routes query the provenance graph
  of the tenant's database; a commit writes nothing new and no fragment is stored. Reason: the
  history is already kept and ordered by time; stored fragments would be a second copy to keep in
  step through commits, restores and migrations. Rejected: materialised pages written by the relay.
- **DEC-2** (leader's choice): **a member is one aggregate's change in one activity**, a version
  event: created (a generation alone), updated (a generation and an invalidation of the same
  aggregate) or removed (an invalidation alone), declared with `ldes:versionCreateObject`,
  `ldes:versionUpdateObject` and `ldes:versionDeleteObject`; `ldes:versionOfPath` names the
  aggregate, `ldes:timestampPath` the change's time (the activity's end, `prov:atTime`). It carries
  the aggregate's IRI, class and version token, the activity's IRI and class, and nothing the
  server-sent event of that change does not already carry. Reasons: LDES members must not change
  once published, and access is decided per aggregate (DEC-8), so a member about one aggregate is
  shown whole or not at all; a harvester gets LDES version semantics (latest state per aggregate)
  for free. Rejected: (a) the whole activity as the member, cut per caller as server-sent events do
  (one member IRI with different content per caller breaks immutability); (b) the whole activity,
  shown only when every part is readable (hides changes the caller may read); (c) snapshots of the
  aggregate's content (the store keeps only the current state; thin messages, aggregate-events
  DEC-9).
- **DEC-3** (leader's choice): a member's IRI is a name-based UUID IRI (`urn:uuid:`, version 5)
  derived from the activity's IRI and the aggregate's IRI, computed, never stored. Reason: the same
  member has the same IRI on every read, after a restore (which keeps activity IRIs) and on any
  deployment address. Rejected: an IRI under `public_url` (changes with the address); a stored IRI
  (a write per change, DEC-1).
- **DEC-4** (leader's choice): the member class is a LinkML class beside `Generation` and
  `Invalidation` in `rp_provenance.yaml`; its generated SHACL shape is the stream's `tree:shape`
  and members are built through its generated model (principle 2, P-0007). The stream, node and
  relation statements are TREE and LDES protocol terms, built with rdflib from constants next to
  their use (P-0009), not modelled in LinkML. Rejected: a LinkML schema of the TREE vocabulary (an
  external specification's terms, nothing of ours to generate).
- **DEC-5** (leader's choice): **fixed time buckets**: the root node relates to one node per UTC day
  that has members, a day node to one page per UTC hour that has members, each relation a
  `tree:GreaterThanOrEqualToRelation` and `tree:LessThanRelation` pair on the timestamp path with
  `tree:remainingItems`. The bucket widths are protocol constants, since page IRIs are made from
  them. Rejected: pages of N members (a boundary moves with every commit, so no page could be
  immutable); configurable widths (changing one breaks every harvested page IRI).
- **DEC-6** (leader's choice): a page is **immutable** (`ldes:immutable true` and `Cache-Control:
  private, immutable`) once its upper bound is older than a settle delay. Reason: a change's time
  is the service's clock at the end of the activity, taken before the store applies the commit, so
  a slow commit can land in a page after that page's hour. The delay exceeds the longest commit
  (the store's request timeout) plus a clock allowance, and is a deployment value in the central
  settings (P-0009). A page not yet settled carries an `ETag` and the stream an
  `ldes:pollingInterval`. Rejected: ordering by the store's `rp:pendingSince` (absent on records
  older than aggregate-events and on restored ones).
- **DEC-7** (leader's choice): **no retention policy** is declared: the stream is the full log,
  because activity records are kept (`rp-messages`). If records are ever pruned, the stream
  declares `ldes:startingFrom` in the change that prunes them.
- **DEC-8** (leader's choice): **access as for server-sent events** (aggregate-events DEC-3). Every
  route needs a verified caller with `read` on the tenant; a page lists a member only when the
  caller may read its aggregate, and the resource its activity used when it used one, decided by
  the same rule as server-sent events. Pages are per caller (`Cache-Control: private`). A member
  hidden from a caller when a page settled stays out of that caller's cached copy; a caller granted
  more rights re-harvests from the root. Rejected: an anonymous public stream (the toolkit has no
  anonymous access; that is `rp-access`'s decision, not this EPIC's).
- **DEC-9** (leader's choice): **opt in**. One setting turns the routes on, off by default; with it
  on, the service refuses to start without `public_url`, since an LDES names itself with absolute
  IRIs. The routes sit under the toolkit's reserved prefix as `rp-ldes`, beside `rp-events`, so no
  aggregate can shadow them. Server-sent events do not change (keep.md). Rejected: always on (a new
  read surface on every deployment that never asked for it).
- **DEC-10** (leader's choice): pages are RDF, Turtle by default, JSON-LD and the other RDF
  representations the service negotiates (`rp-service-api`; N-Quads and the rest arrive with
  `manual-revision-notes` Q-5) on request. No plain JSON for these routes.
- **DEC-11** (leader's choice): **the proof is a real harvest**. An end-to-end test runs the npm
  `ldes-client` (rdf-connect, pinned) against the toy library's stream and finds every change the
  caller may read and none it may not; members are validated against the generated shape with
  pySHACL. The client is a test tool only, never a dependency of the package (P-0008: no Python
  library exists to reuse; inputs/seed.md).
- **DEC-12** (developer, 2026-11-17, Q-4): low priority; the PLAN waits for its own epic session.

## Rabbit-holes

- **Late members.** DEC-6's settle delay is the only guard; the PLAN states the delay's floor from
  the store timeout and tests a commit that lands after its hour has ended.
- **Busy hours.** An hour with many thousands of changes makes a large page. The PLAN measures one
  on the toy library; splitting a page further is a later change, not this one.
- **Counting pages.** Listing the days and hours that have members is a grouped SPARQL query over
  the whole provenance graph at each root read; keep it one query, cache nothing.
- **Removed aggregates.** The access rule decides on an IRI whose aggregate may be gone; it must
  answer as it does for a server-sent event of the same removal.
- **Activities of a consumer's subclasses** (a `Transition`, a served command) still yield one
  member per aggregate; the activity's own slots stay out of the member (thin).
- **Principals in members.** The member carries what the server-sent event carries; whether a
  principal's IRI belongs in a public-sector harvest is the consumer's call, recorded in the docs.

## No-gos

- An LDES client, harvester or replicator in the package.
- A replication protocol, or writes through the stream.
- An LDES server product: no ingestion of foreign streams, no configurable fragmentation, no
  geospatial or string fragmentations, no search forms (`tree:search`), no `ldes:transactionPath`.
- Changes to the commit, the provenance record, the relay, the outbox or server-sent events.
- Anonymous or public access, or a new access action.
- A stream of the application database or the system database (tenants only, as server-sent
  events).
- Aggregate content in members (event-carried state).
- A retention policy or pruning of activity records.
- Any consumer term, model or code.

---

## What Changes

- `rdf_persistence/model/rp_provenance.yaml`: the member class (DEC-2, DEC-4); regenerated code
  and shapes.
- `rdf_persistence/model/service/rp_service.yaml` (or the generated settings of
  `technical-models`): the opt-in flag and the settle delay (DEC-6, DEC-9).
- `rdf_persistence/services/`: a module reading a tenant's days, hours and the changes of one hour
  from the provenance graph, deriving members and cutting them to what the caller may read.
- `rdf_persistence/entrypoints/`: the `rp-ldes` routes (stream, root, day, page) beside `sse.py`,
  installed only when the flag is on; the start-up check on `public_url`.
- `tests/`: unit and feature tests for buckets, members, immutability and access; an integration
  test validating members with pySHACL; an e2e harvest with the npm `ldes-client`.
- Docs: a how-to page on harvesting a tenant's history, its question in `questions.adoc`, the
  architecture page's building blocks.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rp-events`: a tenant's history can be harvested as a Linked Data Event Stream (ADDED, candidate).

## Impact

- New optional public routes `GET {prefix}/{tenant_segment}/{t}/rp-ldes` and below; off by default,
  so no deployment changes until a consumer opts in.
- Two new settings (the flag and the settle delay); with the flag on, `public_url` becomes required.
- No new runtime dependency; the e2e tier gains a pinned npm test tool.
- Each root read runs one grouped query over the tenant's provenance graph.
