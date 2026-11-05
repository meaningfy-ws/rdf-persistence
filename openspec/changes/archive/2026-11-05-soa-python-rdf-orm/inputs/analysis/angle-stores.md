# Angle: stores & transactions (L2) + change events (L6)

- Change: `soa-python-rdf-orm` · round 3 · slug `angle-stores` · analyst run 2026-11-03
- Brief: `BRIEF-round3.md`; rubric `RUBRIC.md`; Fluree digest in `../brief-2026-11-03-mwb2-scope.md`
- Deep dives (clone + `gitnexus analyze` + code + docs), all shallow clones in `/home/lps/work/repos/`:

| Clone | Commit | Licence | GitNexus index |
|---|---|---|---|
| `fluree-db` (fluree/db) | 807902b (2026-11-02, v4.2.5 / v5.0.0-alpha.1) | **BUSL-1.1** → Apache-2.0 four years after each version (`LICENSE:1-51`) | 84 750 nodes, 248 780 edges, 300 flows (registered as repo `db`); full-text index missing, so queries returned nothing (see *Not checked*) |
| `oxigraph` (oxigraph/oxigraph) | 5b0ef09 (2026-11-02, after 0.5.13) | MIT OR Apache-2.0 | 877 files, 8 791 symbols, 23 765 edges |
| `rdflib` (RDFLib/rdflib, `main` = 8.0.0a0) | 114dd59 (2026-11-02) | BSD-3-Clause | 8 983 files, 29 620 symbols, 41 129 edges |
| `rdf-delta` (afs/rdf-delta) | 0a44c60 (2026-08-01) | Apache-2.0 | 413 files, 4 660 symbols, 14 463 edges |

Jena/Fuseki, RDF4J, GraphDB, Stardog and Virtuoso were desk-scanned from their docs and the
RDF4J OpenAPI spec only. They are too large to index, or closed source.

---

## 1. Headline findings

1. **Fluree has changed a lot since the 2024 evaluation. Most of the 2024 "losses" are now
   closed, and one new problem has appeared.**
   - Fluree v4 (2026-04-22) is a **rewrite in Rust** with a **W3C SPARQL 1.1 Query, Update and
     Graph Store Protocol** surface. It also has an official Python package, `fluree`
     (embedded engine, first published 2026-10-08), real multi-operation **transactions with
     optimistic conflict detection**, Turtle/TriG/JSON-LD **file load**, OIDC/JWKS bearer
     tokens, and **fail-closed policies** (`default-allow: false`).
   - **Still missing:** cascade delete ("To cascade, explicitly match and delete references",
     `docs/transactions/retractions.md:385`).
   - **New problem: the licence is now BUSL-1.1, not open source.** It forbids offering Fluree
     as a "Database Service", meaning letting third parties "define their own schemas … and use
     the Licensed Work to store … data under them" (`LICENSE:15-27`). An MWBv2 product in which
     *end users* define models could come close to that line. This needs a legal reading
     before adoption.
2. **"One SPARQL Update request = one atomic transaction" is the only atomicity guarantee the
   standard gives you portably.** Fuseki/TDB2 (serializable, multiple readers and a single
   writer), Oxigraph (repeatable read, all-or-nothing update), Fluree (`;`-separated operations
   commit as one), and RDF4J/GraphDB all honour it. Virtuoso honours it only in non-autocommit
   log mode (docs recommend `log_enable(2)` = row autocommit for big updates). semantic.works'
   sparql-parser breaks it on purpose, because it re-batches into ≤100-quad chunks
   (`semantic-works.md` §"Graphs"). **A Unit of Work that flushes once, as one
   `DELETE…INSERT…WHERE ; INSERT DATA …` request, is therefore the portable baseline.** rdflib
   already implements exactly this buffer-then-join in `SPARQLUpdateStore`
   (`rdflib/plugins/stores/sparqlstore.py:722-739`: `commit()` sends
   `"\n;\n".join(self._edits)`; `rollback()` drops the buffer).
3. **Transactions that span several requests exist only through vendor APIs.**
   - RDF4J REST `POST /repositories/{id}/transactions` → `PUT ?action=ADD|DELETE|UPDATE|QUERY|COMMIT`,
     `DELETE` = rollback (RDF4J OpenAPI spec, lines 1209-1436). This also covers GraphDB.
   - Stardog `/transaction/begin|commit|rollback` (pystardog `connection.py:97-137`).
   - Fluree only in-process: the `Transaction` in its Python package. Over HTTP each request is
     one commit, and "A Raft or peer host must not offer transactions to its clients"
     (`fluree-db-api/src/transaction.rs:36-40`).
   - **New since round 2:** rdflib ≥ 7.5 ships an httpx-based **RDF4J client with a
     `Transaction` context manager** (`rdflib/contrib/rdf4j/client.py:741-860`). rdflib 7.6 adds
     a **GraphDB client** that also manages GraphDB ACLs (`rdflib/contrib/graphdb/client.py:78-378`,
     `CHANGELOG.md:1-39`). Both qualify under DEC-5 because they belong to the rdflib org.
4. **Isolation is weaker than it looks in the embedded stores.**
   - Oxigraph's "repeatable read" RocksDB transactions are *snapshot read + WriteBatch*, with
     **no write-conflict detection** (`lib/oxigraph/src/storage/rocksdb_wrapper.rs:474-493,
     1047-1056`). Two concurrent read-modify-write transactions can therefore lose an update.
   - Oxigraph's in-memory backend serialises writers with a `transaction_lock`
     (`lib/oxigraph/src/storage/memory.rs:29,73-77`).
   - **Optimistic concurrency must therefore be enforced by the persistence layer.** The usual
     way is a *guarded update*: a version triple checked in the `WHERE` of the same update.
5. **Change events have no single standard.**
   - **RDF Patch** (`H id`/`H prev` header, `TX/TC/TA`, `A/D/PA/PD`) is the most standard-like
     delta format. It now lives in Apache Jena itself (module `jena-rdfpatch`). The stand-alone
     **RDF Delta** patch-log server (afs/rdf-delta) is announced as "going to be archived"
     (README line 3).
   - RDF Delta's patch log uses **compare-and-swap on the log head through `prev`**
     (`PatchLogBase.java:150-187`), which is a clean model for optimistic concurrency and
     idempotent replay that we can borrow.
   - Fluree publishes only *ledger-head* SSE events (`GET /v1/fluree/events`, `ns-record`). The
     facts of a commit are then pulled with `ledger.changes(commit)` / `GET /commits`.
   - semantic.works emits rich `changeSets` (insert/delete/effective*) from its proxy.
   - GraphDB's Kafka integration is mostly inbound (`Ontotext-AD/kafka-sink-graphdb`); the
     outbound Kafka connector was announced in 2021 and is not verified here.

---

## 2. Landscape table (desk scan)

Stars and pushes come from `gh api` and downloads from pypistats (last month) on 2026-11-03.
DEC-5 = >200★ AND a commit in the last 12 months; org/monorepo packages inherit.
Layers: L2 stores & transactions, L6 events, L3 authz (noted only), L4 service.

### 2a. Stores

| Store | Repo / stars / last push | Licence | Lang | DEC-5 | SPARQL Q / U / GSP | Atomic unit & isolation | Multi-request tx | Named graphs | JSON-LD native | Bulk load | History / time-travel | Ops footprint | Layers |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Apache Jena Fuseki + TDB2** | apache/jena 1 494★, 2026-11-02 | Apache-2.0 | Java | pass | 1.1 full / full / full | Each HTTP request is one TDB2 txn; **serializable**, MR+SW ([TDB txns](https://jena.apache.org/documentation/tdb/tdb_transactions.html)) | No over HTTP (embedded Jena API only) | yes | in/out (JSON-LD 1.1 via Titanium) | `tdb2.tdbloader` (offline) | No (RDF Patch / Delta for a change log) | 1 JVM, file-based DB; shiro auth; Fuseki modules | L2, L6 (via RDF Patch) |
| **Oxigraph** server / lib | oxigraph/oxigraph 2 021★, 2026-11-02; 30 contributors | MIT/Apache-2.0 | Rust | pass | 1.1 full / full / `/store` GSP (`server/README.md:73-85`) | One update/load = atomic; **repeatable read**, no write-write conflict detection (§1.4) | No (Rust `start_transaction` only, not exposed in Python or HTTP) | yes | **JSON-LD 1.1 in/out** (`lib/oxjsonld`, CHANGELOG "JSON-LD 1.1 … enabled by default") | `bulk_load` (non-atomic, parallel SST) | No | single binary / wheel; RocksDB; no built-in auth (nginx recipe, `server/README.md:123-150`) | L2 |
| pyoxigraph | (oxigraph monorepo) 267 k dl/mo, 0.5.13 2026-10-22 | MIT/Apache-2.0 | Rust/Py | pass (inherits) | in-process | `update`/`load`/`extend` atomic (`python/src/store.rs:116,317,382`) | — | yes | yes | `bulk_load` (`store.rs:502`) | No | `pip install` | L2 |
| oxrdflib | oxigraph/oxrdflib 56★, 27 k dl/mo | BSD-3 | Py | pass (inherits) | rdflib `Store` over pyoxigraph | as pyoxigraph | — | yes | via rdflib | — | No | pip | L2 |
| **Eclipse RDF4J server** | eclipse-rdf4j/rdf4j 423★, 2026-11-03 | BSD-3 | Java | pass | 1.1 full / full / full | per request + **REST transactions**; isolation levels NONE…SERIALIZABLE (Java API; whether HTTP exposes an isolation parameter was not confirmed in the OpenAPI) | **Yes**: `POST …/transactions` → `PUT ?action=…` → `COMMIT` / `DELETE` (OpenAPI lines 1209-1436) | yes | in/out | via txn / GSP | No | Tomcat/Jetty webapp | L2 |
| **Ontotext GraphDB** | closed; graphdb-docker 95★ | proprietary (Free edition) | Java | n.a. (product) | full / full / full (RDF4J protocol) | RDF4J-protocol txns; cluster | **Yes** (RDF4J REST) | yes | in/out (+ JSON-LD framing on export) | ImportRDF / LoadRDF offline, server import | No (plugins for change tracking: not verified) | heavy JVM, licensed cluster; built-in RBAC / graph ACL | L2, L3, L6 (Kafka/connectors) |
| **Virtuoso OS** | openlink/virtuoso-opensource 977★, 2026-10-26 | GPL-2.0 (OS ed.) | C | pass | 1.1 Q / U (non-strict) / GSP | **Weak**: docs advise `log_enable(2)` (row autocommit) for SPARUL; atomic only in manual-commit mode ([docs](https://docs.openlinksw.com/virtuoso/fn_log_enable)) | ODBC/JDBC only | yes | in/out | `ld_dir`/`rdf_loader_run` | No | single server, ini tuning, quirks | L2 |
| **Stardog** | closed; pystardog 42★, 64 k dl/mo | commercial (free tier) | Java | n.a. / client fail on stars | full / full / full | explicit txns | **Yes**: `/transaction/begin|commit|rollback` (pystardog `connection.py:97-137`) | yes | in/out | `db create` bulk | versioning (legacy) / CDC: not verified | licensed JVM | L2, L3 |
| **QLever** | ad-freiburg/qlever 935★, 2026-11-02 | Apache-2.0 | C++ | pass | 1.1 Q / U (since ~2025) / GSP ([docs](https://docs.qlever.dev/update/)) | updates are a delta layer over a static index; token-gated; atomicity semantics not documented | No | yes | output only | index build (very fast) | No | read-mostly, huge-scale; `PERSIST_UPDATES` flag | L2 (read model) |
| Blazegraph | blazegraph/database 987★, **archived** 2023 | GPL-2.0 | Java | **fail** (dead) | — | — | — | — | — | — | — | — | avoid |
| **Fluree DB v4** | fluree/db 477★, 2026-11-02; 15 contributors; v4.0.0 2026-04-22 | **BUSL-1.1** | Rust | pass on numbers; **licence not OSI** | SPARQL 1.1 Q "in progress toward full" (700+ W3C tests in CI) / U full except remote LOAD / GSP indirect only (`docs/reference/compatibility.md:86-189`) | one request (also `;`-multi-op) = one commit; serial per ledger | **In-process only** (Python `Transaction`, optimistic, §3.1); not over HTTP | yes | **native JSON-LD in/out + JSON-LD query** | Turtle/TriG/JSON-LD files, `insert_rows` DataFrames, "2M facts/s" bulk import (claimed) | **Yes**: `at(t=…)`, `history()`, branches, merge | single binary or Docker; S3/DynamoDB; Raft | L2, L3, L6 |
| fluree/server (Clojure v3) | 21★, 2026-01-29 | none | Clojure | fail | (legacy v3) | | | | | | | | legacy |
| **TerminusDB** | terminusdb/terminusdb 3 469★, 2026-11-02 | Apache-2.0 | Prolog/Rust | pass | **No SPARQL** (WOQL / GraphQL); JSON documents | commit per request, git-like | branches/merge | n.a. | JSON documents (not JSON-LD) | yes | **yes** (commits, diff) | single server | L2 (off-standard) |
| AllegroGraph | closed; agraph-python 49★ | commercial | Lisp | n.a. | full | sessions with commit/rollback (agraph-python) | **yes** (dedicated sessions) | yes | yes | agload | no | licensed | L2 |
| rdflib Memory / BerkeleyDB | rdflib 2 545★, 13 M dl/mo | BSD-3 | Py | pass | in-process SPARQL | Memory: none (wrap with `AuditableStore` undo log); BerkeleyDB: `transaction_aware`; `Graph.commit/rollback` delegate to the store | n.a. | yes | parse/serialize | slow | no | none | L2 (tests) |
| Amazon Neptune | — | AWS service | — | n.a. | full / full / no GSP (loader) | per request; Neptune Streams = CDC | no | yes | output | S3 bulk loader | Streams (24 h – 90 d) | managed | L2, L6 (note) |

### 2b. Python clients

| Client | Repo / stars / activity / dl·mo | DEC-5 | What it gives for tx / UoW | Notes |
|---|---|---|---|---|
| **rdflib `SPARQLUpdateStore`** | rdflib | pass | `autocommit=False` → buffer edits; `commit()` = **one** joined Update request; `rollback()` = drop buffer (`sparqlstore.py:639-739`) | Atomic only if the endpoint treats one request as one txn. Sync, `requests`/urllib based |
| **rdflib `contrib.rdf4j` client + `RDF4JStore`** (7.5.0, 2025-11-28) | rdflib | pass | `with repo.transaction() as txn:` → `query/update/upload/delete/commit/rollback` over RDF4J REST (`contrib/rdf4j/client.py:741-944`). `RDF4JStore` itself is `transaction_aware = False` (`plugins/stores/rdf4j.py:73`) | httpx; GSP manager; works with GraphDB |
| **rdflib `contrib.graphdb` client** (7.6.0, 2026-02-13) | rdflib | pass | inherits RDF4J Transaction; adds **ACL management**, cluster, import, monitoring (`contrib/graphdb/client.py`) | relevant to L3 (DEC-8: store-native ACL) |
| SPARQLWrapper | RDFLib/sparqlwrapper 570★, push 2026-04, last release 2.0.0 (2022) | pass (org) | none (raw request) | 1.4 M dl/mo; sync; stagnant releases |
| **pyoxigraph** | oxigraph | pass | atomic per call; `Store.update` multi-op; no multi-call txn | fastest embedded option for tests and single-node apps |
| oxrdflib | oxigraph org | pass | rdflib `Store` plugin | lets rdflib code run on Oxigraph |
| **`fluree` (PyPI, official)** | fluree/db monorepo; 4.2.5 (2026-11-01); first release 2026-10-08; pypistats 0 | pass on numbers (monorepo), **very young**, BUSL | `ledger.transaction()` and `ledger.transact(fn)` with retry; `ConflictError` (§3.1) | **embedded only**: no remote HTTP client. A remote Fluree is reached with any SPARQL 1.1 client |
| aioflureedb | dlosatoes/aioflureedb 5★, 2024-05 | **fail** | v1/v2 FlureeQL | obsolete with v4 |
| pystardog | stardog-union/pystardog 42★, 2026-09 | fail on stars (vendor SDK) | `Connection.begin/commit/rollback`, context manager | use only if Stardog is chosen |
| agraph-python | franzinc 49★ | fail (vendor SDK) | sessions | — |
| terminusdb-client | 80★ (org pass), last PyPI 2023-11 | pass (org) / stale | commits/branches | not SPARQL |
| sparqlx | lu-pl/sparqlx 6★, GPL-3.0 | **fail** → ideas | httpx async, streaming, batched | idea source only (noted in round 2) |
| rdf4j-python, graphdb-client (pmuston) | <10★ | fail | — | superseded by the rdflib contrib clients |

### 2c. Change events / deltas

| Mechanism | Repo / status | DEC-5 | Format | Transport | Ordering / CAS | Layers |
|---|---|---|---|---|---|---|
| **RDF Patch** (in Jena `jena-rdfpatch`) | apache/jena, active | pass | text/binary `H id`, `H prev`, `TX/TC/TA`, `A/D/PA/PD` ([spec](https://jena.apache.org/documentation/rdf-patch/)) | file / HTTP | `prev` chain | L6 |
| **RDF Delta** patch-log server | afs/rdf-delta 92★, 2026-08, **"going to be archived"** | fail (stars; archiving) | RDF Patch | HTTP patch log, Zookeeper/S3 HA Fuseki | **CAS on log head** (`PatchLogBase.java:150-187`), idempotent replay of the head patch (l.160-164) | L6 → borrow ideas |
| semantic.works delta-notifier + sparql-parser | mu-semtech (see `semantic-works.md`) | org fails stars (delta-notifier 0★) | `changeSets{insert,delete,effectiveInsert,effectiveDelete}` | HTTP POST fan-out with rules | `sequenceId`; no CAS | L6 → borrow format |
| Fluree events + commit log | fluree/db | pass/BUSL | SSE `ns-record` (head moved) + `GET /commits`, `ledger.changes(commit)` (`_connection.py:842-851`) | SSE + pull | monotonic `t`, commit ids | L6 |
| Solid Notifications Protocol | solid/notifications 11★ (spec); CSS 610★ | spec / CSS pass | AS2 JSON-LD notifications | WebSocket / Webhook / SSE channels | per resource | L6 (LDP-oriented) |
| GraphDB Kafka sink / connector | Ontotext-AD/kafka-sink-graphdb 7★ (inbound) | fail (stars), product | RDF payloads | Kafka | — | L6 (inbound) |
| Neptune Streams | AWS | n.a. | change records | REST poll | commitNum/opNum | L6 (note) |
| App-level outbox → Kafka/NATS | pattern | — | RDF Patch or changeSets JSON | broker | outbox sequence | L6 (pattern) |

---

## 3. Deep dives

### 3.1 Fluree DB v4 (fluree/db, mandatory)

**Summary.** Fluree v4 is a Rust monorepo of about 60 crates (`ls fluree-db-*`): ledger,
transact, query, sparql, shacl, policy, cypher, graphql, server, python, wasm and others. It
is now a **standards-speaking** RDF store with ledger semantics: immutable commits, `t`, time
travel, branches and merge. It also offers JSON-LD as a first-class write and query language,
and a fail-closed, data-centric policy engine. The Python package embeds the engine in-process
(PyO3), so it is not a client of a remote server.

**Re-check of the 2024 evaluation (open action in the digest).**

| 2024 finding | 2026-11 status | Evidence |
|---|---|---|
| No real SPARQL 1.1 endpoint (FlureeQL lock-in) | **Closed.** SPARQL 1.1 Query ("in progress toward full", 700+ W3C tests run in CI), Update "supported except remote LOAD", GSP with indirect graph identification, Service Description | `docs/reference/compatibility.md:86-200`; `testsuite-sparql/`; `docs/api/endpoints.md:368-382` |
| No Python client (aioflureedb immature) | **Closed, but very young.** Official `fluree` wheel (embedded), typed (`py.typed`, `_fluree.pyi`), pandas/polars, async module `aio.py`. First PyPI release 2026-10-08 | `fluree-db-python/README.md`; `python/fluree/` |
| No bulk file load | **Closed.** `insert(path)` for Turtle/TriG/JSON-LD; `insert_rows` DataFrames; `/import` `.flpack`; `sync` diff-load | README "Writing"; `docs/api/endpoints.md:787` |
| v3 closed-mode / policy docs missing | **Closed.** `default-allow: false` = fail-closed, "Recommended for production"; `f:required` gates; policies in SPARQL or JSON-LD WHERE with `$identity` | `docs/security/policy-model.md:5-38,233-248` |
| JWT identity policies (test needed) | Now supports did:key-signed requests and **OIDC/JWKS bearer tokens** (`--jwks-issuer`); identity comes from the `fluree.identity` claim | `docs/security/authentication.md:27-74` |
| No cascade delete | **Still open** (only edge-annotation cascade) | `docs/transactions/retractions.md:198-216,385` |
| No OTM/ORM | Still none for Python; Cypher/GraphQL surfaces exist | `fluree-db-graphql`, `fluree-db-cypher` |
| No UI | Browser crate / CLI exist; no admin UI was assessed | `fluree-db-browser/` (not read) |
| Licence (2024: open source) | **Now BUSL-1.1**, with the "Database Service" restriction; becomes Apache-2.0 after 4 years per version | `LICENSE:1-51`; `docs/reference/license-faq.md` |

**Transactions (code).**
- `fluree_db_api::Transaction` (`fluree-db-api/src/transaction.rs:156-174`) holds `base`,
  `base_head`, a `SequentialStager` and a list of staged operations, plus a `read: AtomicBool`.
- Each `stage()` validates the operation against policy, SHACL and uniqueness as it is added
  (l.1-12). `commit()` (l.396+) writes one commit.
- **Optimistic concurrency:**
  - If another commit has landed and the transaction was **not read**, it re-bases, or stages
    every operation again against the new head.
  - If it **was read** (via `db()` or Cypher `RETURN`), it raises `TransactError::CommitConflict`
    (module doc l.14-28; check at l.428).
  - Python maps this to `fluree.ConflictError` (`fluree-db-python/src/error.rs:42-82`, HTTP
    409). `ledger.transact(fn)` reruns `fn` on conflict.
- This is a textbook **optimistic UoW with automatic retry**.
- **Limits:**
  - Only for "local-commit deployments": a Raft or peer host "must not offer transactions to
    its clients" (l.36-40).
  - Over HTTP, atomicity is per request. The only compare-and-swap is the guarded
    `WHERE`/`FILTER` pattern (`docs/transactions/conditional-updates.md`). No `If-Match` or
    expected-`t` header was found on `/update` (grep `fluree-db-server/src`; the `ETag` handling
    in `routes/storage_proxy.rs:357-522` covers storage-proxy reads only).

**Events.**
- `GET /v1/fluree/events` is SSE of **nameservice** records (ledger head moved), available
  only on transaction servers (`docs/api/endpoints.md:2996-3017`). It exists for query peers,
  not as a fact-level CDC feed.
- Fact-level changes come from `GET /commits/*ledger`, `GET /show/*ledger` (policy-filtered),
  and Python `ledger.changes(commit)` / `history(subject)`. `history` is implemented as a
  SPARQL query over `<< s p o >> f:t ?t ; f:op ?op` (`_connection.py:800-834`).
- A consumer therefore follows the SSE stream and then pulls deltas.

**Scores (store-angle reading of the rubric).**

| # | Score | Justification | Evidence |
|---|---|---|---|
| C1 | 4 | Store-side: tx + rollback, named graphs, typed/lang literals, JSON-LD in/out, SHACL, history. No cascade, no ORM | sections above |
| C2 | 4 | Clear Transaction/Savepoint/Stager design, optimistic CC, immutable ledger | `transaction.rs:100-174` |
| C3 | 4 | Typed Python API, context managers, rich docs (mdBook `docs/`, 30+ pages). Young | `fluree-db-python/README.md` |
| C4 | 4 | `pip install fluree`, `:memory:` mode, single binary server | README "Install"; `_connection.py:101-136` |
| C5 | 3 | Re-implements everything (it *is* a database); speaks W3C standards | crate list |
| C7 | 4 | SPARQL 1.1 Q/U/GSP; GSP indirect only; Q "in progress"; LOAD remote unsupported | `compatibility.md` |
| C9 | 3 | Standards plus OIDC are good; the licence and extension-heavy features (FlureeQL, `f:` vocab, branches) create a soft lock-in | `LICENSE`; `docs/` |
| C10 | 3 | Rapid churn (v4.0 April → v4.2.5 Nov → v5 alpha in Oct), very detailed changelog in docs; otel tracing | releases; `otel/` |
| C8 | 4 | Huge test suites (W3C SPARQL and SHACL), CI, 15 contributors; one company | `testsuite-*`; contributors API |

**Verdict: integrate, behind the store port, as an optional backend.** Do not make it the
default until (a) a legal check of BUSL against the MWBv2 product model is done, and (b) the
Python package has matured, since it is one month old. The cheapest way in is
**SPARQL-over-HTTP (S2/S3)**, which keeps rdf-persistence portable; the embedded `fluree`
package then becomes an in-process adapter with real transactions. **Borrow:** the optimistic
transaction model (re-base if unread, `ConflictError` if read) and `transact(fn)` retry.

### 3.2 Oxigraph / pyoxigraph / oxrdflib

**Summary.** Oxigraph is a Rust SPARQL 1.1 database (RocksDB or in-memory). It ships as a
server, a CLI, Python (pyoxigraph), JS/WASM and an rdflib plugin (oxrdflib). It has the best
standards fidelity per byte of dependency, and **JSON-LD 1.1 is now in/out natively**
(`lib/oxjsonld`; CHANGELOG "JSON-LD 1.1 is now implemented and enabled by default").

**Implementation (code).**
- **Isolation:** `Store` guarantees "repeatable read … no partial writes" (`lib/oxigraph/src/store.rs:70-72, 372-378`).
- **Transactions:** `start_transaction()` (l.406) returns a `RocksDbStorageReadableTransaction`.
  It is built from a RocksDB snapshot plus `writebatch_wi` (`rocksdb_wrapper.rs:474-493`), and
  `commit()` is a plain `rocksdb_write_writebatch_wi` (l.1047-1056). There is **no conflict
  check**, so concurrent read-modify-write is last-writer-wins. Docs warn that a transaction
  "keeps the complete set of changes into memory" (l.384-385).
- **In-memory backend:** writers are serialised via `transaction_lock` (`storage/memory.rs:29,73-77`),
  with MVCC versions (`version_counter`).
- **Python:** atomic `update`, `load`, `extend` (`python/src/store.rs:116,317,382`) and a
  non-atomic `bulk_load` (l.502). **There is no Python-level `start_transaction`** (grep finds
  only docstrings). Multi-statement atomicity in Python means one `update()` with `;`-joined
  operations.
- **Server:** `/query`, `/update`, `/store` (GSP), and dataset-level TriG/N-Quads PUT/POST
  (`server/README.md:73-85`). There is no auth; the README recipe puts nginx basic-auth in front
  (l.123-150).
- GitNexus: process flows `Serve → Snapshot`, `Serve → StorageReader` link HTTP serving to snapshots.

| # | Score | Justification |
|---|---|---|
| C1 | 3 | Store primitives only: atomic updates, named graphs, JSON-LD; no explicit multi-call tx in Python or HTTP; no history |
| C2 | 4 | Clean storage abstraction (memory / RocksDB behind one `Storage`), snapshots |
| C3 | 4 | Typed Python stubs, doctests in docstrings, good docs |
| C4 | 5 | `pip install pyoxigraph`; same engine in-memory, on disk and as server |
| C5 | 4 | Own parsers, but a W3C-conformant stack (`testsuite/`) |
| C7 | 5 | SPARQL 1.1 Q/U/GSP |
| C9 | 5 | Pure standards; rdflib bridge (oxrdflib); JS/WASM build |
| C10 | 4 | Single binary, small surface, semver (0.x), frequent releases |
| C8 | 5 | 2 021★, 30 contributors, W3C test suites, fuzzing (`fuzz/`) |

**Verdict: adopt** as the default embedded and test store (S1) and as a lightweight server
option. In-process concurrent writers need application-level optimistic checks (guarded
updates).

### 3.3 rdflib stores and clients (`main`, 8.0.0a0; released features ≤ 7.6.0)

- **`SPARQLUpdateStore`** (`plugins/stores/sparqlstore.py`):
  - `autocommit=True` by default; `autocommit=False` buffers SPARQL strings in `_edits` (l.722-725).
  - `commit()` sends them as **one request joined with `;`** (l.728-736); `rollback()` discards
    them (l.738-739).
  - `dirty_reads=False` forces a commit before every read (l.675-696), so reading inside the
    UoW silently flushes. This is a pitfall for a UoW.
  - This is the "local buffer + single request" UoW in its simplest form. There is no conflict
    detection.
- **`AuditableStore`** (`plugins/stores/auditable.py:1-12`): wraps any store, keeps a
  **reverse-operation log**, and replays it on `rollback()`. In its own words this is "A and I
  out of ACID", no durability. It is the canonical **compensation** pattern, already in a
  DEC-5-passing library (GitNexus: process `Rollback → Triples`; tests
  `test/test_store/test_store_auditable.py::test_commit_rollback`).
- **`contrib.rdf4j`** (7.5.0) and **`contrib.graphdb`** (7.6.0):
  - httpx-based clients (optional extra `rdflib[rdf4j]`, `rdflib[graphdb]`, `pyproject.toml:45-46`).
  - `Transaction.create` → `POST /repositories/{id}/transactions`; `commit` → `PUT ?action=COMMIT`;
    `rollback` → `DELETE` (`contrib/rdf4j/client.py:810-856`); also `query/update/upload/get/delete`
    inside the transaction (l.899-1044).
  - The GraphDB client adds `AccessControlListManagement` (l.78-376), which is relevant to DEC-8
    "store-native policies".
  - `RDF4JStore` (Graph/Dataset over RDF4J) is **not** transaction-aware (`plugins/stores/rdf4j.py:73`).
    Transactions are reached only through the client.
- BerkeleyDB store: `transaction_aware` flag (`berkeleydb.py:91,162`). It is niche.

Scores (store-angle): C1 3 · C2 3 · C3 3 · C4 5 · C5 5 · C7 4 (SPARQLStore portable; RDF4J
client vendor-protocol) · C9 5 · C10 4 · C8 5 (2 545★, 13 M dl/mo).
**Verdict: adopt.** rdflib is already the MWBv2 foundation. Use `SPARQLUpdateStore`'s buffering
idea, but put our own UoW above it, because reading inside a transaction must not flush. Wrap
`contrib.rdf4j.Transaction` as the RDF4J/GraphDB transactional adapter.

### 3.4 RDF Delta / RDF Patch

- **RDF Patch** is a simple line format with transaction brackets and `id`/`prev` headers. It
  is part of Apache Jena (`jena-rdfpatch`) and so is maintained with Jena.
- **RDF Delta**:
  - It is a patch-log server (local/file/RocksDB/S3/Zookeeper stores:
    `rdf-delta-server-local/.../patchstores/{mem,file,rdb}`) plus a Fuseki integration for
    HA-replicated datasets.
  - `DeltaLinkLocal.append` (l.197-220) runs `beforeWrite`, `patchLog.append` and
    `afterWrite`, then fires `listener.append` events.
  - `PatchLogBase.append` (l.150-187), under a log-wide lock:
    - it treats a re-sent head patch as idempotent;
    - it validates that `prev` equals the current head (`PatchValidation.validateNewPatch`),
      i.e. **compare-and-swap**;
    - it stores the patch, then saves the index, and deletes the patch if the index save
      fails (compensation).
  - GitNexus surfaces processes `Append → GetPreviousId`, `Append → DeltaException`.
- **Status:** README line 3 says "This project is going to be archived". It has 92★ and fails
  DEC-5 as a dependency.

**Verdict: borrow ideas** (RDF Patch as a delta wire format; `prev`-hash CAS for optimistic
concurrency; idempotent replay; a patch log as the event outbox). Use Jena's RDF Patch (DEC-5
pass) if a JVM component is acceptable. A Python RDF Patch writer is small: `A`/`D` lines in
N-Triples/N-Quads syntax.

---

## 4. Patterns catalogue (L2 / L6)

| # | Pattern | Atomicity | Concurrency | Where seen | Portability |
|---|---|---|---|---|---|
| P-a | **Single-request flush**: UoW collects new/dirty/removed objects, computes a triple diff, sends **one** Update (`DELETE {…} INSERT {…} WHERE {…} ; INSERT DATA {…} ; DELETE DATA {…}`) | store-guaranteed per request (Fuseki, Oxigraph, RDF4J, GraphDB, Fluree; **not** Virtuoso autocommit, **not** behind mu sparql-parser) | none by itself | rdflib `SPARQLUpdateStore` (`sparqlstore.py:728-736`); Fluree multi-op Update | **any SPARQL 1.1 endpoint** |
| P-b | **Guarded update (CAS in WHERE)**: each aggregate root carries a version triple (`ex:version 7` or a hash); flush = `DELETE {… ?root ex:version 7} INSERT {… ex:version 8} WHERE { ?root ex:version 7 … }`; zero rows matched → conflict | per request | optimistic, per aggregate | Fluree `conditional-updates.md`; generic SPARQL | any endpoint. **Caveat:** SPARQL Update returns no "rows affected", so confirm with a follow-up `ASK` for the new version, or use a unique per-flush token triple (`ex:lastTx <uuid>`) |
| P-c | **Vendor multi-request transaction** (begin → ops → commit/rollback) | real ACID | store isolation (RDF4J levels, Stardog, GraphDB) | rdflib `contrib.rdf4j.Transaction`; pystardog; Fluree embedded | vendor protocol behind an adapter |
| P-d | **Embedded optimistic transaction with retry** (re-base if unread, conflict if read; `transact(fn)` retries) | ACID, single process | optimistic + retry | Fluree `transaction.rs`; `ledger.transact` | Fluree only; idea portable to our UoW |
| P-e | **Compensation / undo log**: apply ops one by one, record inverses, replay on failure | best-effort (no durability) | none | rdflib `AuditableStore`; RDF Delta patch-delete-on-index-failure | any store; fallback for stores without P-a (Virtuoso autocommit, chunking proxies) |
| P-f | **Named-graph swap** (write to a staging graph, then `MOVE`/`COPY` or a GSP `PUT`) | atomic graph replace | last-writer-wins per graph | GSP `PUT`; Fluree `sync` commits only the diff | any endpoint with GSP; good for document-centric aggregates (one graph per aggregate) |
| P-g | **ETag / If-Match on GSP graph** | per request | optimistic per graph | HTTP semantics; not found in Fuseki/Oxigraph/Fluree GSP as conditional writes (unverified for others) | only if a proxy adds it → borrow for our own data-management service (L4) |
| P-h | **Patch log with prev-CAS** (RDF Patch `H prev`) | log append atomic | optimistic on the log head | RDF Delta `PatchLogBase.append` | needs a log server, or our outbox |
| P-i | **Transactional outbox for deltas**: the same flush also inserts a change record (in a `<urn:outbox>` graph, as RDF Patch or changeSets JSON); a relay publishes it to SSE/Kafka/webhooks | atomic with the data (same Update) | ordered by sequence | idea; semantic.works emits from its proxy instead | any endpoint (P-a) |
| P-j | **Proxy-emitted deltas** (CDC at the SPARQL proxy) | depends on proxy (mu re-batches!) | — | semantic.works sparql-parser → delta-notifier | stack-specific |
| P-k | **Ledger history / time travel as the audit trail** | n.a. | n.a. | Fluree `at(t)`, `history()`, `changes()` | Fluree only (others need P-i / P-h) |
| P-l | **Head-moved notification + pull** | n.a. | n.a. | Fluree SSE `ns-record` + `/commits` | Fluree; generic idea |

### Recommended UoW layering for rdf-persistence (ACL-agnostic)

```
UnitOfWork (domain-facing, cosmic-python)  ── identity map, new/dirty/removed sets
   │ flush(): diff → ChangeSet (inserts, deletes, guards, outbox record)
   ▼
TransactionalStore port  (capabilities: single_request_atomic, multi_request_tx, history)
   ├─ SparqlHttpAdapter      → P-a + P-b (+ P-i)     Fuseki, Oxigraph server, Fluree HTTP, GraphDB/RDF4J, QLever
   ├─ Rdf4jTxAdapter         → P-c (rdflib.contrib.rdf4j)   RDF4J, GraphDB
   ├─ PyOxigraphAdapter      → P-a in-process (+ lock / P-b for writers)
   ├─ FlureeEmbeddedAdapter  → P-c/P-d (fluree.Transaction / transact)
   └─ RdflibMemoryAdapter    → P-e (AuditableStore) for tests
```

- The port carries opaque **request context** (bearer token / headers: X13). The persistence
  layer therefore works behind an authorizing proxy (mu sparql-parser, a GraphDB/Fluree policy,
  any OIDC-protected SPARQL endpoint) and holds no ACL logic (DEC-8).
- Capability flags let the UoW choose: P-c if the store offers it, else P-a, else P-e. It must
  warn when atomicity degrades (for example Virtuoso autocommit, or a chunking proxy).

---

## 5. How each option plugs into the MWBv2 chain

UML → model2owl/LinkML → generated Pydantic domain → **rdf-persistence (repositories + UoW)** →
FastAPI data-management service → JS/TS UI (JSON-LD).

| Option | Plugs in at | JSON-LD to the UI | Authz (DEC-8) | Events to the UI / services |
|---|---|---|---|---|
| Oxigraph (embedded or server) | S1/S2/S3 adapter; tests | service serialises (rdflib / pyoxigraph JSON-LD 1.1) | proxy in front (nginx/OIDC proxy); no native ACL | outbox (P-i) → SSE from the service |
| Fuseki/TDB2 | S2/S3 adapter | service, or Fuseki JSON-LD output | Fuseki shiro / graph-level dataset security; or a proxy | RDF Patch (Jena) / outbox |
| RDF4J / GraphDB | S2/S3 + transactional adapter via `rdflib.contrib.rdf4j` | GraphDB JSON-LD (+ framing on export) | **GraphDB native RBAC/graph ACLs**, manageable from Python (`contrib.graphdb` ACL manager) | outbox; GraphDB connectors (not verified) |
| Fluree v4 | S2/S3 over HTTP (portable) **or** an embedded adapter | **native JSON-LD in/out; JSON-LD query with nested @id** — the UI could even query a policy-guarded Fluree almost directly (MWBv2 runbook idea) | **native, data-centric, SPARQL/JSON-LD policies + OIDC** (closest match to the DEC-8 preference) | SSE head events + `/commits` pull; history for audit |
| semantic.works stack (sparql-parser + Virtuoso) | S2 adapter behind mu-auth | via mu-cl-resources (JSON:API) or our service | mu-auth graph ACL (query rewriting) | delta-notifier changeSets |
| QLever | read-model / analytics endpoint (S5 read/write split) | output only | token for updates only | none |
| TerminusDB | off-standard; would need its own adapter (no SPARQL) | JSON documents | own RBAC | commits/diff |

## 6. Architecture variants enabled

| Variant | Store choice | Atomicity / concurrency | Events | Notes |
|---|---|---|---|---|
| **V-A "Portable SPARQL"** (default) | Any SPARQL 1.1 endpoint; Oxigraph for dev/test, Fuseki or GraphDB in prod | P-a + P-b | P-i outbox in a named graph → relay (SSE/webhook/Kafka) | Maximum portability; ACL via an OIDC-aware SPARQL proxy |
| **V-B "Vendor-transactional"** | RDF4J / GraphDB | P-c via `rdflib.contrib.rdf4j`; isolation by the store | outbox or GraphDB connector | Real multi-request tx; GraphDB ACLs managed from Python; licensed for the cluster |
| **V-C "Ledger-native" (Fluree)** | Fluree v4 server (HTTP SPARQL) + optional embedded | per-request + guarded WHERE (HTTP); P-d embedded | SSE + commit pull; history as the audit log | Best fit for data-centric policies + JSON-LD UI + time travel; **BUSL and maturity risk**; no cascade delete |
| **V-D "semantic.works-compatible"** | Virtuoso behind sparql-parser | **degraded**: the proxy chunks updates (≤100 quads) → P-e compensations + P-b guards | delta-notifier changeSets (consume/produce compatible format) | Reuses the mu ecosystem; weakest atomicity |
| **V-E "Embedded single-node"** | pyoxigraph (RocksDB) in the service process | P-a + a process-local writer lock or P-b | in-process outbox → SSE | Simplest operations (one container); no horizontal scale for writes |
| **V-F "CQRS read model"** | Write: any of the above; Read: QLever/Oxigraph replica fed from the outbox / RDF Patch | write side as chosen | outbox drives the projection | for large read workloads (X10) |

---

## 7. Feature inventory for this angle (existing taxonomy ids)

| Id | Feature | Best available evidence |
|---|---|---|
| S1 | In-memory store | pyoxigraph `Store()`, rdflib Memory, `fluree.connect(":memory:")` |
| S2 | Remote SPARQL Q+U | all stores in §2a except TerminusDB; clients: SPARQLUpdateStore, SPARQLWrapper |
| S3 | GSP | Fuseki, Oxigraph `/store`, RDF4J/GraphDB, Fluree (indirect only), QLever; client `contrib.rdf4j.GraphStoreManager` |
| P3 | UoW / session flush | partial in rdflib `SPARQLUpdateStore(autocommit=False)`; full in Fluree embedded `Transaction` |
| P4 | Transactions local and remote | RDF4J REST (rdflib client), Stardog, Fluree embedded; per-request elsewhere |
| P5 | Optimistic concurrency | Fluree `ConflictError`; RDF Delta `prev`-CAS; otherwise guarded WHERE (P-b) |
| P13 | Transaction options | Fluree `TransactionOptions` (governance, fuel tracking, index config) (`transaction.rs:117-128`); RDF4J isolation levels |
| P15 | Concurrency mode | TDB2 MR+SW; Oxigraph memory writer lock; Fluree serial per ledger |
| X5/X12 | Change notifications / delta format | RDF Patch; mu changeSets; Fluree SSE+commits; Solid Notifications |
| S5 | Read/write split | QLever / Fluree peers (query peers via SSE) |
| S11 | Embedded store admin | pyoxigraph `backup/optimize/flush` (`store.rs:790-827`); Fluree branch/drop/reindex |

### Proposed new features (new prefixes T*, E*; S* continued)

| Proposed id | Area | Feature | Seen in |
|---|---|---|---|
| T1 | Transactions | **Single-request atomic flush**: the UoW compiles all changes into one SPARQL Update request (multi-operation, `;`) | rdflib SPARQLUpdateStore; Fluree |
| T2 | Transactions | **Guarded update / compare-and-swap in WHERE** on a per-aggregate version or token triple, with conflict detection | Fluree conditional updates; generic |
| T3 | Transactions | **Vendor multi-request transaction adapter** (begin/ops/commit/rollback over HTTP) | RDF4J REST via rdflib contrib; Stardog; GraphDB |
| T4 | Transactions | **Compensating rollback / undo log** when the store cannot do atomic multi-op | rdflib AuditableStore; RDF Delta |
| T5 | Transactions | **Read-your-writes inside a transaction** (queries see staged changes without flushing) | Fluree `txn.query`; RDF4J txn QUERY; *anti-example*: rdflib `dirty_reads=False` flushes |
| T6 | Transactions | **Automatic retry of a transactional function on conflict** (`transact(fn)`) | Fluree |
| T7 | Transactions | **Store capability descriptor** (atomic-per-request, multi-request tx, isolation level, history, GSP, JSON-LD) used to choose the strategy and warn on degradation | idea (none found) |
| T8 | Transactions | **Savepoints** inside a transaction | Fluree `Savepoint` (`transaction.rs:104-110`) |
| T9 | Transactions | **Idempotent writes / idempotency key** (safe client retry after a timeout) | Fluree upsert idempotent, `Idempotency-Key` on `/push`; RDF Delta head-replay |
| S15 | Stores | **Time travel / as-of queries and per-subject history** | Fluree `at(t)`, `history()`; TerminusDB |
| S16 | Stores | **Branching and merge of datasets** | Fluree, TerminusDB |
| S17 | Stores | **Diff-load / sync** (make a graph equal to a document, committing only the difference) | Fluree `sync`, GSP `PUT` as sync |
| S18 | Stores | **Bulk loader path separate from transactional writes** (non-atomic, fast) | pyoxigraph `bulk_load`, TDB2 loader, Fluree import |
| S19 | Stores | **Commit metadata** (message, author identity, `t`, digest) on every write | Fluree `Commit` |
| E1 | Events | **Transactional outbox** written in the same atomic update as the data | pattern (none found in RDF libs) |
| E2 | Events | **RDF Patch as the delta wire format** (`id`/`prev`, TX/TC) | Jena RDF Patch, RDF Delta |
| E3 | Events | **Head-moved notification + delta pull** (SSE/webhook, then fetch commits) | Fluree events + `/commits` |
| E4 | Events | **Effective vs requested changes** in deltas (no-op inserts and deletes removed) | semantic.works `effectiveInsert/Delete` |
| E5 | Events | **Subscription rules / filters on deltas** (s/p/o patterns, graph, type) | mu delta-notifier rules; Solid notification channels |
| E6 | Events | **Policy-filtered change feeds** (subscribers see only the facts they may read) | Fluree `changes()` under `with_policy`; mu `allowedGroups` (dropped by the notifier) |
| E7 | Events | **Ordered, gap-detectable sequence** (sequenceId / `t` / prev hash) so consumers can resume | Fluree `t`; RDF Delta versions; mu `sequenceId` |

---

## 8. Open questions

1. **Fluree licence:** does an MWBv2-built product in which *customers* define schemas fall
   under the BUSL "Database Service" exclusion (`LICENSE:15-27`, carve-out (i) requires that
   "you, not those third parties, define the schema")? This needs a legal or commercial
   conversation with Fluree, PBC before V-C.
2. **Default atomic strategy:** should the UoW *require* single-request atomicity (P-a) and
   refuse to run on degrading stacks (mu sparql-parser chunking, Virtuoso autocommit), or
   degrade to compensations (P-e) with a warning?
3. **Optimistic concurrency granularity:** a version triple per aggregate root (P-b), or a
   named graph per aggregate with GSP/ETag (P-f/P-g)? The choice interacts with the
   graph-level ACL of DEC-8 (graph-per-aggregate eases graph ACLs but multiplies graphs).
4. **Conflict detection without "rows affected":** SPARQL Update returns no match count. Is a
   follow-up `ASK` (two round-trips, not atomic with the write but sufficient to *detect*)
   acceptable, or should the adapter use vendor transactions where available?
5. **Events:** should rdf-persistence emit deltas itself (E1 outbox, store-agnostic), or rely
   on store/proxy CDC (Fluree, mu)? What format: RDF Patch (E2) or mu-compatible changeSets
   (E4)? Both are easy to produce from the flush ChangeSet.
6. **Fluree embedded vs server:** embedded transactions are refused on Raft/peer hosts. Is a
   single-writer Fluree process acceptable for MWBv2 deployments?
7. **Cascade delete:** Fluree still lacks it, and so does every store here. Should
   aggregate-boundary deletion (delete the root and owned parts, and dangling inbound
   references) live in rdf-persistence's mapper (model-driven from LinkML `inlined` /
   composition)?

## 9. Not checked

- The Fluree GitNexus index finished after the report was written (repo name `db`). Its
  full-text index is missing ("FTS indexes missing … run `gitnexus analyze --repair-fts`"),
  so `query` and `cypher` returned nothing. Fluree evidence is from direct source and doc reading (`transaction.rs`,
  `error.rs`, `_connection.py`, `docs/**`). No Fluree code was run; the performance claims are
  the vendor's.
- Jena/Fuseki, RDF4J server, GraphDB, Stardog, Virtuoso, QLever, AllegroGraph and Neptune are
  desk-only. The RDF4J HTTP isolation-level parameter, GraphDB change tracking/outbound Kafka,
  Stardog CDC and QLever update atomicity were not verified.
- No store was run; the isolation claims for Oxigraph are from code reading
  (`rocksdb_wrapper.rs`), not from a concurrency test.

---

## Round 4

Leader brief: `BRIEF-round4.md`. Inputs re-read: `index.adoc`, `building-blocks.adoc`,
`variants.adoc`, `catalogue.adoc`, `feature-taxonomy.adoc` (v3), `angles/stores.adoc`.
New evidence: the finished GitNexus index of `fluree-db`, registered as repo **`db`**
(2 620 files, 84 750 symbols, 248 780 edges, commit 807902b). Its full-text index is missing,
so `query` returns nothing; `cypher` works and is used below.

### R4.0 Fluree transaction claims re-checked with GitNexus

| Round-3 claim | GitNexus / code check | Result |
|---|---|---|
| `Transaction` holds base, base_head, stager, ops and a `read` flag | `cypher` on `fluree-db-api/src/transaction.rs`: Struct `Transaction` l.155, Properties `base` l.158, `base_head` l.159, `stager` l.160, `read` l.169; Struct `Savepoint` l.104; Struct `TransactionOptions` l.116 | **confirmed** |
| Commit re-bases blind writes and fails read transactions | `commit` (Function l.395) CALLS `rebase_stage`, `is_retryable_commit_conflict` (`tx_builder.rs`), `commit_contention` (`error.rs`), `transact_policy`, `stage_all`. Body: under `lock_for_write`, `if read && !unchanged → CommitConflict{expected_t, head_t}` (l.418-431) | **confirmed, refined**: the engine itself loops up to `MAX_RETRIES = 16` re-base/re-stage attempts (l.419) before giving up. The policy is re-evaluated against the new head |
| Multi-operation transactions are embedded-only, not over HTTP | `cypher` finds no CALLS edge into `begin_transaction`; grep finds a single caller, `fluree-db-python/src/transaction.rs:47` (none in `fluree-db-server`, `fluree-db-bolt`, `fluree-db-cli`) | **confirmed** |
| Savepoints (T8) | Functions `savepoint` l.276 and `rollback_to` l.291 exist in the Rust API. Python uses them only internally, to roll back a failing Cypher script (`fluree-db-python/src/transaction.rs:152-176`); they are not exposed in `fluree/_connection.py` | **corrected**: savepoints are Rust-only, not a Python feature |
| Writes are serialised per ledger | `commit` takes `handle.lock_for_write()` (l.424) | **confirmed** |

### R4.a v3 cross-check (102 v3 features × 4 deep-dived candidates)

Codes: **P** present · **p** partial · **A** absent · **n.a.** not applicable to a store or
store client. Absences were confirmed by grep over the clones (patterns cited where useful).
Range rows (G1-G11, G13-G27, U1-U10) are n.a. for every candidate: they are generation or UI
features. Mapping to my round-3 ids follows the taxonomy appendix: my E4 "effective vs
requested" and E5 "subscription rules" are folded into **X12**; my E6/E7 became **E4/E5**.

| Candidate | P | p | A | n.a. |
|---|---|---|---|---|
| Fluree v4 (+ `fluree` PyPI) | 27 | 11 | 17 | 47 |
| Oxigraph / pyoxigraph / oxrdflib | 3 | 5 | 46 | 48 |
| rdflib stores + contrib clients | 4 | 12 | 39 | 47 |
| RDF Delta / RDF Patch | 4 | 6 | 39 | 53 |

| v3 Id | Fluree v4 (+ `fluree` PyPI) | Oxigraph / pyoxigraph / oxrdflib | rdflib stores + contrib clients | RDF Delta / RDF Patch | Evidence |
|---|---|---|---|---|---|
| AZ1 | P | A | p | A | Fluree: identity/policy-wrapped view (`docs/security/programmatic-policy.md`, `wrap_identity_policy_view`); rdflib: GraphDB client manages repo ACLs, no request-scoped narrowing (`contrib/graphdb/client.py:78-376`); Oxigraph/RDF Delta: no auth layer (`oxigraph/server/README.md:123-150` nginx recipe) |
| AZ2 | P | A | A | A | Fluree: policy evaluated per flake inside the engine, so counts/aggregates only see permitted flakes (`docs/security/policy-model.md:233-236`); others: no policy engine (grep `policy` in oxigraph/lib, rdflib/plugins/stores: none) |
| AZ3 | A | A | A | A | no SPARQL-AST policy injection (Fluree filters flakes, not query text) |
| AZ4 | A | A | A | A | no PDP list/plan integration in any |
| AZ5 | P | A | A | A | Fluree: `f:action f:modify` + `f:queryState` pre/post state (`policy-model.md:27-33`); staged writes checked per operation (`fluree-db-api/src/transaction.rs:1-12`) |
| AZ6 | n.a. | n.a. | n.a. | n.a. | service-pipeline feature |
| AZ7 | A | A | A | A | — |
| AZ8 | P | A | p | A | Fluree `f:onProperty/onClass/onSubject` (`policy-model.md:27-35`); rdflib GraphDB client only administers GraphDB FGAC entries (`AccessControlEntry`, `contrib/graphdb/client.py:218-376`) |
| AZ9 | P | A | A | A | Fluree `?$this`/`?$identity` pre-bound in `f:query` (`policy-model.md:30`) |
| AZ10 | P | A | A | A | Fluree policies are JSON-LD nodes in the ledger, fail-closed (`policy-model.md:5-38,242-248`) |
| AZ11 | P | A | p | A | Fluree `f:required` gates + `default-allow` (`policy-model.md:233-248`); rdflib: GraphDB ACL order/policy set via client (`client.py:218`) |
| AZ12 | A | A | A | A | — |
| AZ13 | A | A | A | A | — |
| AZ14 | A | A | A | A | — |
| AZ15 | A | A | A | A | — |
| AZ16 | p | A | A | A | Fluree: privileged system read for config only (`docs/ledger-config/README.md:55-57`), no per-service sudo |
| AZ17 | P | A | A | A | Fluree Python `with_policy` handle (`_connection.py` `_require_unrestricted`, l.836-839) |
| AZ18 | P | A | A | A | Fluree identity from `fluree.identity` JWT claim, OIDC via `--jwks-issuer` (`docs/security/authentication.md:53-74`) |
| AZ19 | P | A | p | A | Fluree server: per-request bearer; rdflib httpx clients take auth per client instance, not per call (`contrib/rdf4j/client.py:1220-1255`) |
| AZ20 | A | A | A | A | — |
| AZ21 | n.a. | n.a. | n.a. | n.a. | object-mapper feature |
| AZ22 | n.a. | n.a. | n.a. | n.a. | client-cache feature |
| AZ23 | A | A | A | A | — |
| AZ24 | p | A | p | A | Fluree typed errors with `f:exMessage` on denial (`policy-model.md:36`, `docs/api/errors.md`); rdflib contrib raises typed exceptions with status (`contrib/rdf4j/exceptions.py`) |
| AZ25 | A | A | A | A | no masking/redaction (grep `mask|redact` in fluree docs/security: none) |
| AZ26 | P | A | A | A | Fluree explain shows policy filtering (`docs/security/policy-in-queries.md:259`) |
| AZ27 | p | A | A | A | Fluree tracking reports policy accounting with the commit (`TransactionOptions.tracking`, `transaction.rs:123`) |
| AZ28 | n.a. | n.a. | n.a. | n.a. | ReBAC sync |
| AZ29 | n.a. | n.a. | n.a. | n.a. | generation |
| G1-G11 | n.a. | n.a. | n.a. | n.a. | code generation is outside a store/client |
| G12 | P | A | A | A | Fluree GraphQL schema derived from SHACL in the ledger (Inferred/Shaped/Curated tiers, `docs/query/graphql.md:17-30`) |
| G13-G27 | n.a. | n.a. | n.a. | n.a. | code generation |
| T1 | P | P | P | n.a. | Fluree `;`-multi-op = one commit (`compatibility.md` SPARQL Update); pyoxigraph `update` atomic (`python/src/store.rs:317`); rdflib `SPARQLUpdateStore.commit` (`sparqlstore.py:728-736`) |
| T2 | P | p | p | p | Fluree conditional updates doc + `commit` CAS on head for read txns (`transaction.rs:418-431`, GitNexus: `commit` CALLS `rebase_stage`, `is_retryable_commit_conflict`, `commit_contention`); Oxigraph/rdflib: guard expressible in SPARQL, no rows-affected; RDF Delta: CAS on log head (`PatchLogBase.java:167`) |
| T3 | p | A | P | n.a. | Fluree: embedded only, `begin_transaction` called only from `fluree-db-python/src/transaction.rs:47` (grep in server/bolt/cli: none); rdflib `contrib.rdf4j.Transaction` (`client.py:755-944`); Oxigraph: no Python/HTTP tx (grep `transaction` in `python/src/store.rs`: docstrings only) |
| T4 | n.a. | n.a. | P | p | rdflib `AuditableStore` (`auditable.py:1-12`); RDF Delta deletes stored patch if index save fails (`PatchLogBase.java:174-182`) |
| T5 | P | p | p | n.a. | Fluree `txn.query` sees staged (`transaction.rs` `db()` l.374); Oxigraph Rust `Transaction` reader only (`store.rs:406`), not in Python; rdflib RDF4J txn `query` (`client.py:899`) but `SPARQLUpdateStore` flushes on read (`sparqlstore.py:675-696`) |
| T6 | P | A | A | A | Fluree `ledger.transact(fn)` + engine retries rebases up to 16 times (`transaction.rs:419` `MAX_RETRIES`) |
| T7 | p | A | p | A | Fluree `/.well-known/fluree.json` advertises capabilities (`endpoints.md:14-33`) + SPARQL Service Description; rdflib `Store.transaction_aware/context_aware/graph_aware` flags (`rdflib/store.py:147-150`) |
| T8 | p | A | A | A | Fluree `savepoint`/`rollback_to` in Rust API (`transaction.rs:276,291`, GitNexus Function nodes); Python uses them only internally for Cypher scripts (`fluree-db-python/src/transaction.rs:152-176`) |
| T9 | P | A | A | P | Fluree idempotent upsert (`docs/transactions/upsert.md:161`), `Idempotency-Key` on `/push` (`endpoints.md:405`); RDF Delta re-sent head patch returns current version (`PatchLogBase.java:160-164`) |
| T10 | n.a. | n.a. | n.a. | n.a. | object-cache feature |
| T11 | A | A | A | A | none splits updates (Fluree refuses over novelty limits instead; `TransactionOptions.index_config`) |
| E1 | A | A | A | n.a. | no outbox; Fluree's commit log is the record (see E3) |
| E2 | A | A | A | P | RDF Patch is RDF Delta's format; Fluree exports N-Quads/TriG, not patches |
| E3 | P | A | A | p | Fluree SSE `ns-record` + `/commits` (`endpoints.md:2996-3017`); RDF Delta clients pull on transaction start (`SyncPolicy` NONE/TXN_RW/TXN_W, `SyncPolicy.java:25-30`) |
| E4 | P | A | A | A | Fluree `changes()` and `/show` apply the caller's policy (`_connection.py:842-851`, `endpoints.md:484`) |
| E5 | P | A | A | P | Fluree monotonic `t` + commit ids; RDF Delta versions + `prev` chain |
| E6 | A | A | A | A | — |
| E7 | A | A | A | A | — |
| E8 | A | A | A | A | — |
| E9 | p | A | A | A | Fluree SSE only, nameservice-level, not Solid/Mercure |
| U1-U10 | n.a. | n.a. | n.a. | n.a. | UI/client features (Fluree TS client `fluree-client` near-dead, see catalogue) |
| RAD3 | n.a. | n.a. | n.a. | n.a. | — |
| RAD4 | P | n.a. | n.a. | n.a. | Fluree GraphQL mutations opt-in (`f:graphqlEnableMutations`, `endpoints.md:1778`) |
| X17 | p | A | A | A | Fluree: one ledger served as SPARQL, JSON-LD query, Cypher, GraphQL (`docs/query/README.md`); not a resource registry |
| X18 | p | p | p | n.a. | multi-operation atomic SPARQL Update in all three; no client-local ids |
| X19 | A | A | A | A | no `If-Match` on writes; Fluree ETag only on storage-proxy reads (`fluree-db-server/src/routes/storage_proxy.rs:357-522`) |
| X20 | p | A | A | A | Fluree cursor on `/commits` (`endpoints.md:615`), not on queries |
| X21 | p | p | p | P | SPARQL Update bodies on `/update` (Fluree, Oxigraph, rdflib clients); RDF Delta accepts RDF Patch bodies |
| X22 | n.a. | n.a. | n.a. | n.a. | client bundle |
| D11 | P | P | P | p | Fluree structured errors (`docs/api/errors.md`); Oxigraph server returns error text; rdflib contrib exceptions carry status + body (`client.py` commit error) |
| D12 | n.a. | n.a. | n.a. | n.a. | ORM |
| D13 | n.a. | n.a. | n.a. | n.a. | ORM |
| S15 | P | A | A | p | Fluree `at(t)`, `history()`; RDF Delta can replay to a version but not query it |
| S16 | P | A | A | A | Fluree branch/merge (`endpoints.md:2209-2656`) |
| S17 | P | p | p | A | Fluree `sync`, GSP PUT = diff (`endpoints.md:368-382`); Oxigraph/rdflib: GSP PUT replaces the graph (`oxigraph/server/README.md:73-85`, `GraphStoreManager.overwrite`, `client.py:305`) |
| S18 | P | P | p | n.a. | Fluree import/insert_rows; pyoxigraph `bulk_load` (`store.rs:502`); rdflib: GraphDB server import via contrib (`graphdb/client.py:1162-1248`) |
| S19 | P | A | A | p | Fluree `Commit(t,id,digest,…)` + `message=`; RDF Patch `H` headers carry id/prev only |

Reading the counts: Fluree covers most v3 L2/L3/L6 features *inside one product* (policies,
history, branches, change feed). Oxigraph is deliberately a bare standards engine: its value
lies in v0–v2 features (S1–S3, X1–X2), not in v3. rdflib supplies the client-side transaction
pieces (T1, T3, T4, T7 flags). RDF Delta contributes the event and idempotency pieces
(E2, E5, T9).

### Purpose and origin

**Deep-dived candidates**

| Candidate | Built for | Who / context | Design angle | Therefore fits |
|---|---|---|---|---|
| **Fluree DB v4** | A "graph database for data that matters": temporal, verifiable, git-like ledgers with policy enforcement; now also positioned for AI agents (Fluree Memory, document ingest; README l.1-15) | Fluree, PBC (licensor in `LICENSE`); v1–v3 in Clojure; v4 is a Rust rewrite released 2026-04-22; 15 contributors, one company | **Ledger-first and policy-as-data**: every write is a signed/verifiable commit; access rules are RDF in the ledger; many query surfaces (SPARQL, JSON-LD, Cypher, GraphQL, SQL graph sources) over one engine | L2 + L3 + L6 in one box. Natural home of **V3**; usable as a plain SPARQL store in V1/V5. Not a fit where the licence (BUSL "Database Service") or single-vendor lock-in is unacceptable |
| **Oxigraph / pyoxigraph / oxrdflib** | A small, fast, standards-strict SPARQL 1.1 database usable as a library in Rust, Python and JS, or as a server | Thomas Pellissier Tanon (`CITATION.cff`), open-source project with 30 contributors; oxrdflib bridges it to rdflib | **Store-first, spec-conformance-first**: W3C test suites, no auth, no history, no vendor extensions | L2 only. The default **embedded/test store in every variant**; a light production store in V1 (behind a proxy); a read replica in V5. Never the policy point (no L3) |
| **rdflib stores + contrib clients** | The Python RDF toolkit; `SPARQLStore`/`SPARQLUpdateStore` expose remote endpoints as rdflib graphs; `AuditableStore` gives undo; `contrib.rdf4j`/`contrib.graphdb` (2025-11 / 2026-02) give RDF4J/GraphDB protocol and admin clients | RDFLib community since 2002; the contrib clients were contributed by Edmond Chuc (`@edmondchuc`, PRs #3306, #3372, `CHANGELOG.md:17-39`) | **Library-first, store-agnostic**: graph API on top, pluggable `Store` underneath, with capability flags (`transaction_aware`, `context_aware`, `graph_aware`; `rdflib/store.py:147-150`) | L1/L2 foundation for **all variants**. T1 baseline (SPARQLUpdateStore), T3 adapter for **V4** (contrib.rdf4j/graphdb), T4 fallback for **V2** (AuditableStore) |
| **RDF Delta / RDF Patch** | Recording and publishing changes to RDF datasets: replication, incremental backup, high-availability Fuseki (README l.5-20) | Andy Seaborne (Apache Jena committer); RDF Patch now lives in Apache Jena (`jena-rdfpatch`); RDF Delta "going to be archived" | **Replication-log-first**: an ordered patch log with `prev` CAS; consumers pull | L6 format and ideas (E2, E5, T9) for V1/V5 outboxes; runtime only in Jena-based deployments. Does not fit as a Python dependency |

**Desk-scan-only candidates** (purpose and origin only)

| Candidate | Built for / origin | Fits |
|---|---|---|
| Apache Jena Fuseki + TDB2 | Reference SPARQL 1.1 server on a serializable, single-writer store; Apache Software Foundation, from HP Labs | V1 production store; V5 read endpoint; RDF Patch source |
| Eclipse RDF4J server | Java RDF framework (ex Sesame, Aduna) with a REST transaction protocol; Eclipse Foundation | V1 store; V4 transaction protocol (also spoken by GraphDB) |
| Ontotext GraphDB | Enterprise RDF database with cluster, RBAC and fine-grained access control; Ontotext (Sofia) | **V4**; V1 as a plain store |
| Virtuoso Open Source | Multi-model SQL/RDF server behind large Linked Data sites (DBpedia); OpenLink Software | **V2** (semantic.works default); weak atomicity elsewhere |
| Stardog | Commercial knowledge-graph platform (virtualisation, reasoning, explicit transactions); Stardog Union | V4-like only if a client already licenses it |
| QLever | Very fast SPARQL search engine over huge, mostly static data; University of Freiburg | V5 read model only |
| Blazegraph | Java graph DB (Systap); team moved to Amazon Neptune; archived 2023 | none |
| TerminusDB | Version-controlled document graph DB (WOQL/GraphQL); TerminusDB company | none (off-standard); S15/S16 ideas |
| AllegroGraph | Commercial RDF DB with sessions and security filters; Franz Inc. | none unless client-mandated |
| Amazon Neptune | Managed graph service with Neptune Streams; AWS | V1 store via SPARQL (no GSP); Streams as CDC |
| SPARQLWrapper | Thin SPARQL protocol client; RDFLib org | V1–V5 read path; stale releases |
| pystardog / agraph-python / terminusdb-client | Vendor SDKs | only with their store |
| aioflureedb | Async client for Fluree v1/v2 by one author | none (obsolete) |
| Solid Notifications | W3C Solid CG protocol for resource-change notifications | E9 transport idea for V1/V5 |
| GraphDB Kafka sink | Inbound RDF updates from Kafka into GraphDB; Ontotext | V4 ingestion only |

### R4.c Variant fit

S = supports (works as a part), E = enables (the variant depends on it or is much easier with
it), B = blocks or conflicts, – = neutral.

| Candidate | V1 Portable | V2 semantic.works | V3 Fluree | V4 GraphDB | V5 CQRS reads | A runtime mapper | B generated | C generic service |
|---|---|---|---|---|---|---|---|---|
| Fluree v4 | S (SPARQL HTTP) | – | **E** | – | S (policy-filtered SPARQL endpoint the UI may query) | S | S | **E** (GraphQL schema inferred from SHACL in the ledger, `docs/query/graphql.md:17-30`) |
| `fluree` PyPI | S (embedded adapter) | – | E (T3/T6 in-process) | – | – | S | S | – |
| Oxigraph / pyoxigraph | **E** (dev/test default) | – (Virtuoso-oriented) | S (tests) | S (tests) | S (replica) | E (fast test loop) | E | S |
| oxrdflib | S | – | – | – | – | S (rdflib API on Oxigraph) | S | – |
| rdflib `SPARQLUpdateStore` | **E** (T1) | S, but atomicity lost behind the proxy | S | S | – | E | E | S |
| rdflib `AuditableStore` | S (T4 fallback) | **E** (compensations behind a chunking proxy) | – | – | – | S | S | – |
| rdflib `contrib.rdf4j` / `contrib.graphdb` | S | – | – | **E** (T3, ACL admin) | – | S | S | – |
| RDF Patch (Jena) | S (outbox format, E2) | B-ish (V2 uses `changeSets`; translate) | – (Fluree has its own commits) | S | **E** (feeds replicas) | – | – | – |
| RDF Delta server | S (Jena only) | – | – | – | S (HA Fuseki replicas) | – | – | – |
| Fuseki/TDB2 | **E** (prod store) | S (instead of Virtuoso, untested with sparql-parser) | – | – | S | – | – | – |
| RDF4J server | S | – | – | S (same protocol) | S | – | – | – |
| GraphDB | S | – | – | **E** | S | – | – | – |
| Virtuoso | S (weak atomicity) | **E** | – | – | S | – | – | – |
| Stardog / AllegroGraph | S (client-mandated) | – | – | S (analogous) | S | – | – | – |
| QLever | – | – | – | – | **E** (read model) | – | – | – |
| TerminusDB | B (no SPARQL) | B | B | B | B | – | – | – |
| Blazegraph | B (dead) | B | B | B | B | – | – | – |

Headline: **V1 rests on Oxigraph (dev) + Fuseki/GraphDB (prod) + rdflib `SPARQLUpdateStore`
(T1) with our guarded updates (T2)**. **V3 is the only variant with transactions, history and
triple-level policy in one engine (Fluree)**. **V4 is cheap now that rdflib ships the RDF4J and
GraphDB clients**. **V2 forces compensations (AuditableStore pattern)**. **V5 wants QLever or an
Oxigraph/Fuseki replica fed by an RDF Patch outbox.** Store choice is almost orthogonal to the
approaches A–C. The one exception is Fluree, which makes C cheaper because its GraphQL schema
derives from SHACL.

### R4.d Corrections to the integrated docs

1. **`variants.adoc` V3 costs: "a policy cannot target a named graph"** — partly wrong. An
   `f:AccessPolicy` has no graph target (only `f:onProperty/onClass/onSubject`,
   `docs/security/policy-model.md:27-35`). But ledger config supports **per-graph policy
   defaults and policy sources** through `f:graphOverrides` / `f:targetGraph`, including
   `defaultAllow false` and `OverrideNone` for one sensitive graph
   (`docs/ledger-config/README.md:51,152-182`). Suggested wording: "policies target
   properties, classes and subjects; graph-level control is per-graph default and policy-set
   configuration, not a policy target".
2. **`catalogue.adoc` pyoxigraph / oxrdflib "Built for: … store with transactions"** — the
   Python API has no transaction object. Each `update`/`load`/`extend` call is atomic
   (`python/src/store.rs:116,317,382`); `start_transaction` exists only in Rust
   (`lib/oxigraph/src/store.rs:406`). Suggested: "with atomic updates (multi-operation
   transactions in the Rust API only)". Origin is better written as "Thomas Pellissier Tanon
   (`CITATION.cff`), community project".
3. **`index.adoc:31` and `building-blocks.adoc:61` "Oxigraph transactions do not detect write
   conflicts"** — true for the **RocksDB** store. The **in-memory** store serialises writers
   with a `transaction_lock` (`lib/oxigraph/src/storage/memory.rs:29,73-77`), so no lost update
   is possible there. Add "(on-disk store)".
4. **`angles/stores.adoc:164` proposed-feature list** still uses my round-3 numbering (E4
   "effective vs requested", E5 "subscription rules", E6, E7). These now map to X12, X12, E4,
   E5 (taxonomy appendix). The list should be renumbered to v3 ids to avoid two meanings of E4/E5.
5. **`angles/stores.adoc:164` (and my round-3 report) "T7 store capability descriptor (none
   found)"** — partial precedents exist: rdflib `Store` flags `transaction_aware`,
   `context_aware`, `graph_aware` (`rdflib/store.py:147-150`); Fluree discovery
   `/.well-known/fluree.json` (`docs/api/endpoints.md:14-33`) and SPARQL Service Description.
   None reports isolation or atomicity, so T7 as defined is still unbuilt.
6. **T8 savepoints "seen in Fluree"** (taxonomy v3, my round 3) — Rust API only; the Python
   package does not expose them (R4.0).
7. **Fluree retry** (`angles/stores.adoc:85-86`, catalogue "`fluree` (PyPI) … retry on
   conflict") — add that the engine itself retries re-base/re-stage of blind-write transactions
   up to 16 times under the ledger write lock (`transaction.rs:419-431`). `transact(fn)` is the
   *caller-level* retry for transactions that read.
8. **`catalogue.adoc` rdflib contrib clients origin "RDFLib community"** — more precisely
   contributed by Edmond Chuc (`@edmondchuc`, `CHANGELOG.md:17-39`). This is a minor refinement:
   a single main author is a bus-factor note for T3.

No contradiction was found for: Fuseki "one request = one serializable transaction", RDF4J
REST transactions, GraphDB/RDF4J protocol, RDF Patch in Jena, RDF Delta archiving, Fluree BUSL,
Fluree no cascade delete, or Fluree "over HTTP each request is one commit".

### R4.e Proposed new features (round 4, existing areas)

| Proposed id | Area | Feature | Seen in |
|---|---|---|---|
| T12 | Transactions | **Read-tracked optimistic commit**: blind-write transactions re-base automatically on a moved head; transactions that read fail with a conflict (refines T2/T6) | Fluree `transaction.rs:14-28,418-431` |
| AZ30 | Authorization | **Lagging policy config**: policy or config changes take effect from the next transaction, so a write cannot authorise itself | Fluree `docs/ledger-config/README.md:57-59` |
| S20 | Stores | **Per-named-graph store configuration** (policy defaults, SHACL, reasoning, override control per graph) | Fluree `f:graphOverrides` (`docs/ledger-config/README.md:51`) |
| S21 | Stores | **Store-side shape and uniqueness enforcement in the write transaction** (a write is refused on a SHACL or unique-property violation, including shapes sent with the request) | Fluree `opts.shapes`, `opts.uniqueProperties` (`docs/reference/compatibility.md:376`) |

---

## Round 5

Brief: `BRIEF-round5.md`. Pages reviewed: `angles/stores.adoc`, and the L2/L6 parts of
`index.adoc`, `building-blocks.adoc`, `variants.adoc` and `design-implications.adoc`. The
coordinator asked for special attention to the **single guarded operation** claim (B7) and the
**commit token + ASK** claim, which came from the DDD angle. I tested both against store code
(Oxigraph, Fluree) and the SPARQL 1.1 Update semantics. Per the brief, no store was run, so
these are code-reading results, not concurrency tests.

### R5.1 Do the guarded-operation and token+ASK claims hold on real stores?

**Claim 1: "a failed guard skips only its own operation, so all version guards must sit in one
`DELETE … INSERT … WHERE`".** *Correct as SPARQL semantics, and confirmed in code.*
- Oxigraph evaluates the operations of one request in sequence inside one storage transaction
  (`lib/oxigraph/src/sparql/update.rs:440-448`, `eval_all`).
- A `DELETE/INSERT … WHERE` turns each WHERE solution into mutations; zero solutions give zero
  mutations, even for ground templates (`update.rs:300-323`).
- Fluree documents the same rule, including "nothing is inserted, even for all-literal INSERT
  templates" (`docs/transactions/conditional-updates.md:22-29`).
- Two caveats the pages do not state:
  - (a) **Everything that must not happen on conflict has to be inside that same guarded
    operation.** This covers the outbox triples, the inserts of new owned children, and
    "insert-if-absent" for new roots (`FILTER NOT EXISTS` in the same WHERE). A separate
    `INSERT DATA` in the same request still runs when the guard fails. The page wording
    "one `DELETE … INSERT … WHERE {all version guards}` + outbox triples" leaves this open.
  - (b) **Atomic is not isolated.** The single operation is all-or-nothing, but whether the
    WHERE read and the write are serialised against concurrent requests depends on the store:

| Store | Guard read and write serialised? | Evidence | Consequence for B7 |
|---|---|---|---|
| Fuseki / TDB2 | Yes: the update runs in one write transaction; one writer at a time, serializable | [TDB transactions](https://jena.apache.org/documentation/tdb/tdb_transactions.html) (desk) | B7 safe |
| Oxigraph **in-memory** (pyoxigraph `Store()`) | Yes: `start_transaction` takes `transaction_lock` and holds it until commit (`storage/memory.rs:73-84`) | code | B7 safe |
| Oxigraph **on disk** (RocksDB; pyoxigraph `Store(path)`, Oxigraph server) | **No.** The WHERE runs on a snapshot (`start_readable_transaction`) or, for a first-position `DELETE/INSERT`, on the live storage (`update.rs:106-117, 420-438`); the commit is an unconditional `rocksdb_write_writebatch_wi` (`rocksdb_wrapper.rs:1047-1056`). The server serves requests concurrently with no update lock (grep `Mutex` in `cli/src/main.rs`: none around updates) | code | **Two concurrent commits on the same version can both pass the guard: lost update.** B7 needs a per-process write lock in our adapter (one process holds RocksDB read-write, so a mutex around `update()` closes it), or a single-writer deployment |
| Fluree v4, HTTP single update | Yes in effect: a stage that lost a race is re-based only if no subject it **read or wrote** changed, otherwise it is re-staged (WHERE re-evaluated) under the ledger write lock (`fluree-db-api/src/tx.rs:2606-2617, 2705-2718`; `tx_builder.rs:1945-2010, 2399`). Policy-gated requests hold the write lock across stage and commit (`tx_builder.rs:2324-2335`) | code | B7 safe; even read-only guards on other aggregates are protected |
| RDF4J / GraphDB | Depends on repository isolation level and engine | not verified (desk) | **Test before relying on B7**; or use T3 transactions with SERIALIZABLE where offered |
| Virtuoso (autocommit) | No atomicity guarantee for large updates | desk | B7 unsafe |
| behind semantic.works sparql-parser | The guard is evaluated once when the update is expanded; the quads are then written in batches, ordered only for overlapping quads (`semantic-works.md` §Graphs) | analysis report | Guard is checked, but the write is not atomic and the check-then-write race stays open |

**Claim 2: "Update returns no match count, so write a commit token in the same update and
confirm with an ASK".** *Workable, with four caveats the pages do not state.*
1. The token must be **append-only**: a fresh IRI per commit, e.g. the outbox record itself.
   If the token is a replaceable property such as `ex:lastTx`, the next commit can overwrite it
   before our ASK runs, and we report a false conflict.
2. The ASK must read **our own write**. It must go to the primary or write endpoint, not a
   replica (Fluree query peers, GraphDB cluster followers, RDF Delta replicas, Neptune
   readers). Fluree offers `min_t` gating for this (`docs/transactions/commit-receipts.md`
   "Read-after-write consistency").
3. Token+ASK **detects a failed guard; it cannot detect a race the store did not serialise**.
   On Oxigraph RocksDB, both racing commits find their tokens (see the table above).
4. **Store shortcuts make the ASK unnecessary:**
   - Fluree's commit receipt carries `t`, `flakes_added` and `flakes_retracted`, and a CAS
     no-op is detected "by checking whether `t` advanced"
     (`docs/transactions/commit-receipts.md`; `conditional-updates.md:112`).
   - Inside an RDF4J/GraphDB transaction (T3), the ASK can run before `COMMIT`, in the same
     transaction.

   The ASK also helps after a timeout: it tells whether an ambiguous request committed (T9).

Also, "Over plain SPARQL … flush and commit are the same step" (`design-implications.adoc`)
is true only for P-a. With T3 (RDF4J/GraphDB) and embedded Fluree, flush and commit are
separate steps, and read-your-writes (T5/B15) becomes possible.

### R5.a v4 cross-check (77 v4 features × 4 deep-dived candidates)

| Candidate | P | p | A | n.a. |
|---|---|---|---|---|
| Fluree v4 (+ `fluree` PyPI) | 13 | 5 | 5 | 54 |
| Oxigraph / pyoxigraph / oxrdflib | 3 | 3 | 11 | 60 |
| rdflib stores + contrib clients | 1 | 6 | 11 | 59 |
| RDF Delta / RDF Patch | 1 | 2 | 5 | 69 |

Range rows are n.a. for all four (boundary, mapper, migration-tool, generation, UI and DX
features belong to our layers, not to a store). Absences were confirmed by grep (`cascade`,
`opentelemetry`, `testcontainers`) over the clones.

| v4 Id | Fluree v4 | Oxigraph family | rdflib stores + clients | RDF Delta / Patch | Evidence |
|---|---|---|---|---|---|
| B1-B6 | n.a. | n.a. | n.a. | n.a. | model and mapper boundary features; stores have no aggregate notion |
| B7 | P | p | p | n.a. | Fluree: zero-row WHERE suppresses even ground INSERTs (`docs/transactions/conditional-updates.md:22-29`) and a lost race re-evaluates the WHERE; the rebase scope includes read subjects (`fluree-db-api/src/tx.rs:2606-2617,2705-2718`). Oxigraph: semantics right (`lib/oxigraph/src/sparql/update.rs:300-323`, ops in sequence l.440-448), but the guard read and the batch write are not serialised on RocksDB (§R5.1). rdflib: `SPARQLUpdateStore` can send it; the guarantee is the server's |
| B8 | p | n.a. | p | P | RDF Patch is a backend-neutral change set (A/D/TX/TC); Fluree `sync(dry_run=True)` counts a change before committing; rdflib `AuditableStore` keeps the reverse-op list as a value (`auditable.py`) |
| B9 | n.a. | n.a. | n.a. | n.a. | domain-event collection lives in our layer |
| B10 | P | P | P | n.a. | GSP `PUT`/`DELETE` per graph: Fluree (`docs/api/endpoints.md:368-382`), Oxigraph `/store` (`server/README.md:73-85`), rdflib `GraphStoreManager.overwrite/clear` (`contrib/rdf4j/client.py:305-336`) |
| B11-B12 | n.a. | n.a. | n.a. | n.a. | mapper features |
| B13 | A | A | A | n.a. | no general cascade: Fluree `docs/transactions/retractions.md:385`; nothing in oxigraph/rdflib (grep `cascade`: none) |
| B14 | n.a. | n.a. | n.a. | n.a. | — |
| B15 | P | A | p | n.a. | Fluree `txn.query` reads staged state (T5); rdflib `SPARQLUpdateStore` does the opposite: it autoflushes before reads unless `dirty_reads=True` (`sparqlstore.py:675-696`) |
| B16 | n.a. | n.a. | n.a. | n.a. | — |
| PG1-PG3 | n.a. | n.a. | n.a. | n.a. | — |
| PG4 | p | A | A | n.a. | Fluree: graph sources and ledgers as partitions (`conn.query` across ledgers via `FROM`); others named graphs only |
| EV1-EV7 | n.a. | n.a. | n.a. | n.a. | migration tooling is ours (stores give SPARQL Update only) |
| EV8 | p | p | p | n.a. | SPARQL Update `ADD`/`MOVE`/`COPY` supported by Fluree (`docs/reference/compatibility.md:155-160`) and Oxigraph (W3C Update suite); rdflib sends them; staging logic is ours |
| EV9 | P | p | A | p | Fluree branches (`docs/api/endpoints.md:2209`); pyoxigraph `backup()` (`python/src/store.rs:827`); RDF Delta replays a log to a version |
| AZ30 | P | n.a. | n.a. | n.a. | Fluree (angle-authz evidence; `fluree-db-policy/src/evaluate.rs:1417` tests a class cache keyed on graph and subject) |
| AZ31 | A | n.a. | n.a. | n.a. | no container inheritance (policies are flat nodes, `policy-model.md`) |
| AZ32 | P | n.a. | n.a. | n.a. | Fluree (angle-authz) |
| AZ33 | p | n.a. | n.a. | n.a. | Fluree: policy posture "cannot be varied to probe for the existence of any particular row" (`docs/security/policy-in-queries.md:316`); 404 vs 403 not verified |
| AZ34 | P | n.a. | n.a. | n.a. | Fluree lagging config (`docs/ledger-config/README.md:57-59`) |
| AZ35-AZ36 | n.a. | n.a. | n.a. | n.a. | — |
| G28-G36 | n.a. | n.a. | n.a. | n.a. | generation |
| T12 | P | A | A | n.a. | Fluree `transaction.rs:14-28,418-431` |
| T13 | P | P | p | n.a. | Fluree query peers are a read-only surface (`docs/operations/query-peers.md:20`); Oxigraph `serve-read-only` / `Store::open_read_only` (`cli/src/main.rs:77-95`); rdflib `ReadOnlyGraphAggregate` (`graph.py:3160`) is in-process only |
| T14 | n.a. | n.a. | n.a. | n.a. | mapper feature |
| S20 | P | A | A | n.a. | Fluree `f:graphOverrides` |
| S21 | A | A | A | A | — |
| S22 | P | A | A | n.a. | Fluree `opts.shapes`, `opts.uniqueProperties` (`docs/reference/compatibility.md:376`) |
| S23 | P | P | p | p | Fluree `/pack`, `/import`, drop, reindex (`endpoints.md:681-810`); pyoxigraph `backup/optimize/flush` (`store.rs:790-827`); rdflib GraphDB client monitoring and import (`contrib/graphdb/client.py:1162-1403`); RDF Delta incremental backup (README) |
| X23 | n.a. | n.a. | n.a. | n.a. | client feature |
| X24 | p | A | A | A | Fluree MCP server (`fluree-db-mcp`, `docs/ai/mcp-server.md`), a DB-level surface, not a resource registry |
| E10 | A | A | A | A | — |
| I7-I8 | n.a. | n.a. | n.a. | n.a. | mapper |
| P20 | n.a. | n.a. | n.a. | n.a. | mapper |
| U11-U13 | n.a. | n.a. | n.a. | n.a. | UI |
| D14-D19 | n.a. | n.a. | n.a. | n.a. | mapper/API DX |
| D20 | A | A | A | A | no testcontainers module for any (none upstream; Oxigraph and Fluree publish Docker images only) |
| D21-D28 | n.a. | n.a. | n.a. | n.a. | our DX/testing |
| D29 | P | A | A | A | Fluree OpenTelemetry with W3C `traceparent` (`docs/operations/distributed-tracing.md:14,172-174`); grep `opentelemetry` in oxigraph/rdflib: none |

### R5.b Page review: corrections

1. **`design-implications.adoc`, "What the evidence fixes" → Atomicity:** "All version guards
   sit in a single `DELETE … INSERT … WHERE` operation, because a failed guard skips only its
   own operation." The statement is correct, but add: "The outbox triples, new owned children
   and insert-if-absent checks must sit in the same guarded operation; a separate `INSERT DATA`
   runs even when the guard fails. A single operation is atomic but not necessarily isolated:
   on Oxigraph's on-disk store two concurrent guarded commits can both pass (the adapter must
   hold a write lock); RDF4J/GraphDB behaviour is untested." Evidence: R5.1.
2. **`design-implications.adoc`, Conflict detection:** "Write a commit token in the same update
   and confirm with an ASK." Add: "The token must be append-only (e.g. the outbox record IRI),
   the ASK must hit the primary, and it cannot catch races the store does not serialise. Stores
   with commit receipts (Fluree `t`, flake counts) or transactions (T3) need no ASK."
3. **`design-implications.adoc` sequence diagram:** "one DELETE … INSERT … WHERE {all version
   guards} + outbox triples" should read "… INSERT {changes + outbox triples} WHERE {all version
   guards}", so the outbox cannot be written on a failed guard.
4. **`design-implications.adoc`:** "Over plain SPARQL every request is its own transaction, so
   flush and commit are the same step and autoflush has no place." Add "with vendor
   transactions (T3) or embedded Fluree, flush and commit differ and staged reads are possible".
5. **`design-implications.adoc`, Store capability row:** add one capability: "**serialises a
   guarded update against concurrent writers**" (yes: TDB2, Oxigraph in-memory, Fluree; no:
   Oxigraph on disk, Virtuoso autocommit, sparql-parser; unknown: RDF4J/GraphDB). This is what
   decides whether B7 alone gives optimistic concurrency.
6. **`index.adoc:27-32` and `building-blocks.adoc:63-64`** ("optimistic concurrency (version
   triple checked in the update's WHERE clause)") — add "on stores that serialise the update;
   otherwise plus an adapter write lock (Oxigraph on disk) or vendor transactions".
7. **`angles/stores.adoc:16`:** "Fuseki/TDB2, Oxigraph, Fluree, RDF4J and GraphDB honour it"
   (one request = one atomic transaction). Add "atomic; isolation of the guard read differs —
   see R5.1".
8. **`angles/stores.adoc:111`:** "Concurrent in-process writers need guarded updates." Replace
   with "Concurrent writers on the on-disk store need a write lock in the adapter; a guarded
   update alone can lose an update (`update.rs:106-117`, `rocksdb_wrapper.rs:1047-1056`)."
   Same fix for variant E at l.238 ("P-a + process lock or P-b" → "P-a + process write lock
   (P-b alone is not enough on disk)").
9. **`angles/stores.adoc:188` (P-b):** "confirm with `ASK` or a per-flush token triple" — add
   the append-only and primary-endpoint conditions, and the Fluree receipt shortcut.
10. **`angles/stores.adoc:220-225`** "Round-4 proposals (no taxonomy id yet)" — these are now
    v4 **T12, AZ34, S20, S22**; replace the list with the ids.
11. **`variants.adoc` V3 strengths** "conflict-detecting transactions" — add "(embedded package
    only; over HTTP each request is one commit, made safe by Fluree's re-stage on a lost race)".

No error was found in: the Fluree licence, transaction, savepoint, events and per-graph-policy
statements (`angles/stores.adoc:83-93`, `variants.adoc:41-42` now correct), the rdflib client
statements, or the RDF Delta statements.

### R5.c Final verdicts and what to remember

| Candidate | Verdict |
|---|---|
| Fluree v4 (+ `fluree` PyPI, events) | **integrate** (optional backend behind the store port; legal check first) |
| Oxigraph / pyoxigraph / oxrdflib | **adopt** (embedded, test and light server store) |
| rdflib `SPARQLUpdateStore`, `AuditableStore`, `contrib.rdf4j` / `contrib.graphdb` | **adopt** (foundation, T1 baseline, T3 adapter, T4 fallback) |
| RDF Delta | **ideas**; RDF Patch **compatible** (delta wire format) |

Three things a system architect must remember:
1. **One request is atomic everywhere that matters, but it is not always isolated.** Optimistic
   concurrency through a guarded update is safe on Fuseki/TDB2, in-memory Oxigraph and Fluree.
   It is **not** safe on on-disk Oxigraph without an adapter write lock, and it is untested on
   RDF4J/GraphDB. The store port must declare "serialises guarded updates" and the unit of work
   must act on it.
2. **Everything conditional goes in one guarded operation**: changes, new children and outbox
   triples. A conflict is detected with an append-only token checked on the primary, or better
   from the store's own receipt or transaction (Fluree `t` and flake counts, RDF4J/GraphDB
   transactions).
3. **Fluree is the only store that gives transactions, history, change feed and triple-level
   policy in one engine**, but under BUSL-1.1 with a one-month-old Python package. Keep it
   behind the same SPARQL port as the others, so choosing it stays reversible.

### R5.e New features

None proposed. The capability flag in correction 5 ("serialises guarded updates against
concurrent writers") is a refinement of **T7**, not a new feature.
