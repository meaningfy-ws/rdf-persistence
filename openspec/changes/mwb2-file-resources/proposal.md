<!-- Parents: issues #54, #55, #56, #59, #60 (filed by mapping-workbench-v2, 2026-11-09), serving
     MWB2 changes v1-04 and v1-06 (D-12). Seeds, intake findings and the developer's answers:
     inputs/seed.md. -->

# EPIC: Let mapping-workbench-v2 keep project files on the toolkit

> Shaped 2026-11-09 from #54, #55, #56, #59, #60 (Q-1 to Q-8 in inputs/seed.md). PLAN
> (design.md + tasks.md) is derived at the start of the epic session.

**Golden-thread parents:** `rp-metamodel` (what a root must carry), `rp-service-api` (the generic routes and the OpenAPI document),
`rp-aggregate-store` (the session's reads and loaded graphs), `rp-file-store` (`StoredFile`),
`rp-testkit` (the conformance guards).

## Appetite

**MEDIUM**, two stages, one PR each. One new route option (DEC-2) and two new session reads
(DEC-4, DEC-5), with their tests and docs; generation and OpenAPI touched lightly. Existing
structure is reused: no new layer, port or dependency.

## Why

MWB2's v1-06 keeps project files (ontologies, test data, mapping files) as `StoredFile` roots and
cannot build it on the toolkit today:

- **It cannot create a file record** (#59): the generated Python makes a root's `description`
  required, while the JSON Schema and OpenAPI say it is optional. That is the toolkit's own rule
  (PD-11), applied to some outputs and not others, and no guard noticed.
- **It cannot trust file metadata** (#55): any caller with `modify` can change a stored file's
  checksum, or delete its record and leave the blob, through the generic routes.
- **It cannot read what it loaded or look aggregates up** (#56, #60) without writing SPARQL, which
  its rule (and ours for consumers) forbids.
- **Its web app's types do not compile** (#54): a listing filter on a multivalued slot points into
  another schema's property, and `openapi-typescript` renders that as invalid TypeScript.

#59 and #55 block v1-06's file API outright; #54 has a stopgap in MWB2 (S-90).

## Solution outline

- **Stage 1 — make file records buildable and trustworthy (#59, #55, #54).** A root's
  `description` is optional in every generated artefact, and a guard fails when the Python model
  and the JSON Schema disagree on whether a slot is required. A root can be marked so the toolkit
  serves its reads but not its generic writes; file roots are marked by default, and the consumer
  writes them through a session in its own routes. Listing filters carry their item type inline.
- **Stage 2 — read without SPARQL (#56, #60).** A session reads back a graph loaded for an
  aggregate, and finds a class's aggregates in the tenant by equality on slot values.

Outcome: MWB2 drops its S-90 stopgap and builds v1-06's file API, ontology browsing and
duplicate-name refusal on public toolkit calls only.

## Key decisions

- **DEC-1**: An aggregate root's `description` is optional in every generated artefact; `apply_defaults`
  no longer marks it required (the `rp_unlabelled` half of PD-11 stays). A conformance guard
  compares each generated Python field's required flag with the class's JSON Schema `required` and
  fails on a difference. Source: Q-1. Reason: the outputs disagree today, and MWB2 creates file
  records with no description. Rejected: required everywhere; a per-class opt-out annotation.
- **DEC-2**: A class annotation `rp_writes: service` leaves the generic `POST`, `PUT` and `DELETE`
  of that root unmounted (and out of the OpenAPI document); its `GET` and listing stay. A root that
  mixes in `StoredFile` has it by default. The consumer writes such roots through
  `kit.session(...)`. Source: Q-2. Reason: the record and its blob must change together, which only
  the consumer's own route can do. This is a deliberate step past the previous EPIC's no-go
  ("unmounting the generic routes", which was about tenant writes and validators, #49): it is
  per class and opt-in except for file roots. Rejected: opt-in only; making every `StoredFile`
  slot service-set (a generic `DELETE` would still orphan the blob).
- **DEC-3**: A listing filter's schema is the slot's item schema written inline (`type` and
  `format`, or a `$ref` to an enum's component), never a pointer into another schema's property.
  Source: #54's expected behaviour. Proven by a unit test and by `make typecheck-ts` running a
  pinned `openapi-typescript` on the toy service's OpenAPI and `tsc --strict` on the result (Q-6).
- **DEC-4**: `Session.loaded_graph(iri, graph_iri) -> rdflib.Graph` returns the triples of a graph
  loaded for the aggregate `iri`, read from the store; a graph IRI not loaded for that aggregate
  is `NotFound`; a caller who may not read the aggregate is refused as for any read. No paging.
  Source: Q-3. Rejected: returning the parsed graph from `load_graph` (readable only at upload).
- **DEC-5**: `Session.find(cls, **equals) -> list[str]` returns the IRIs of the tenant's aggregates
  of `cls` whose slots equal the given values (a multivalued slot: all values present, as in the
  listing), built from the listing plan the router already uses. An unknown slot name raises a
  clear error. Source: Q-4. Rejected: making `ListPlan` and `kit.listings` public.

## Rabbit-holes

- **Where the PD-11 rule lives (#59).** `apply_defaults` serves Python, TypeScript and the shape
  snapshot; removing the root half must not touch the `rp_unlabelled` half. Existing generated
  consumer code loosens from `str` to `Optional[str]`; a consumer's mypy may flag uses that assumed
  a value. Say so in the release notes; no shim.
- **Our own fixtures use generic writes on `Scan` (#55).** `Scan` is a `StoredFile` root, so
  DEC-2's default unmounts its writes; tests that create scans through the generic routes move to
  a session. Do not add an opt-out just to keep them.
- **405 vs 404 (#55).** With the collection and member `GET` still mounted, the framework answers
  405 for the missing methods; accept that, do not add handlers to shape the answer.
- **Reading a large loaded graph (#56).** One `CONSTRUCT` of the whole graph; size is the
  consumer's concern for now.
- **`find` and access (#60).** It runs inside a session, so tenant and permissions are the
  session's; it does not add a permission check of its own beyond what a listing needs.

## No-gos

- Required-everywhere descriptions, or a new annotation to opt out of them.
- Validators or field-level write rules on aggregate writes; making `StoredFile` slots internal.
- Blob handling in the toolkit's generic routes (upload, replace, delete of the file itself).
- Paging, projections or SPARQL passthrough for loaded graphs; returning a graph from `load_graph`.
- Non-equality filters, sorting or paging in `find`; returning stored roots instead of IRIs;
  exporting `ListPlan` or `Listings`.
- Changing the OpenAPI document beyond the filter parameters and the unmounted writes.

---

## What Changes

- **Stage 1**: `services/schema_structure.py` `apply_defaults` drops the root description rule
  (#59); regenerated toy and toolkit artefacts; a new required-flag guard in
  `testkit/conformance.py` (#59). `model/rp_core.yaml` `RpAnnotation` gains `rp_writes`;
  `entrypoints/router.py` and `entrypoints/openapi.py` skip the generic writes of service-written
  roots, with the `StoredFile` default (#55, **BREAKING** for a consumer that writes file roots
  through the generic routes). `entrypoints/openapi.py` `_filter` inlines item schemas;
  `Makefile` `typecheck-ts` runs `openapi-typescript` (#54).
- **Stage 2**: `services/session.py` gains `loaded_graph` (#56) and `find` (#60), the latter
  reusing `services/listing.py`.
- Docs: `howto/adopt.adoc` (file roots written through a session; reading loaded graphs; finding
  aggregates), `generation.adoc` (descriptions optional, the new guard), `questions.adoc`.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `rp-metamodel`: a root's description is optional in every generated artefact.
- `rp-service-api`: `rp_writes: service` and the `StoredFile` default; listing filters inline their
  item schemas.
- `rp-aggregate-store`: `loaded_graph` and `find` on a session.
- `rp-testkit`: the required-flag conformance guard.

## Impact

- MWB2: builds file records without a description; removes S-90 (`.d.ts` + `skipLibCheck`);
  writes its file roots through its own routes (it already plans to); ontology browsing and the
  409 on a duplicate name use public calls.
- Other consumers: generic writes on `StoredFile` roots disappear (**BREAKING**, opt back in is
  not offered); `description` on roots becomes `Optional` in generated Python and TypeScript.
- No new runtime dependency; `openapi-typescript` is a pinned dev tool run via `npx`, like `tsc`.
  No change to the stored data's shape.
