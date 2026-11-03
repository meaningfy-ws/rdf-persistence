# Round-4 corrections to the integrated docs (collected by the leader)

Applied by the leader already:
- index.adoc Queries row: per-library attribution (Owlready2 = safe binding only).
- index.adoc Identity and Writes rows: per-library attribution; version-guarded single-request
  commit "implemented nowhere yet".

To apply in round-4 harmonisation:
- libraries/owlready2.adoc: feature ids → G19, G20, T10, E8; GitHub mirror pwin/owlready2 has
  218★ but is stale since 2023 (DEC-5 still fails on GitHub data); PyPI 0.51 (~102k/mo), analysed
  commit 0.52; build-time use needs an explicit DEC-5 exception + Java in CI; ROBOT is an
  unanalysed alternative.
- catalogue.adoc layers: sparqlmodel L1, L2 (partial), L4; triplemodel L0 (partial), L1,
  L2 (partial).
- catalogue.adoc LinkML origin: built at Lawrence Berkeley National Laboratory (NCATS funds).
- catalogue.adoc datamodel-code-generator: now in its own GitHub organisation.
- building-blocks/angles codegen: FastAPI OpenAPI from LinkML Pydantic models carries a
  non-standard `linkml_meta` object and types IRIs as plain string; LinkML gen-openapi strips it
  (openapigen.py:336) — publish gen-openapi output or strip in FastAPI (inferred from code).
- TypeScript gap wording: enums declared but enum-typed fields emitted as `string`; dates map to
  `date` (invalid TS type).
- Taxonomy round-4 proposals (raw ids, to renumber): owlready2 G28 toolchain prerequisites, G29
  reasoner profile, U11 desktop instance editor; sparqlmodel D14 append-only duplicate warning;
  triplemodel I7 reversible IRI minting; codegen G28 strip generator bookkeeping, G29 importer
  drop report, G30 SHACL equivalence CI check; angle-lpg PG1–PG6.
- catalogue.adoc neomodel: layers L1 + L2 (L0 partial, L6 weak); origin = neo4j-contrib community
  org (Robin Edwards, 2013), not a Neo4j product.
- catalogue.adoc Prez: add L2 (read adapters).
- index.adoc Authorization pattern: Prez forwards no identity (one basic-auth service account);
  it offers only the typed-query seam (AZ3) and the trusted-proxy gate (AZ23).
- LDkit: drop or verify "Charles University" (not stated in repo); align fit — catalogue says
  "integrate", angle pages say "ideas"; resolve to: integrate for V5 graph-direct reads (fails
  DEC-5 → needs explicit exception), ideas otherwise.
- Taxonomy proposals: prez T12 read-only guard at protocol boundary; neomodel D14 parameter
  redaction in query logs (collides with sparqlmodel D14 → renumber).
- OldMan: rounds 1–3 analysed master only; unmerged `session` branch (late 2015) adds Session with
  change tracking, flush(), cross-store sessions (partial identity lookup, still one request per
  resource) — evidence saved in temp/oldman-session/. Author: Benjamin Cogrel (`oldm` = org).
  OldMan is Active Record, no identity map, no equality by IRI (index Mapping/Identity rows fixed
  by the leader).
- Eager loading: VALUES + UNION is OldMan's; SuRF uses sub-select + UNION without VALUES (index
  Reads row fixed by the leader).
- catalogue.adoc OldMan layers: add L0 (partial), L2, L3 (partial); SuRF last commit 2017.
- Taxonomy proposals: oldman I7 temporary IRIs minted at flush (collides with triplemodel I7 →
  renumber), P20 UoW orders writes by reference dependencies, T12 UoW spanning several stores
  without cross-store atomicity (collides with prez T12 → renumber).
- angle-evolution: EV1–EV9, D14–D18 (D14 collides again → renumber).
- libraries/pydantic-rdf.adoc:95: `linkml_meta` now VERIFIED (LinkML 1.10.0 gen-pydantic emits
  class_uri/slot_uri by default; default mode drops range/inlined/multivalued → runtime mapper
  infers from annotations or generate with metadata_mode=full). pydantic-rdf classes must
  subclass BaseRdfModel (only its Annotated markers fit the persistence-free pattern).
- catalogue.adoc rdfmapper origin: 2025 UFMA thesis building on simpot (2022); sparqlx row: GPL-3.0,
  sync+async, SPARQL Update, rdflib Graph targets; pydantic-rdf data loss = language tags, extra
  values on single-valued fields, ignored WithDataType.
- index rdfproxy leak line fixed by the leader (totals, single-item lookups, grouped rows).
- Taxonomy proposals: G28 build check that linkml_meta is complete (collides → renumber),
  AZ30 policy-filter equivalence test.
- semantic.works (applied by the leader in index/variants/building-blocks): header trust is
  internal-only (mu-identifier strips browser-sent mu-auth-*); Atomic Operations are our extension;
  sparql-parser works with any SPARQL store; ~100-quad chunking is a heuristic; V5 can use
  sparql-parser as an existing graph-level read proxy. Still to apply: libraries/semantic-works.adoc:79
  trusted-header wording.
- angle-ddd (applied by the leader in index): LinkML has no composition construct; single guarded
  operation; thin aggregate-shaped UoW bullet. Proposals B1–B16 (new area B, Boundaries).
- Stores (applied by the leader): Oxigraph conflict detection on-disk only, Python atomic per call;
  Fluree per-graph policy defaults via f:graphOverrides. Still to apply: catalogue pyoxigraph row
  ("transactions" → atomic per-call updates in Python; transactions Rust-only); angles/stores.adoc:164
  uses round-3 E-numbering and T7 "none found" (rdflib Store flags, Fluree /.well-known are partial
  precedents); origins: Oxigraph by Thomas Pellissier Tanon; rdflib contrib rdf4j/graphdb by Edmond
  Chuc; Fluree retries blind-write commits up to 16×; savepoints Rust-only.
  Proposals: T12 read-tracked optimistic commit, AZ30 policy changes apply from next tx, S20
  per-graph store config, S21 store-side SHACL/uniqueness on write.
- JS client: building-blocks L5 fixed by the leader (@inrupt passes DEC-5, Solid-only). Still to
  apply: angles/jsclient.adoc:202 "X20" → G11; catalogue: LDO by Jackson Morgan, also NextGraph;
  LDflex maintained mainly by Jesse Wright; rdf-ext is Thomas Bergwinkl's org (not Zazuko);
  cypress-cucumber-preprocessor transferred from TheBrainFamily; @api-platform/admin row: server must
  copy order[]/page/itemsPerPage params + schema.org hints; fluree-client last push 2026-03 (drop
  "near-dead"). Proposals: X23 strict JSON-LD processing, U11 Web Components, G28 dcterms:conformsTo
  link, U12 bulk batch.
- Authz: Fluree claims confirmed via the finished index (reads filtered binary_scan.rs:1082, writes
  checked stage.rs:2861, SPARQL policy conditions executor.rs:224,459; policy-condition caching TODO;
  policies cannot target a named graph directly — per-graph defaults via f:graphOverrides, per the
  stores angle). angles/authz.adoc: drop "Fluree index not finished" note. Catalogue: Casbin is now
  Apache Casbin (ASF: apache/casbin, apache/casbin-pycasbin); ODRL-Evaluator origin = odrl-force org
  (Slabbinck, Herweg; IDLab Ghent / SolidLab); Jena access denies with HTTP 400 "Not supported",
  not 403. Fluree v4 adds cascade only for edge annotations (no general cascade delete).
  Proposals: AZ30 per-graph class resolution, AZ31 policy inheritance down containers, AZ32 skip
  check for uncovered predicates, AZ33 404 instead of 403 (AZ30 collides → renumber).
- Service (index + building-blocks fixed by the leader): API Platform ships only the row-filter hook
  (app writes the filter, e.g. CurrentUserExtension), emits ETags but checks no If-Match, has no
  JSON:API Atomic Operations; GitNexus repo name is `core`. Still to apply: angles/service.adoc:113
  overstatement; catalogue linkml-store "variant (E)" → approach C, line ~259 "variant D" → approach;
  origins: HyperGraphQL → Semantic Integration Ltd. (now Epeirogenic AB); UltraGraphQL → RWTH Aachen
  i5 (archived 2020); ldp4j → Center for Open Middleware; Trellis → Aaron Coburn; add Antoine Bluchet
  (API Platform maintainer), Martynas Jusevičius (LinkedDataHub), Chris Mungall (linkml-store).
  Proposals: AZ30 withhold headers/validators from non-readers, X23 MCP tools from the resource
  registry, E10 subscription channel options, S20 named graphs mirrored to VCS, D14 formal model of
  HTTP + access contract in CI (collisions → renumber).
