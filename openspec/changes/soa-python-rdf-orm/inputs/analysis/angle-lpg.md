# Angle: labelled property graphs (LPG) behind the same ports (DEC-14, side question)

- Change: `soa-python-rdf-orm` · round 3 · slug `angle-lpg` · analyst run 2026-11-03
- Brief: `BRIEF-round3.md`; rubric `RUBRIC.md`; compare `neomodel.md` (Neo4j OGM, already analysed)
- Scope: proportionate. The product stays triple-store-first; this file answers "how hard would an
  LPG backend be, and what must the ports look like now so it can be added later".
- Deep dives:

| Clone | Commit | Licence | Index |
|---|---|---|---|
| `neosemantics` (neo4j-labs/neosemantics, "n10s") — my clone | d5cfd2a (2026-10-09, v2025.06.1, Neo4j 2025.06.2 per `pom.xml:8,37`) | Apache-2.0 | GitNexus: 2,292 nodes, 5,681 edges, 98 clusters, 174 flows; 102 Java files, 27.8k LOC |
| `linkml-store` (existing sibling, not re-indexed) | f19c1d9 (2026-09-20) | MIT | read directly; Neo4j adapter = 625 LOC (`api/stores/neo4j/`, `utils/neo4j_utils.py`) |
| `rdflib-neo4j` (neo4j-labs) — my clone, small, read directly (not indexed) | e50d0c9 (2026-10-09) | Apache-2.0 | 1,255 LOC |

---

## Purpose and origin

- **neosemantics (n10s):** a Neo4j Labs server plugin by Jesús Barrasa (Neo4j) for moving RDF in
  and out of Neo4j: import RDF/OWL/SKOS into an LPG, export the LPG as RDF, map vocabularies,
  validate with SHACL, run light inference. Angle: **store-side bridge** (lives inside Neo4j as
  Cypher procedures). Layer fit: L2 (an import/export path into Neo4j); it does not touch L1.
- **rdflib-neo4j:** Neo4j Labs, same author; an rdflib `Store` that streams triples into Neo4j
  using the n10s mapping conventions, from Python, without the server plugin. Angle: **bulk
  loader**. Layer fit: L2 loader only (write-only, see below).
- **linkml-store:** LinkML org (Chris Mungall et al.); a document/collection API over many
  backends (DuckDB, MongoDB, Solr, ChromaDB, Neo4j, …) driven by a LinkML schema. Angle:
  **schema-first data access for AI/data-science pipelines**. Layer fit: L1-ish, but as a
  collection API, not a Data Mapper with a unit of work. **It has no RDF/SPARQL backend**
  (`src/linkml_store/api/stores/`: chromadb, dremio, duckdb, filesystem, hdf5, ibis, mongodb,
  neo4j, solr).

## 1. Headline findings

1. **No existing Python mapper targets both RDF and LPG.** linkml-store has Neo4j but no RDF
   store; neomodel/gqlalchemy are LPG-only; every RDF mapper (rounds 1–2) is RDF-only. The only
   "both models" products are **stores**: Amazon Neptune (SPARQL + openCypher/Gremlin; Neptune
   Analytics runs openCypher over RDF since 2024-08, the "OneGraph" research line) — see
   <https://aws.amazon.com/about-aws/whats-new/2024/08/amazon-neptune-analytics-opencypher-queries-graphs>
   and <https://ceur-ws.org/Vol-3828/paper44.pdf>.
2. **The de-facto RDF→LPG mapping is n10s's**, and it is lossy by default. Every RDF corner the
   rdf-persistence design cares about needs an explicit encoding choice (table in §3). The
   conventions are reusable as a spec for an LPG adapter even if n10s itself is not used.
3. **There is no standard RDF↔LPG mapping.** GQL (ISO/IEC 39075:2024) standardises the LPG query
   language, not the mapping. W3C RDF 1.2 (triple terms; CR 2026-04-07,
   <https://www.w3.org/TR/2026/CR-rdf12-concepts-20260407/>) makes edge properties expressible
   in RDF, and the RDF 1.2 Interoperability note is still a Group Note *draft*
   (<https://www.w3.org/TR/2026/DNOTE-rdf12-interop-20260723/>) and deals with RDF Full↔Basic,
   not with property graphs.
4. **LPG is the easier store for transactions, the harder one for semantics.** Neo4j (Bolt) has
   real multi-statement ACID transactions, which SPARQL 1.1 lacks; but named graphs, language
   tags, custom datatypes, IRIs-as-identity and open-world multi-valued properties all need
   encodings. So the UoW/store port ports *up* easily; the mapper and the query builder are where
   the cost is.
5. **Recommendation: do not build an LPG adapter now; shape four seams now** (§5) that cost
   almost nothing because rdf-persistence needs them anyway. That keeps an LPG adapter an
   additive change later.

## 2. Landscape (desk scan, 2026-11-03)

Stars / last push from `gh api repos/...`; downloads = PyPI last month (pypistats.org).

| Candidate | What | Stars | Last push | Licence | PyPI/month | DEC-5 | Layers |
|---|---|---|---|---|---|---|---|
| neo4j/neo4j-python-driver | official Bolt driver | 1,051 | 2026-10-29 | GitHub "Other" (not checked) | 12.4M | pass | L2 |
| neo4j-contrib/neomodel | Neo4j OGM, Active Record (see `neomodel.md`) | 1,092 | 2026-11-02 | MIT | 112k | pass | L1 |
| py2neo | former Neo4j toolkit/OGM | 32 (`neo4j-contrib/py2neo` remnant) | 2023-11-30 | Apache-2.0 | 66k (legacy) | **fail** (EOL 2023) | — avoid |
| neo4j-labs/neosemantics (n10s) | RDF↔LPG plugin | 972 | 2026-10-09 | Apache-2.0 | — (jar) | pass | L2 |
| neo4j-labs/rdflib-neo4j | rdflib Store → Neo4j (write-only) | 104 | 2026-10-09 | Apache-2.0 | 23k | pass via org (neo4j-labs) | L2 loader |
| apache/tinkerpop (gremlinpython inside) | Gremlin, many backends | 2,153 | 2026-11-03 | Apache-2.0 | 15.4M | pass | L2 |
| opencypher/openCypher | language spec, TCK | 1,028 | 2026-03-20 | Apache-2.0 | — | pass (spec) | — |
| memgraph/memgraph | Cypher LPG, in-memory | 4,641 | 2026-11-02 | GitHub "Other" (BSL per vendor, not verified) | — | pass (licence caveat) | L2 |
| memgraph/gqlalchemy | Memgraph OGM (pydantic) | 302 | 2026-09-10 | Apache-2.0 | 50k | pass | L1 |
| FalkorDB/FalkorDB | Cypher LPG on Redis | 10,505 | 2026-11-02 | GitHub "Other" (SSPL per vendor, not verified) | — | pass (licence caveat) | L2 |
| kuzudb/kuzu | embedded Cypher LPG | 4,017 | 2025-10-10 | MIT | 323k | **fail — archived 2025-10** (<https://www.theregister.com/2025/10/14/kuzudb_abandoned/>) | — |
| LadybugDB/ladybug | community fork of Kuzu | 1,897 | 2026-11-03 | MIT | 58k (`real-ladybug`) | pass (young) | L2 (embedded, test fake) |
| apache/age | openCypher on PostgreSQL | 4,927 | 2026-10-13 | Apache-2.0 | — | pass | L2 |
| linkml/linkml-store | LinkML collection API, Neo4j backend | 27 | 2026-10-09 | MIT | 10k | pass via LinkML org | L1 (collection) |
| awslabs/amazon-neptune-tools | Neptune export/utilities | 315 | 2026-10-29 | Apache-2.0 | — | pass | L2 ops |
| aws/graph-notebook | Jupyter for SPARQL/Gremlin/openCypher | 825 | 2026-09-01 | Apache-2.0 | — | pass | dev tooling |
| Amazon Neptune | managed store: RDF + LPG, openCypher over RDF (Analytics) | closed | — | commercial | — | n.a. (service) | L2 |
| Stardog / GraphDB | RDF stores with RDF-star "edge properties"; no Cypher | closed | — | commercial | — | n.a. | L2 (not checked further) |

LinkML generators: **no Cypher / property-graph-schema generator** in
`linkml/packages/linkml/src/linkml/generators/` (grep for `neo4j|cypher|property.graph` is
empty); there are `typedbgen.py` and `terminusdbgen.py` for other graph stores, and
`graphqlgen.py` (types only).

## 3. Deep dive — neosemantics (n10s)

**Architecture (GitNexus + files):** Cypher procedures grouped by concern under `src/main/java/n10s/`:
`graphconfig/` (the mapping config, `GraphConfig.java`), `rdf/load|delete|export|stream|preview`,
`quadrdf/` (named-graph mode), `mapping/` (vocabulary ↔ LPG name mappings), `onto/` and `skos/`
importers, `validation/SHACLValidator.java` (SHACL compiled to Cypher checks), `inference/`,
`endpoint/RDFEndpoint.java` (HTTP: `/{dbname}/describe`, `/cypher` → RDF). The core is an rdf4j
`RDFHandler` (`RDFToLPGStatementProcessor.java`) that buffers per-subject props/labels/rels and
flushes them to the graph.

**How each RDF corner is mapped (code evidence):**

| RDF feature | n10s encoding | Evidence | Loss? |
|---|---|---|---|
| Resource identity (IRI) | node `:Resource {uri}` with uniqueness constraint `n10s_unique_uri`, required before import | `CommonProcedures.java:41-65` | none |
| Vocabulary IRIs (predicates, classes) | `handleVocabUris`: SHORTEN (`ns0__name`), SHORTEN_STRICT, IGNORE (local name), MAP (custom mapping), KEEP (full IRI as key) | `GraphConfig.java:30-34,90-91,229-255` | IGNORE/MAP lose the namespace |
| `rdf:type` | LABELS (default), NODES (`:Class` nodes + `rdf__type` rels), LABELS_AND_NODES | `GraphConfig.java:43-49,95-97,271-280` | none in NODES mode |
| Multi-valued datatype props | `handleMultival`: OVERWRITE (default — keeps last value!) or ARRAY (optionally only for `multivalPropList`); a REIFY mode is commented out | `GraphConfig.java:36-41,92-93,104-105` | **default is lossy**; arrays are unordered-in-RDF but ordered in LPG |
| Language tags | `keepLangTag`: value stored as the string `"text@en"`; otherwise tag dropped; optional `languageFilter` drops other languages | `RDFToLPGStatementProcessor.java:101-113` | **lossy by default**; encoding is a string hack |
| Datatypes | xsd ints→long, decimals→double, boolean, dateTime→ZonedDateTime (with fallbacks to string), WKT→point; `keepCustomDataTypes` stores `"value^^<dt>"` strings | `RDFToLPGStatementProcessor.java:94-140`, `GraphConfig.java:102-103` | xsd:decimal precision lost (→ double) |
| Named graphs | separate `quadrdf` procedures: node key becomes the pair `{uri, graphUri}` (a resource in two graphs is two nodes) | `quadrdf/RDFQuadDirectStatementLoader.java:61-87,124-177`, `quadrdf/ContextResource.java` | identity changes model |
| Blank nodes | skolemised as `bnode://<id>` URIs | `RDFToLPGStatementProcessor.java:412-415` | ok |
| RDF-star / edge properties | import: quoted triple whose object is a resource + literal annotations → relationship property; reified *datatype* statements ignored. Export: relationship properties emitted as RDF-star by default | `RDFToLPGStatementProcessor.java:405-420`; `rdf/export/RDFExportProcedures.java:49`, `LPGToRDFProcesssor.java:179-187` | partial on import |
| Deletes | `n10s.rdf.delete.*` (`rdf/delete/DirectStatementDeleter.java`) — removes the LPG image of a triple set | file | — |
| SPARQL | **none** (only GeoSPARQL namespace constants; grep `sparql` in `src/main`) | — | no SPARQL endpoint over Neo4j |

**Scores (as a bridge component, not a mapper):** C1 3 (rich import/export/validation, no
object mapping) · C2 3 (config-driven handler; clear) · C3 3 (good guide docs, many knobs) · C4 2
(server plugin version-locked to Neo4j, `pom.xml:37`; not checked whether Aura allows it) · C5 5
(rdf4j for parsing/serialising) · C6 2 (data-level, no domain model) · C7 0 (no SPARQL) · C9 3 (RDF
formats in/out, SHACL; Neo4j-only) · C10 3 (Labs status, `LABS_DISCLAIMER.txt`; releases track
Neo4j) · C8 4 (active, 972 stars, single main author).

**Verdict: borrow ideas** — use its mapping config as the *specification* of an LPG encoding
(identity, vocab shortening, multival, lang tags, datatypes, quad mode). **Integrate** only if a
project already runs Neo4j with the plugin: a UoW flush could call
`n10s.rdf.delete.inline` + `n10s.rdf.import.inline` with the change-set serialised as Turtle in
**one Bolt transaction**, reusing rdf-persistence's RDF change-set unchanged (idea, not tested).

## 4. Deep dive — linkml-store Neo4j adapter (the only LinkML-driven LPG mapper)

- **Model:** a collection is either a node collection or an edge collection
  (`graphs/graph_map.py`: `NodeProjection{identifier_attribute="id", category_labels_attribute="category"}`,
  `EdgeProjection{subject, predicate, object}`). Labels come from the `category` value of each
  object (`neo4j_collection.py:_node_pattern`); collections are discovered from `db.labels()`
  (`neo4j_database.py:85-98`).
- **Writes:** one `CREATE` per object (`neo4j_collection.py:_create_insert_cypher_query`); edges
  `MATCH s, o CREATE (s)-[r:pred]->(o)`, with a `DeletePolicy` (CASCADE / ERROR / STUB) for
  dangling ends.
- **Transactions:** none — `commit()` is a no-op ("Neo4j uses auto-commit",
  `neo4j_database.py:66-68`); each object is its own auto-commit statement.
- **Quality:** values from the query are interpolated into Cypher (`neo4j_collection.py:215`
  `f"s {{{ia}: '{subj}'}}"` — injection risk); JSON import builds a relationship query that is not
  an f-string (`neo4j_database.py:150` `"CREATE (a)-[r:{rel_type} ..."`) so it cannot work. No IRIs,
  no lang tags, no named graphs: it maps LinkML *JSON objects*, not RDF.
- **Scores:** C1 2 · C2 2 (collection API, no UoW/identity map) · C3 3 (uniform API across
  backends) · C4 3 · C5 3 (neo4j driver, LinkML) · C6 3 (schema-first) · C7 0 · C9 2 · C10 2 · C8 2 for
  this adapter (27 stars; one test file `tests/test_api/test_neo4j_adapter.py`).
- **Verdict: borrow ideas** — the Node/Edge projection split is the right minimal vocabulary for
  "which LinkML classes become nodes and which become relationships (with properties)". Avoid as
  a dependency for the LPG path.

**rdflib-neo4j (mini dive):** an rdflib `Store` (`Neo4jStore.py:18`) that buffers triples and
flushes batched `UNWIND … MERGE` Cypher with the n10s conventions. `remove()` raises
`NotImplementedError("This is a streamer …")` (`Neo4jStore.py:134-135`) and there is no
`triples()` implementation — **write-only bulk loader**, so it cannot sit behind rdf-persistence's
read/write store port. Verdict: integrate only as an optional bulk-export tool.

## 5. Design answer — what is neutral, what is RDF-specific, what an LPG adapter needs

Parts as in `building-blocks.adoc` L1/L2. Difficulty = effort to add an LPG (Cypher/Bolt) adapter
*later*, assuming the seams in the last column exist.

| Part | Neutral or RDF-specific | What an LPG adapter needs | Difficulty |
|---|---|---|---|
| Domain classes (LinkML → pydantic) | neutral | nothing | low |
| Mapper metadata (`class_uri`, `slot_uri`, range, multivalued, inverse) | neutral metadata, RDF *rendering* | a name policy IRI → label / property key / rel type (n10s SHORTEN/MAP) + a projection: which classes are nodes vs relationships (linkml-store idea) | medium |
| Identity (IRI) | neutral if the key is an opaque IRI string | `uri` property + uniqueness constraint per node (n10s `n10s_unique_uri`) | low |
| Identity map | neutral (keyed by IRI) | nothing | low |
| Unit of work / change-set | neutral **if** the UoW produces an abstract change-set (adds/removes per subject-slot-value), not SPARQL strings | Cypher renderer of the change-set; run in one Bolt transaction (stronger than SPARQL) | low–medium |
| Optimistic concurrency | neutral concept | `WHERE n.version = $v` on `MATCH` | low |
| Literals: typed | mostly neutral | xsd → Neo4j types; decimal/custom datatypes need a string encoding | medium |
| Literals: language-tagged | RDF-specific | encoding choice: `"text@en"` (n10s), per-language keys `title__en`, or a side node; none is natural | medium (and lossy query semantics) |
| Multi-valued slots | neutral | homogeneous arrays for literals (order is LPG-only); multiple relationships for object slots | low |
| Edge properties / qualified relations | **LPG-native, RDF-hard** (RDF 1.2 triple terms or n-ary classes) | native relationship properties | low on LPG |
| Named graphs | RDF-specific | one of: database per graph (Neo4j multi-db), `graphUri` in the key (n10s quad mode, changes identity), or a label/property as scope; each changes semantics | high |
| Query builder | neutral only if it is an AST (filter/order/page/traverse) and SPARQL is one renderer | a Cypher renderer of the same AST (neomodel's `QueryAST` is the model) | medium (high if the builder emits SPARQL text directly) |
| Raw SPARQL escape hatch / CONSTRUCT reads | RDF-specific | none — keep it on a separate RDF-only port | n.a. |
| JSON-LD in/out | neutral (from domain objects + generated `@context`) | nothing | low |
| SHACL validation | neutral if done on domain objects/graphs before flush | nothing (n10s has in-DB SHACL if wanted) | low |
| Authorization scope (DEC-8) | graph-scope is RDF-specific | scope expressed abstractly (partition id); LPG maps it to database or label (Neo4j Enterprise fine-grained RBAC) | medium |
| Store port (capabilities) | neutral | report `transactions=multi_statement`, `named_graphs=False|emulated`, `query_language=cypher` | low |

**Overall estimate:** a usable Neo4j adapter (CRUD, relationships, identity, UoW in one
transaction, simple filters) is **medium** effort if the seams below exist; full RDF fidelity
(named graphs, lang tags with SPARQL-like semantics, round-trip to RDF) is **high** and probably
not worth it. Neptune is the cheap route for "both models": keep the SPARQL adapter and read the
same data through openCypher there — no adapter work, AWS lock-in.

**Seams to shape now (cheap, since the RDF design needs them anyway):**
1. The UoW emits an **abstract change-set** (per subject: slot adds/removes, version check); the
   SPARQL Update text is produced by the store adapter, not by the UoW.
2. The query builder is an **AST with renderers**; SPARQL is the only renderer shipped.
3. **Raw SPARQL lives on a separate `SparqlPort`**, not on `Repository[T]`, so the repository API
   never promises SPARQL.
4. "Named graph" appears in the public API as a **scope/partition** concept (which the RDF adapter
   maps to a graph IRI), and the store port **declares capabilities** (transactions, named graphs,
   query language). This also serves DEC-8 (ACL-agnostic scopes).

Do *not* build now: a Cypher renderer, a property-name policy, LPG schema install, any Gremlin
path (YAGNI until a project asks).

## 6. Patterns catalogue (LPG angle)

| Pattern | Where seen | Use for rdf-persistence |
|---|---|---|
| IRI as unique node property + DB constraint | n10s `CommonProcedures.java:41-65`, rdflib-neo4j README | LPG identity |
| Configurable vocabulary-IRI shortening/mapping | n10s `GraphConfig.handleVocabUris` | name policy for labels/keys |
| Type as label vs type as node | n10s `handleRDFTypes` | polymorphism on LPG (labels = class + ancestors, as neomodel) |
| Node vs edge projection of classes | linkml-store `graph_map.py` | which LinkML classes become relationships with properties |
| Quad mode: graph IRI in the composite key | n10s `quadrdf/ContextResource.java` | one of three named-graph encodings |
| Edge properties ↔ RDF-star | n10s export `RDFExportProcedures.java:49` | round-trip of qualified relations |
| Change-set as RDF delete+insert payloads in one DB transaction | n10s `rdf.delete.inline` + `rdf.import.inline` (idea) | reuse the RDF change-set on Neo4j |
| One store, two query languages over one graph | Neptune Analytics / OneGraph | "both models" without a second adapter |
| Query AST → language renderer | neomodel `match.py:520` | SPARQL now, Cypher later |

## 7. How options plug into MWBv2 and an ACL-agnostic rdf-persistence

- **Variant A — RDF only (baseline):** no change; the four seams are internal hygiene.
- **Variant B — Neptune "both models":** SPARQL adapter as-is against Neptune; analysts use
  openCypher/Gremlin on the same data. Authorization stays at the service (DEC-8). Cost: AWS lock-in.
- **Variant C — Neo4j via n10s:** SPARQL-less; UoW change-set serialised as Turtle and applied with
  n10s procedures in one Bolt transaction; reads via a Cypher renderer. Requires the plugin and
  n10s config pinned per project. Lang tags/named graphs as n10s encodes them.
- **Variant D — native LPG adapter (Cypher via `neo4j` driver; also Memgraph, FalkorDB, AGE,
  LadybugDB speak openCypher-ish):** cleanest LPG model, highest effort. Gremlin (gremlinpython)
  only if a JanusGraph/Cosmos/Neptune-Gremlin target appears.
- L0: LinkML has no PG-schema/Cypher generator; constraints (`uri` unique, indexes) would be a
  small new generator (cf. neomodel `install_labels`).

## 8. Proposed new features (prefix PG*)

- **PG1 Backend-neutral change-set:** the UoW yields an abstract change-set; each store adapter
  renders it (SPARQL Update, Cypher, n10s RDF payload).
- **PG2 Query AST with pluggable renderers:** typed query builder compiles to an AST; SPARQL is one
  renderer.
- **PG3 Store capability descriptor:** the store port declares transaction model, named-graph
  support, query language(s), edge-property support. (Overlaps the L2 "store port that reports its
  real transaction capability" gap — merge if already in the taxonomy.)
- **PG4 LPG projection config:** per LinkML class/slot: node vs relationship, label/key naming
  policy from IRIs, lang-tag and multivalue encoding (n10s-style).
- **PG5 Edge-property / qualified-relationship mapping:** a LinkML class marked as a relationship
  with properties maps to an LPG edge and to RDF 1.2 triple terms or an n-ary node on RDF
  (relates to R7).
- **PG6 Scope abstraction for partitions:** named graph ↔ database/label/property partition, used
  by both persistence and authorization (relates to P6 and DEC-8).

## 9. Open questions

1. Is there an actual project need for Neo4j/LPG, or is "analysts want Cypher" enough to choose
   Neptune (Variant B) instead of building an adapter?
2. Must LPG data round-trip back to RDF losslessly (then named graphs and lang tags force high
   effort), or is LPG a one-way projection for analytics (then n10s/rdflib-neo4j export suffices)?
3. Does the domain model need edge properties (qualified relations)? If yes, decide the RDF
   encoding (RDF 1.2 triple terms vs n-ary class) independently of LPG.

## Not checked

- Neo4j driver and Memgraph/FalkorDB exact licences (GitHub reports "Other"); whether n10s is
  installable on Neo4j Aura; Stardog/GraphDB LPG features beyond RDF-star; current Neptune docs
  for OneGraph in Neptune Database (only the 2024 Analytics announcement and paper were found);
  GQL ISO/IEC 39075:2024 text (cited from known publication, not fetched); no code was run.

---

## Round 5

Brief: `BRIEF-round5.md`. Candidates: **n10s** (neosemantics, commit d5cfd2a) and the
**linkml-store Neo4j adapter** (f19c1d9); rdflib-neo4j (e50d0c9) is mentioned where it matters.
Neither is a mapper with a unit of work, so many v4 features are n.a. by construction. Absences
were confirmed by grep over `neosemantics/src/main/java` and `linkml-store/src/linkml_store`:
`migrat`, `conformsTo`, `mcp`, `redact`, `testcontainers`, `readOnly|READ_ONLY`, `metamodel`,
`checksum`, `opentelemetry` all return 0 files in n10s; in linkml-store only `opentelemetry|span`
(2 unrelated hits) and `suggest` (1 hit, LLM inference module) return anything.

### Correction to my round-3 report (important)

§3, §6 and §7 say a unit-of-work flush could run `n10s.rdf.delete.inline` + `n10s.rdf.import.inline`
"in one Bolt transaction". **The code says otherwise.** n10s opens its *own* inner transactions
per batch: `DirectStatementLoader.periodicOperation` does `graphdb.beginTx() … commit()` every
`commitSize` triples (default 25,000; `rdf/load/DirectStatementLoader.java:215-243`,
`graphconfig/RDFParserConfig.java:14,37-39`), and the deleter does the same
(`rdf/delete/DirectStatementDeleter.java:241`). So delete and import are **not atomic together**,
a large payload commits partially, and with `abortOnError=false` a failed batch is logged as
"triples lost" (default is `true`, `RDFParserConfig.java:48-49`). n10s is therefore usable for a
**one-way projection** (rebuildable read replica, export), **not** as a unit-of-work flush.

### (a) v4 cross-check

n10s = neosemantics; LS = linkml-store Neo4j adapter (plus the generic `Collection` it inherits).

| Id | n10s | LS | Evidence |
|---|---|---|---|
| B1 Aggregate declaration | absent | absent | no aggregate concept; LS projection is node/edge only (`graphs/graph_map.py`) |
| B2 Boundary validation | absent | absent | — |
| B3 Whole-aggregate load | n.a. | absent | LS `query` returns flat node rows (`neo4j_collection.py` `node_to_dict`) |
| B4 Whole-aggregate save by diff | n.a. | partial | LS `apply_patches` reloads **all** objects and `replace()`s the collection (`api/collection.py:1187-1202`); `diff()` yields JSON Patch (`:1204`) |
| B5 Typed cross-aggregate refs | n.a. | absent | edges are `{subject, predicate, object}` dicts |
| B6 Aggregates-per-commit policy | n.a. | absent | — |
| B7 Single guarded operation | n.a. | absent | one `CREATE` per object, auto-commit (`neo4j_database.py:66-68`) |
| B8 Backend-neutral change-set | partial | partial | n10s: an RDF payload *is* a neutral change-set, but applied in independent batches (see correction); LS: JSON Patch list (`collection.py:282`, `:1187`) |
| B9 Domain events via outbox | absent | absent | LS `_broadcast` to in-process listeners only (`collection.py:1264`) |
| B10 Graph per aggregate | n.a. | n.a. | — |
| B11 Version as ETag | absent | absent | grep `version`: only build/library versions |
| B12 After-commit hooks | partial | partial | n10s SHACL as an APOC-trigger procedure (`validation/ValidationProcedures.java:23`); LS `_post_insert_hook` |
| B13 Boundary-aware delete | n.a. | partial | LS `DeletePolicy` CASCADE / ERROR / STUB (`neo4j_collection.py:15-18`) — node-level, no boundary |
| B14 Bounded-context partitioning | n.a. | n.a. | — |
| B15 No-autoflush contract | n.a. | n.a. | no session |
| B16 Sagas | absent | absent | — |
| PG1 Query AST, pluggable renderers | n.a. | partial | LS has a backend-neutral `Query` object (`api/queries.py`) rendered per store (`_build_cypher_query`) — the closest existing example |
| PG2 LPG projection config | present | partial | n10s `GraphConfig` (`handleVocabUris`, `handleMultival`, `handleRDFTypes`, `keepLangTag`, `keepCustomDataTypes`); LS `NodeProjection`/`EdgeProjection` |
| PG3 Edge-property mapping | present | partial | n10s RDF-star ↔ rel props (`RDFToLPGStatementProcessor.java:405-420`, `RDFExportProcedures.java:49`); LS edge collections carry extra props, no RDF side |
| PG4 Partition scope | partial | absent | n10s quad mode keys nodes by `{uri, graphUri}` (`quadrdf/RDFQuadDirectStatementLoader.java:61-87`) |
| EV1–EV9 Evolution | absent | absent | grep `migrat`, `checksum` = 0; n10s `preview` procedures (`rdf/preview/`) are a dry run of an import, not of a migration |
| AZ30–AZ36 Authorization | n.a. | n.a. | neither enforces access; Neo4j RBAC is outside both |
| G28–G36 Generation | n.a. | n.a. | no code generation (LS reads the schema at runtime) |
| G33 Metadata completeness | n.a. | absent | — |
| G34 `dcterms:conformsTo` | absent | absent | grep 0 |
| T12 Read-tracked optimistic commit | n.a. | absent | — |
| T13 Read-only guard | absent | absent | grep 0 (n10s endpoint is GET-only by design, `endpoint/RDFEndpoint.java`) |
| T14 Cross-store UoW | n.a. | absent | LS `Client` attaches several databases but no session spans them |
| S20 Per-graph store config | partial | n.a. | one `GraphConfig` per database (`graphconfig/GraphConfigProcedures.java`), not per named graph |
| S21 Graphs mirrored to VCS | absent | absent | — |
| S22 Store-side shape enforcement in the write tx | partial | absent | `n10s.validation.shacl.validateTransaction` in trigger context (`ValidationProcedures.java:23-25`); needs APOC triggers |
| S23 Ops admin port | absent | partial | LS `export_database`/`import_database` JSON (`neo4j_database.py:100-154`; the import of relationships is broken, `:150`) |
| X23 Strict JSON-LD | n.a. | n.a. | — |
| X24 MCP projection | absent | absent | grep `mcp` = 0 |
| E10 Subscription options | n.a. | n.a. | — |
| I7 Reversible IRI minting | partial | n.a. | n10s SHORTEN prefixes are reversible on export (`nsprefixes/`), IRIs kept intact in `uri` |
| I8 Deferred IRI minting | n.a. | absent | — |
| P20 Reference-aware flush ordering | partial | absent | n10s buffers nodes before relationships per batch (`RDFToLPGStatementProcessor.java:385-455`); LS `STUB` policy creates dangling ends instead |
| D14–D29 DevEx | absent | absent / partial | D17: LS builds Cypher strings but exposes none; D19: LS tests need live Neo4j (`tests/test_api/test_neo4j_adapter.py`); D29: no tracing; D15: no redaction; others grep 0 |

Counts (39 rows, ranges counted once): n10s present 2, partial 7, absent 12, n.a. 18 ·
LS present 0, partial 8, absent 22, n.a. 9 (D14–D29 row counted as absent).

### (b) Page review — `docs/modules/ROOT/pages/architecture/soa/angles/lpg.adoc`

1. **l.83** "a flush could call `n10s.rdf.delete.inline` and `n10s.rdf.import.inline` … in one Bolt
   transaction (idea, not tested)" — **wrong** (see correction). Fix: "Each call commits its own
   batches of `commitSize` triples (default 25,000), so delete and import are not atomic together.
   Use n10s only for one-way projections (a rebuildable read replica or export), never as a
   unit-of-work flush."
2. **l.159** (patterns row "RDF change-set as delete + insert payloads in one database
   transaction") — same error. Fix: "… as delete + insert payloads (not atomic: n10s commits in
   its own batches) | one-way LPG projection".
3. **l.182** option "Neo4j via n10s … applied with n10s procedures in one Bolt transaction" — same
   error. Fix the Shape to "applied with n10s procedures, batch-committed (not atomic)" and the
   Cost to add "no atomic writes: fit for a projection, not for the system of record".
4. **l.18** and **l.118** "real multi-statement ACID transactions, which SPARQL 1.1 lacks" /
   "(stronger than SPARQL)" — overstated. Fix: "which the SPARQL 1.1 *protocol* lacks (RDF4J,
   GraphDB and Stardog add them through vendor APIs; see the stores angle)".
5. **l.129** "Neo4j Enterprise fine-grained RBAC" — not verified in this review. Add "(per Neo4j
   documentation, not checked)".
6. **l.17** "RDF 1.2 triple terms (Candidate Recommendation 2026-04-07)" — add "later status not
   confirmed".
7. **l.92** missing caveat: add "`apply_patches` reloads the whole collection and replaces it
   (`api/collection.py:1187-1202`), so patching is O(collection), not O(change)."
8. **l.52 / l.15** "no RDF or SPARQL backend" — correct; add "(it can still *export* Turtle through
   its format utilities, `utils/format_utils.py:37`)" so readers do not infer no RDF at all.
9. **Variant fit table (l.190-203)** — see below; two rows corrected (V5 reasoning, C caveat), two
   rows get a "not checked" note (V4), the rest confirmed.

### (c) Final verdict

**ideas** — n10s: its mapping config is the specification for any future LPG encoding, and it is
an optional one-way export to Neo4j; linkml-store Neo4j adapter: ideas only (node/edge projection,
neutral `Query` object); rdflib-neo4j: optional append-only bulk loader. No LPG adapter now.

Three things a system architect must remember:
1. **There is no standard RDF↔LPG mapping, and every practical one is lossy** (language tags,
   named graphs, `xsd:decimal`, multi-valued literals under the n10s default). Treat Neo4j as a
   one-way projection unless a project proves it needs round-trips.
2. **n10s writes are not transactional with the caller** (independent 25k-triple batches); and
   rdflib-neo4j cannot delete. Neither can be the write path of a system of record.
3. **LPG readiness costs only four seams the RDF design needs anyway**: a backend-neutral
   change-set (B8), a query AST (PG1), raw SPARQL on its own port, partitions as scopes plus a
   capability descriptor (PG4, T7). Keep SPARQL out of `Repository[T]` and the option stays open.

### (d) Variant fit (deep-dived candidates; replaces the editor's inferred table)

| Variant / approach | n10s | linkml-store Neo4j | rdflib-neo4j | Why (evidence) |
|---|---|---|---|---|
| V1 Portable Python core | neutral | none | neutral | Optional export target only; LS is an alternative L1 without a unit of work, so it does not compose with rdf-persistence |
| V2 semantic.works-compatible | neutral | none | neutral | Everything goes through `sparql-parser` (SPARQL only); an LPG projection could be fed by a delta consumer, outside the stack |
| V3 Fluree | n.a. | n.a. | n.a. | Fluree is RDF/JSON-LD only |
| V4 GraphDB | n.a. | n.a. | n.a. | No LPG route (GraphDB Cypher support not checked) |
| V5 Graph-direct reads (CQRS) | **enables** | none | partial | An outbox-fed read replica can be a Neo4j projection: n10s has delete *and* import (batch commits are acceptable for a rebuildable replica); rdflib-neo4j can only append, so it supports full rebuilds, not incremental updates (`Neo4jStore.py:134-135`). The UI tools of V5 (LDkit, Comunica) are SPARQL-only, so this replica serves analysts, not the UI |
| A Runtime mapper | ideas | ideas | n.a. | PG2 projection config read at runtime next to `class_uri`/`slot_uri` |
| B Generated mapper and routes | n.a. | n.a. | n.a. | LinkML has no Cypher/PG generator (grep empty in `linkml/generators/`) |
| C Generic service | n.a. | ideas | n.a. | LS is itself a schema-at-runtime collection API (C-like) but has no RDF backend; a C service fits LPG only if it talks to the query AST, and blocks it if it emits SPARQL directly as `mu-cl-resources` does |

Editor's table, row by row: **V1 supports — confirmed** (as seams; the candidates themselves are
neutral). **V2 blocks — confirmed** for an LPG *backend*; an LPG *projection* fed from deltas is
still possible outside the stack. **V3 n.a. — confirmed.** **V4 neutral — confirmed**, add "GraphDB
Cypher support not checked". **V5 enables — confirmed, reason wrong**: not "a read side on
Neptune" (Neptune would be the store of every variant, not a V5 feature) but "an outbox-fed LPG
read replica via n10s; serves analysts, not the SPARQL-only V5 UI". **A supports — confirmed.**
**B neutral — confirmed.** **C neutral — confirmed with caveat**: blocks if the generic service
emits SPARQL directly.

### Purpose and origin

Already in §"Purpose and origin" at the top of this report (n10s, rdflib-neo4j, linkml-store).
One addition from round 5: n10s's procedures are designed for **bulk ingestion** (batch commits,
`commitSize`, `abortOnError`), which confirms its angle as a store-side import/export bridge, not
a transactional write path.

### (e) New features

None. The only gap found (non-atomic bulk import) is covered by EV8 (staged bulk load) and T7
(capability descriptor declaring the transaction model).
