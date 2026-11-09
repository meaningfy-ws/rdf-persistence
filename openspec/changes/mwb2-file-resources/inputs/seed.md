# Seeds and shaping record — mwb2-file-resources

> **Secondary input.** Preserved as received and as decided; never groomed. The EPIC
> (`../proposal.md`) is the shaped truth.

## Seeds (GitHub issues, filed by mapping-workbench-v2 on 2026-11-09)

| # | Title | MWB2 change it blocks |
|---|---|---|
| #54 | OpenAPI: listing filters `$ref` the items of an optional array property, which breaks openapi-typescript | v1-04 (stopgap S-90: `.d.ts` + `skipLibCheck`) |
| #55 | Let a consumer keep an aggregate class's generic writes for its own service (stored files) | v1-06 file API |
| #56 | Read a loaded graph's triples (`load_graph` returns only its IRI) | v1-06 ontology counts and browsing |
| #59 | Generated subclass of a Described root makes description required | v1-06 tasks 1.3–1.5, 1.8, 2.1, 2.2 |
| #60 | Find a class's aggregates by slot value from a service | v1-06 task 1.7 (409 on a duplicate name) |

The issue bodies on GitHub are the full seeds.

## What seed intake found in the code (2026-11-09, `develop` at 85d3ab3)

- **#54**: `entrypoints/openapi.py` `_filter` builds `$ref: <Class>/properties/<slot>/items` for a
  multivalued slot.
- **#55**: `entrypoints/router.py` `add_aggregate_routes` mounts `POST`/`PUT`/`DELETE` for every
  served root; `model/rp_files.yaml` marks only `file_key` internal. The previous EPIC
  (mwb2-adoption-fixes) listed "unmounting the generic routes (#49 option B)" as a no-go; that was
  about **tenant** writes and a consumer's validators. #55 is about one **class**'s writes; DEC-2
  below takes it deliberately.
- **#56**: `services/session.py` `load_graph` returns the loaded graph's `URIRef` only; nothing
  public reads it back.
- **#59**: not a LinkML bug. `services/schema_structure.py` `apply_defaults` (PD-11 of
  toolkit-v1-foundation) gives every **aggregate root** a `slot_usage` `description: required`,
  applied to the generators that run on the generation view (Python, TypeScript) but not to the
  JSON Schema / OpenAPI components. The toy fixture shows it: `Book`, `Scan`, `LibraryAccess` have
  `description: str = Field(default=...)` in Python and `required: [id, label]` in
  `openapi-components.json`. MWB2's abstract `ProjectFile` is not a served root; its `is_a`
  subclasses are, so only they got the rule. No guard caught the mismatch. The living spec
  `rp-metamodel` says roots "carry … a description".
- **#60**: the router builds a `ListPlan` through `kit.listings.plan(...)` and runs it with
  `Session.page(plan)`; neither `ListPlan` nor `Listings` is public.

## Developer's answers (2026-11-09)

- **Q-1 (#59)** — description optional everywhere: drop the "description required on roots" half
  of PD-11, keep `label` required; add a guard for Python/JSON Schema required-flag mismatches.
  Rejected: required everywhere; a per-class opt-out annotation.
- **Q-2 (#55)** — a class annotation `rp_writes: service` leaves the generic writes unmounted and
  keeps `GET` and the listing; a root that mixes in `StoredFile` has it by default. Rejected:
  opt-in only; making every `StoredFile` slot service-set.
- **Q-3 (#56)** — `session.loaded_graph(root_iri, graph_iri) -> rdflib.Graph`, read from the store,
  gated like any read of the aggregate, no paging. Rejected: returning the graph from
  `load_graph`; both.
- **Q-4 (#60)** — `session.find(cls, **equals) -> list[str]` of IRIs, reusing the listing plan,
  equality only, an unknown slot raises. Rejected: exporting `ListPlan`/`kit.listing`.
- **Q-5** — two stages, appetite MEDIUM: stage 1 = #59, #55, #54; stage 2 = #56, #60. One PR each.
- **Q-6 (#54)** — a unit test (no parameter schema points into another schema's property) plus
  `make typecheck-ts` running a pinned `openapi-typescript` on the toy OpenAPI and `tsc --strict`
  on its output.
- **Q-7** — autonomy: commit, push, open and merge PRs without asking, merging only on green CI.
- **Q-8 (test scenarios)** — the four scenario sets proposed were kept (answer read as approval of
  all four; the question asked which to drop and all four were ticked — confirm if meant otherwise).

## EPIC update (2026-11-09, after stage 1 was built)

Source: MWB2's impact note `mapping-workbench-v2/temp/rp-adoption-fixes-impact.md` (read-only
analysis of the earlier epic's effect on MWB2), applied to proposal.md by the developer's side.

- #59 is MWB2's critical path: it blocks v1-06 tasks 1.3–1.5, 1.8, 2.1, 2.2, and 1.6, 1.7, 3.6,
  4.6 through them.
- #54 is moot for MWB2: it adopts the generated `rp_service.ts` (#47) and drops `openapi-typescript`
  and its S-90 stopgap in its change `rp-adoption-refresh`. #54 stays fixed here for other
  consumers.
- Stage 1's PR closes #59, #55 and #54 on merge, so MWB2 can refresh its lock without waiting for
  stage 2.
- Stage 2 serves v1-06 tasks 2.3, 2.4, 3.7 (#56) and 1.7 (#60).

The bet and DEC-1 to DEC-5 are unchanged; PLAN adjusted in design.md ("EPIC update") and tasks.md
(stage 1 close, roadmap).
