# Landscape scan — Python RDF ORM / repository libraries (2026-11-03)

Desk scan only: GitHub API (stars, last push, archived, contributors), PyPI JSON (latest
version, last upload, release count), pypistats (downloads, last month), READMEs.
Features are as claimed in READMEs — NOT yet verified in code (that is the GitNexus step).

| Library | Repo | ★ | Contrib. | Last push | Latest release | Downloads/mo | Status |
|---|---|---|---|---|---|---|---|
| sparqlmodel | eddiethedean/sparqlmodel | 0 | 1 | 2026-06-01 | 0.13.1 (2026-06-01) | 61 | new (May 2026), 18 releases in ~2 weeks, then quiet |
| triplemodel | eddiethedean/triplemodel | 0 | 1 | 2026-05-22 | 0.12.0 (2026-05-22) | 48 | beta, same author, base layer of sparqlmodel |
| rdfmapper | LambdaGeo/rdfmapper | 0 | 1 | 2026-09-21 | 0.2.2 (2026-09-20) | 232 | early, active |
| pydantic-rdf | Omegaice/pydantic-rdf | 23 | 1 | 2025-05-03 | 0.2.0 (2025-05-03) | 25 | small, dormant 18 mo |
| pyldo | Mariatta/pyldo | – | – | repo 404 | 0.0.13 (2025-12-27) | 14 | pre-alpha, repo gone/private |
| rdfproxy | acdh-oeaw/rdfproxy | 7 | 4 | 2026-10-27 | 0.10.1 (2026-02-09) | 299 | active, institutional (ACDH), read-only |
| rdflib-orm | edmondchuc/rdflib-orm | 9 | 1 | 2023-07-30 | 0.2.1 (2021-11-27) | 12 | experimental, dormant |
| SuRF | cosminbasca/surfrdf | 44 | 7 | 2021-10-22 | 1.1.9 (2016-05-05) | 61 | dead |
| OldMan | oldm/OldMan | 15 | 1 | 2016-01-05 | not on PyPI (name taken) | – | archived |
| RDFAlchemy | django-rdf-tools/RDFAlchemy | 2 | – | 2012-11-13 | 0.2.9 (no files) | – | dead, Py2 |
| YAROM | openworm/YAROM | 3 | – | 2020-01-25 | 0.12.0 (2020) | 134 | dead |
| Owlready2 | Bitbucket (pwin mirror stale) | 218 (mirror) | – | – | 0.51 (2026-06-22) | ~102k | mature, maintained, ontology-centric |
| linkml-runtime | now in linkml/linkml monorepo | (linkml) | – | 2026-11-02 | 1.12.1 (2026-10-13) | ~550k | mature |
| linkml-store | linkml/linkml-store | 27 | 8 | 2026-10-09 | 0.3.2 (2026-04-28) | ~10k | active, unstable API; NO RDF/SPARQL backend |
| terminusdb-client | terminusdb/terminusdb-client-python | 80 | – | 2026-11-02 | 10.2.6 (2023-11-17) | ~4k | TerminusDB-only, Python <3.12 |
| rdflib | RDFLib/rdflib | 2545 | – | 2026-11-02 | 7.6.0 (2026-02-13) | ~13.2M | mature (baseline) |
| pyoxigraph | oxigraph/oxigraph | 2021 | – | 2026-11-02 | 0.5.13 (2026-10-22) | ~267k | mature, transactional store |
| SPARQLWrapper | RDFLib/sparqlwrapper | 570 | – | 2026-04-30 | 2.0.0 (2022-03-13) | ~1.4M | stable, slow-moving |
| hydrus | HTTP-APIs/hydrus | 196 | – | 2023-02-16 | 0.4.7 (2021-08-11) | – | dormant |
| neomodel (benchmark) | neo4j-contrib/neomodel | 1092 | – | 2026-11-02 | 7.0.0 (2026-08-26) | ~112k | mature (Neo4j OGM) |

## Claimed features (README)

- **sparqlmodel** — "SQLModel of SPARQL": Pydantic v2 models, `SPARQLSession` unit of work
  (identity map, flush, rollback of pending queue, sync+async), query builder → SPARQL,
  relationships with cascade, Memory + HTTP (Fuseki/Jena) stores, GSP mirror, FastAPI
  integration, JSON-LD dump/validate. Closest to the ORM vision on paper.
- **triplemodel** — stateless Pydantic ↔ RDF mapper on pyoxigraph: identity via namespace+id,
  sets vs rdf:List, lang strings, named graphs, sync modes add/replace/patch, SPARQL helpers,
  graph diff, CBD, RDFS-aware dispatch, OWL/RDFS → model codegen (experimental).
- **rdfmapper** — decorator mapping (JPA-like), 1-1/1-n relations, dynamic finder repository
  (`find_by_*`, `count_by_*`), SHACL shape generation + validation. rdflib-based.
- **pydantic-rdf** — Pydantic v2 ↔ rdflib Graph, nested models, lists, cycles, JSON Schema.
  Mapping only, no store/session.
- **pyldo** — Pydantic models from ShEx, Solid Pod support. Pre-alpha.
- **rdfproxy** — SPARQL SELECT → nested Pydantic models, grouping/aggregation, pagination,
  FastAPI. Read-only (no writes).
- **rdflib-orm** — Django-like `models.Model` over rdflib Graph. Experimental.
- **SuRF** — ActiveRDF-style resources, plugins: rdflib, SPARQL protocol, Allegro, Sesame2.
- **OldMan** — models declared as RDF + JSON-LD context (not Python classes), Hydra,
  SPARQL store, CRUD on resources. Conceptually closest to the JSON-LD middleware goal.
- **RDFAlchemy** — `rdfSubject` + `rdfSingle`/`rdfMultiple` descriptors, SPARQL/Sesame backends.
- **Owlready2** — OWL classes as Python classes, SQLite quadstore, reasoners (HermiT/Pellet),
  SPARQL engine. Ontology-first, not a domain-model ORM.
- **linkml-runtime** — rdflib loader/dumper for LinkML-generated dataclasses/Pydantic.
- **linkml-store** — CRUD+Search+Inference over DuckDB/Mongo/Neo4j/Solr/…; no triple-store
  backend (checked `src/linkml_store/api/stores`). Repository-like API we could add a SPARQL
  backend to.

## Observations

- No mature, maintained, write-capable Python ORM over SPARQL 1.1 exists. The mature projects
  are either building blocks (rdflib, pyoxigraph, SPARQLWrapper), ontology-centric
  (Owlready2), or not RDF (linkml-store, neomodel).
- The newest candidates (sparqlmodel, triplemodel, rdfmapper) have the richest feature claims
  but are single-author with no community signal; claims need code verification.
- The LinkML route has the ecosystem (runtime ~550k/mo) but no SPARQL-backed repository.

---

# Addendum — RAD platforms and JavaScript ecosystem (from the Confluence SOTA page + additions)

Same method (GitHub API, npm downloads/month). ★ / last push as of 2026-11-03.

## A. Model → API platforms (rapid application development, server side)

| Project | Lang | ★ | Last push | What it does | Relevance |
|---|---|---|---|---|---|
| **mu.semte.ch / semantic.works** (55 repos) | Lisp/Elixir/JS/Py | 16–18 per repo | 2026-10 | Microservices over one shared triplestore. `mu-cl-resources`: domain.lisp/json → JSON:API ↔ SPARQL CRUD. `mu-authorization` / `sparql-parser`: SPARQL proxy with group-based access + change deltas. `delta-notifier`: change events to services. `mu-javascript-template`, `mu-python-template`: service templates with SPARQL helpers. Ember frontends | **Reference architecture** for the target: model-declared CRUD API + SPARQL middleware + JS-friendly API |
| LinkedDataHub (AtomGraph) | XSLT/Java | 636 | 2026-11 | Low-code KG app platform, ontology-driven CRUD over SPARQL | RAD benchmark; Java stack |
| AtomGraph Processor | Java | 67 | 2023, archived | Ontology-driven Linked Data server | Design idea only |
| Prez + Prez-UI | Python/Vue | 40 / 15 | 2026-10 | rdflib-ecosystem, profile-driven read API (FastAPI) + Vue UI | Python reference, read-oriented |
| grlc | Python | 151 | 2026-10 | Web API generated from SPARQL queries in a repo | Query-first API generation |
| OBG-gen | Python | 17 | 2024-03 | GraphQL server generated from an ontology (academic) | GraphQL route |
| HyperGraphQL | Java | 170 | 2022 | GraphQL over SPARQL | GraphQL route, dormant |
| Trifid (Zazuko) | TS | 102 | 2026-10 | Linked Data server / dereferencing proxy | Read-only |
| Atomic Server | TS/Rust | 1633 | 2026-11 | Atomic Data: typed JSON-AD, own store, real-time | Alternative model, not SPARQL |
| TerminusDB | Prolog | 3469 | 2026-11 | Versioned JSON-LD-ish document graph DB, schema classes, GraphQL | Own store, not SPARQL 1.1 |
| Fluree | Rust | 477 | 2026-11 | Ledger graph DB, JSON-LD native, SPARQL | Own store |
| TypeDB | Rust | 4499 | 2026-10 | Typed graph DB (not RDF) | Modelling-ergonomics benchmark only |
| Veda | – | – | – | repo not found (semantic-machines/veda gone) | drop |
| ontopop | – | – | – | repo not found / 1★ forks | drop |

## B. JavaScript / TypeScript client-side object mappers

| Library | ★ | npm/mo | Last push | What it does |
|---|---|---|---|---|
| LDkit | 83 | ~44k | 2026-10 | TS schema → typed objects, CRUD over SPARQL endpoints via Comunica; closest JS analogue of our ORM |
| LDO (Linked Data Objects) | 73 | ~0.6k | 2026-10 | ShEx → TS typings, objects over RDF/Solid |
| LDflex | 196 | ~1.7k | 2026-10 | Path DSL for querying LD |
| fdr (Kobrix) | 11 | – | 2026-06 | TS library for RDF graph apps |
| rdflib.js | 598 | ~52k | 2026-10 | RDF store/fetcher for JS (Solid) |
| Comunica | 620 | ~47k | 2026-11 | SPARQL/link-traversal query engine for JS |
| GraphQL-LD | 121 | – | 2026-08 | GraphQL queries over LD via JSON-LD context |
| solid-client-js (Inrupt) | 244 | ~69k | 2026-11 | Solid Pod CRUD + ACL |
| RDForms (MetaSolutions) | 8 | – | 2026-10 | Template-driven RDF forms (React) |
| rdf.js (N3, @rdfjs/types) | – | ~1.1–1.2M | – | Common JS RDF interfaces — the interop layer |

## C. Ontology-centric Python (from the page; out of the ORM core)

owlready2 (see above), funowl (57★, OWL functional syntax objects) — ontology authoring, not
application persistence.

## Observations (addendum)

- **mu.semte.ch is the architectural match**: a declared domain → generated CRUD API (JSON:API,
  not JSON-LD) + a SPARQL proxy as the middleware seam (where ACL/deltas live later). Its weak
  spot for us: the core is Common Lisp/Elixir; Python is only a service template.
- The JS side already has a credible typed-object client (LDkit). A JS-friendly rdf-persistence
  means: a stable HTTP contract (JSON:API and/or JSON-LD framed) that JS clients consume, plus
  a schema export (JSON Schema / TS types — LinkML already generates both).
- GraphQL-over-RDF (OBG-gen, HyperGraphQL, GraphQL-LD) is a third API style worth one section.

## D. Foundations to build on (DEC-4 — reuse, never rewrite)

| Foundation | ★ | Downloads/mo | Reuse for |
|---|---|---|---|
| rdflib 7.6 | 2545 | ~13.2M | RDF model, Graph/Dataset, parsers/serialisers (incl. JSON-LD), SPARQL engine, `SPARQLStore` / `SPARQLUpdateStore` (remote SPARQL 1.1 query + update) |
| pyoxigraph 0.5 | 2021 | ~267k | Embedded store with real transactions, fast SPARQL 1.1 |
| oxrdflib 0.5 | 56 | ~27k | rdflib `Store` backed by Oxigraph — rdflib API + Oxigraph engine |
| SPARQLWrapper 2.0 | 570 | ~1.4M | Generic remote SPARQL 1.1 client |
| LinkML (runtime + generators) | – | ~550k | Model → Pydantic/dataclasses, JSON Schema, TS, SHACL, OWL |

Gap the foundations leave (what rdf-persistence would add): identity map, unit of work /
transaction boundary across a remote SPARQL store (rdflib's SPARQLUpdateStore has no
rollback), object ↔ graph mapping, repository API, HTTP contract for JS clients.

## E. Reuse threshold applied (DEC-5: > 200★ and commit < 12 months)

**Qualify — Python, compatible with the stack (build on these):**
rdflib (2545), pyoxigraph/oxigraph (2021), SPARQLWrapper (570), LinkML (680; runtime +
generators), pySHACL (367), pydantic (29k); by inheritance: oxrdflib (oxigraph org).
Owlready2: mirror 218★ but stale; canonical repo is on Bitbucket (updated 2026-08-11) —
qualifies on activity, but ontology-centric, so not a persistence foundation.

**Qualify — JavaScript (the JS-friendly side reuses these, not us):**
N3.js (797), Comunica (620), rdflib.js (598), solid-client-js (244).

**Qualify but out of scope (own non-SPARQL stores / other stacks):**
TypeDB, TerminusDB, Atomic Server, Fluree, Ontop, LinkedDataHub (Java/XSLT platform),
neomodel (Neo4j) — design benchmarks only.

**Do NOT qualify (design study only):** every Python RDF ORM/mapper (sparqlmodel, triplemodel,
rdfmapper, rdfproxy, pydantic-rdf, rdflib-orm, SuRF, OldMan, RDFAlchemy), mu-semtech repos
(each < 20★), LDkit (83), LDflex (196), LDO (73), grlc (151), Prez (40), OBG-gen,
HyperGraphQL (stale), OWL-RL (181).

**Consequence:** no ORM/repository layer over SPARQL meets the bar → rdf-persistence writes that
layer itself, on top of the qualifying foundations; mu.semte.ch and the small mappers inform its
design.

## F. Explicit inclusions (DEC-6)

- **Owlready2** — ontology world: OWL classes ↔ Python classes, SQLite quadstore, HermiT/Pellet
  reasoning, own SPARQL engine. LGPL-3.0. Reuse question: can it serve the ontology-driven path
  (OWL model → persistent objects) next to the LinkML/SPARQL path, and does its store talk to
  external SPARQL endpoints (expected: no — embedded only; to verify in code).
- **semantic.works (mu.semte.ch, org `mu-semtech`)** — reference RAD architecture: domain
  config → JSON:API CRUD over SPARQL, SPARQL proxy (authorization + deltas), delta-notifier,
  JS/Python service templates.
