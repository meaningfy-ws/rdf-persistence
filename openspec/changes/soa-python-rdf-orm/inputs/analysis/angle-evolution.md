# Angle: day-2 concerns — schema evolution, data migration, testing, operations

- Change: `soa-python-rdf-orm` · analyst round 3 (angle `evolution`) · 2026-11-03
- Deep dives (clone + `gitnexus analyze`, all new clones):
  | Clone | Commit | Licence | Files | GitNexus index |
  |---|---|---|---|---|
  | `mu-migrations-service` (mu-semtech) | 44cdbdf (2023-10-27; last push 2024-09-03) | MIT | 12 | 54 nodes, 89 edges, 4 flows |
  | `linkml-map` (linkml) | 09667a6 (2026-11-02) | Apache-2.0 (`LICENSE`; GitHub shows NOASSERTION) | 429 | 5 648 nodes, 10 095 edges, 272 flows |
  | `alembic` (sqlalchemy) — mainstream benchmark | 1bcba93 (2026-10-27) | MIT | 194 | 4 973 nodes, 12 479 edges, 244 flows |
  | `testcontainers-python` | 6146aa1 (2026-10-07, v4.15.0) | Apache-2.0 | 460 | 3 642 nodes, 7 289 edges, 293 flows |
- Existing clones used read-only (not re-indexed): `linkml` (d48b197), `rdflib` (114dd59, 8.0.0a0),
  `oxigraph` (5b0ef09, 0.6.0-dev), `fluree-db` (docs only).
- Docs read: Fuseki server protocol (https://jena.apache.org/documentation/fuseki2/fuseki-server-protocol.html),
  `rdflib/docs/upgrade7to8.md`, `oxigraph/CHANGELOG.md`, `fluree-db/docs/operations/*`,
  `mu-migrations-service/README.md`, `linkml-map/docs/`.
- Stats from `gh api` and PyPI / pypistats (last month), 2026-11-03.

## Summary

Day 2 is the weakest part of the RDF ecosystem. **Migrations**: the only RDF-native migration
runner found is semantic.works' `mu-migrations-service` (2★, stale, fails DEC-5) — a ~250-line
"run ordered `.sparql`/`.ttl` files once, record them as triples" loop. Nothing turns a LinkML
schema diff into SPARQL Update migrations: LinkML has no schema-diff command, and `linkml-map`
transforms *objects/tables* between schema versions but its advertised SPARQL CONSTRUCT
compilation is **claimed, not found in code**. The mainstream benchmark (Alembic) shows the shape
we should copy: a version record in the store, ordered revision scripts with up/down, and an
autogenerate that diffs model vs. store. **Testing**: the Python tooling is mature and passes
DEC-5 (testcontainers, pytest-bdd, schemathesis, pytest-cov, pySHACL), but **no testcontainers
module exists for any RDF store** — every RDF project hand-writes the fixtures (rdfproxy did).
**Operations**: OpenTelemetry has no SPARQL semantic conventions, so SPARQL calls appear only as
plain HTTP spans; backups are store-specific; two licences bite at operation time (Fluree BUSL-1.1,
Zitadel AGPL-3.0).

## Purpose and origin

| Tool | Built for / by | Design angle | Fit (layer, variants) |
|---|---|---|---|
| mu-migrations-service | semantic.works (Aad Versteden, redpencil.io) to seed and patch the shared triplestore of mu-project stacks | store-first, file-based, run-on-boot container | L2 ops; idea source for all variants; native to V2 only |
| linkml-map (ex linkml-transformer) | LinkML core team (Mungall et al., biomedical KGs) to map data between two LinkML schemas | schema-to-schema, object/tabular | L0/L1 offline data transformation; V1–V5 for small/complex migrations |
| Alembic | SQLAlchemy author (Mike Bayer) for relational schema migrations | model-diff + revision graph | pattern benchmark only (not RDF) |
| testcontainers-python | Testcontainers community (AtomicJar/Docker) — throwaway real dependencies in tests | test-infra, container-first | dev/CI for every variant |
| pytest-bdd / behave / Cypress cucumber | pytest community / behave community / badeball | BDD Gherkin execution | service E2E (pytest-bdd), UI E2E (Cypress) |
| schemathesis | Dmitry Dygalo et al. — property-based testing of OpenAPI/GraphQL | contract-first fuzzing | L4 contract tests (V1, V3, V4, V5) |
| pySHACL | RDFLib org — SHACL validation in Python | standards-first validator | post-migration and write-path gate, all variants |
| OpenTelemetry Python contrib | CNCF | vendor-neutral telemetry | ops for all variants |

## 1. Landscape (desk scan)

DEC-5 = >200★ AND commit in last 12 months (org/monorepo inheritance noted).

| Candidate | Stars / last push | Licence | Lang | Downloads/mo | DEC-5 | Topic | Layers |
|---|---|---|---|---|---|---|---|
| mu-semtech/mu-migrations-service | 2 / 2024-09-03 | MIT | Ruby | n/a (Docker) | **fail** (stars, staleness; org also fails) | migration runner | L2 |
| linkml/linkml-map | 50 / 2026-11-02 | Apache-2.0 | Python | 5.5 k | pass via `linkml` org (680★) | schema-to-schema data mapping | L0, L1 |
| linkml/linkml (core; schema metadata, deprecation slots) | 680 / 2026-11-02 | Apache-2.0 | Python | 477 k | pass | evolution metadata | L0 |
| linkml/linkml-dataops (object differ/patcher) | 6 / 2024-02-27 | none | Python | — | fail (stale; org would inherit, but dormant) | object diff → patch | L1 |
| INCATools/kgcl + kgcl-rdflib (KG Change Language: rename, obsolete, move) | 23 / 2026-02; 20 / 2024-11 | MIT | Python | — | fail (repo); org INCATools has ODK 389★ — inheritance arguable | change vocabulary | L0, L2 |
| iiwish/kgdiff (semantic RDF diff) | 26 / 2026-11-02 | MIT | — | — | fail | RDF diff/review | L0 |
| ontodev/robot (`robot diff`, OWL QC) | 329 / 2026-11-02 | BSD-3 | Java | — | pass | ontology diff in CI | L0 |
| INCATools/ontology-development-kit | 389 / 2026-11-02 | BSD-3 | Docker | — | pass | ontology release pipeline (versionIRI, release artefacts) | L0 |
| afs/rdf-delta (RDF Patch log, Fuseki HA) | 92 / 2026-09-01 | Apache-2.0 | Java | — | fail | change log / replication / point-in-time | L2, L6 |
| fluree/db (history, branches, `.flpack` archive) | 477 / 2026-11-02 | **BUSL-1.1** | Rust | 0 (PyPI new) | pass on numbers, licence not OSI | time travel, branch-rehearsed migrations | L2 |
| sqlalchemy/alembic | 4 464 / 2026-10-30 | MIT | Python | 179 M | pass | benchmark | — |
| django/django (migrations) | 91 489 / 2026-11-02 | BSD-3 | Python | — | pass | benchmark | — |
| testcontainers/testcontainers-python | 2 319 / 2026-10-09 | Apache-2.0 | Python | 31 M | pass | real-store tests | dev |
| RDFLib/rdflib (Memory store as fake) | 2 545 / 2026-11-02 | BSD-3 | Python | 13 M | pass | in-memory fake | L2 |
| oxigraph/oxigraph (`pyoxigraph` in-memory store) | 2 021 / 2026-11-02 | Apache-2.0 / MIT | Rust | 267 k | pass | in-memory fake with real SPARQL | L2 |
| w3c/rdf-tests (SPARQL 1.1/1.2 suites) | 74 / 2026-11-03 | W3C | — | — | n.a. (standard test data) | conformance | L2 |
| schemathesis/schemathesis | 3 737 / 2026-11-03 | MIT | Python | 3.2 M | pass | OpenAPI contract fuzzing | L4 |
| pytest-dev/pytest-bdd | 1 472 / 2026-11-02 | MIT | Python | 3.1 M | pass | Gherkin in pytest | dev |
| behave/behave | 3 539 / 2026-11-03 | BSD-2 | Python | 3.5 M | pass | Gherkin runner | dev |
| badeball/cypress-cucumber-preprocessor | 1 360 / 2026-10-31 | MIT | TS | — | pass | Gherkin on Cypress (UI E2E) | L5 |
| pytest-dev/pytest-cov | 2 074 / 2026-10-18 | MIT | Python | — | pass | ≥90 % coverage gate | dev |
| RDFLib/pySHACL | 367 / 2026-10-28 | Apache-2.0 | Python | 1.6 M | pass | post-migration validation | L1 |
| open-telemetry/opentelemetry-python(-contrib) (FastAPI, httpx, requests instrumentation) | 2 701 / 1 122, 2026-11-02 | Apache-2.0 | Python | 47–68 M | pass | tracing | ops |
| apache/jena (Fuseki admin: backup, compact, stats) | 1 494 / 2026-11-02 | Apache-2.0 | Java | — | pass | ops of the default prod store | L2 |
| openlink/virtuoso-opensource | 977 / 2026-10-26 | **GPL-2.0** only | C | — | pass | V2 store | L2 |
| zitadel/zitadel | 15 500 | **AGPL-3.0** | Go | — | pass | IdP (ops licence) | L3 |
| Ontotext-AD/graphdb-docker | 95 / 2026-10-29 | none (product proprietary) | HCL | — | n.a. (product) | V4 deployment | L2 |

## 2. Deep dives

### 2.1 mu-migrations-service (semantic.works)

**Architecture.** One Ruby file (`web.rb`, ~220 lines) on `mu-ruby-template`; GitNexus finds 4
flows, all rooted in `boot` (`web.rb:214-219`): `wait_for_database` → `execute_migrations`.

**Implementation principles (evidence).**
- *Discovery and order*: globs `/data/migrations/**/*.sparql` and `*.ttl` (`web.rb:139-140`),
  sorts by the **first integer in the filename** (`web.rb:27-32`, `143-146`). Subfolders allowed;
  identity is the filename only (README "Naming").
- *Version record in the store*: each run writes `<file://…> a muMigr:Migration;
  muMigr:filename; muMigr:executedAt` into the application graph (`web.rb:89-97`); "already
  run" is an `ASK`/paged `SELECT` on that graph (`web.rb:42-59`, `163-188`).
- *Execution*: `.sparql` → sent verbatim as one update (`web.rb:65-67`); `.ttl` → parsed,
  inserted in batches into a **temporary graph**, then `ADD <tmp> TO <target>` and `DROP SILENT`
  the temp graph (`web.rb:105-133`) — a cheap staging pattern that keeps the target graph free of
  half-loaded data. Batch size halves on error down to `MINIMUM_BATCH_SIZE` (`web.rb:117-123`).
  A sibling `.graph` file names the target graph (`web.rb:71-76`).
- *Authorization*: runs everything as **sudo** (`mu-auth-sudo` header, `web.rb:3,12`) —
  migrations bypass the PEP by design (README "Working with mu-authorization", experimental).
- *Scaffold*: `scripts/new/run.sh` creates a timestamped file (`YYYYMMDDHHMMSS-name.sparql`).

**Gaps (confirmed in code).** No checksum of applied files (an edited migration is silently
skipped); no down/rollback; the version record is written in a **separate request after** the
migration (`web.rb:89-97`), so a crash in between re-runs a non-idempotent `.sparql`; no lock
against two instances; no dry-run; no post-migration validation; zero tests (12 files, none a
test); last push 2024-09.

| C | Score | Justification / evidence |
|---|---|---|
| C1 | n.a. | not an ORM |
| C3 | 3 | trivial to use (drop file, restart); README tutorials + reference; no CLI beyond scaffold |
| C4 | 4 | one container, env-var config (`Dockerfile`) |
| C5 | 3 | uses ruby-rdf + mu helpers; not Python |
| C7 | 4 | plain SPARQL 1.1 Update + `ADD`/`DROP`; but `ASK`/paging assumptions on the store |
| C8 | 1 | no tests, stale, 2★, single author |
| C9 | 4 | the migration log is RDF in the store (queryable, portable) |
| C10 | 2 | tiny surface, but no checksums/locks/down make day-2 incidents manual |

**Verdict: borrow ideas** (DEC-5 fail). Borrow: file-per-migration with timestamp ids, the
migration log as triples in an admin graph, staging graph + `ADD` for Turtle loads, adaptive batch
size. Fix in ours: checksum, lock, record-in-same-request, dry-run, SHACL gate.

### 2.2 linkml-map

**Architecture.** CLI `linkml-map` (`pyproject.toml:49-50`) with commands `map-data`, `compile`,
`derive-schema`, `invert`, `validate-spec` (`src/linkml_map/cli/cli.py:72-694`). Core:
`ObjectTransformer.map_object` (`transformer/object_transformer.py:378`, 1 381 lines),
`Session.transform/reverse_transform/invert` (`session.py:125-150`). GitNexus processes
`Reverse_transform → Invert_slot_derivation` and `Invert → Invert_slot_derivation` confirm the
inversion path through `inference/inverter.py` (`TransformationSpecificationInverter`,
`NonInvertibleSpecificationError`).

**Implementation principles.** A declarative `TransformationSpecification`
(`datamodel/transformer_model.py:168`) of `ClassDerivation`/`SlotDerivation`/`EnumDerivation`
(`:296`, `:397`, `:477`) with `populated_from`, expressions, unit conversion, pivots. Compilers:
Python, SQL/DuckDB, Markdown, Graphviz (`compiler/*.py`). Inputs/outputs are dicts, YAML/JSON/
JSONL/TSV/CSV/Parquet/DuckDB (`writers/output_streams.py:34-43`) — **no RDF loader or writer**
(grep for `rdflib`/`sparql` in `src/` returns only the docstring below).

**Docs vs code.** The model's description promises "translation of the specification into SPARQL
CONSTRUCTs, to operate on triples" (`transformer_model.py:84`) — **claimed, not found in code**:
no SPARQL compiler in `compiler/`.

| C | Score | Justification / evidence |
|---|---|---|
| C3 | 3 | YAML spec + CLI; docs `quickstart.md`, `writing-specs.md`; pre-0.6 API churn (`tests/test_deprecations.py`) |
| C4 | 4 | pure Python, uv-friendly; DuckDB optional |
| C5 | 5 | built on linkml-runtime `SchemaView` |
| C6 | 5 | model-first: both ends are LinkML schemas |
| C7 | 1 | no RDF / SPARQL path (see above) |
| C8 | 3 | real test suite incl. compliance suite (`tests/test_compliance/`); 50★; 0.5.x |
| C9 | 3 | LinkML-native, but outside RDF |
| C10 | 3 | young (0.5.4), deprecations in flight |

**Verdict: integrate (offline, optional)** for complex migrations that reshape aggregates
(split/merge classes, unit conversion, enum remaps): read old aggregates through rdf-persistence
with the old generated model → `Session.transform` → write with the new model. The `invert`
command gives a **down-migration for free when the spec is invertible**. Not for bulk data (object
at a time); a SPARQL CONSTRUCT/UPDATE compiler for linkml-map is a plausible upstream
contribution (EV3).

### 2.3 Alembic (benchmark)

What the mainstream does, with evidence:
- **Version table in the target DB** — `alembic_version` (`runtime/migration.py:182-202`),
  `stamp` to mark a revision without running it (`:548-561`).
- **Revision graph with up/down** — `RevisionStep`/`StampStep` (`migration.py:994`, `:1220`),
  heads and branches (`HeadMaintainer`, `:701`); GitNexus flows `Run_migrations → Begin_commit`,
  `→ _has_version_table`.
- **Transaction per migration** optional (`transaction_per_migration`, `migration.py:140-141`).
- **Autogenerate** — `compare_metadata` / `produce_migrations` (`autogenerate/api.py:45`, `:171`)
  run per-object comparators registered as plugins (`compare/tables.py:82` `_compare_tables`,
  `:232` `_compare_columns`; `compare/constraints.py`, `comments.py`, `server_defaults.py`), then
  `render.py` writes a Python script for human review. Renames are **not** detected — they show
  as drop + add — so the developer edits the generated script.

Transfer to RDF: the "database schema" is mostly implicit in RDF, so the diff must be
**model-vs-model** (old LinkML vs new LinkML), not model-vs-store. LinkML already carries the
rename hint Alembic lacks: `deprecated_element_has_exact_replacement` (mapped to IAO:0100001
"term replaced by", `linkml_runtime/linkml_model/mappings.py:102-106`). **Verdict: borrow ideas**
(the version record, revision ids, up/down, stamp, autogenerate-then-review workflow, comparator
plugins).

### 2.4 testcontainers-python

**What exists.** 50+ modules (`src/testcontainers/*.py`) incl. `neo4j`, `arangodb`, `keycloak`,
`openfga`, `vault`, `toxiproxy` (community) — **no Fuseki, GraphDB, Oxigraph, Virtuoso, Fluree
or Zitadel module** (grep over `src/` and `docs/` for those names: no hits). Generic building
blocks are enough: `DockerContainer` + `HttpWaitStrategy`/`LogMessageWaitStrategy`
(`core/wait_strategies.py:56`, `:155`), and `DockerCompose` (`compose/compose.py:197`, `start`
`:318`, `get_service_host_and_port` `:569`, `wait_for` `:577`) to bring up a whole
semantic.works-style stack. rdfproxy already uses this pattern for Oxigraph and Fuseki
(`rdfproxy/tests/conftest.py:59-112`, see rdfproxy.md).

| C | Score | Evidence |
|---|---|---|
| C3 | 4 | context-manager fixtures; docs per module (`docs/modules/*.md`) |
| C4 | 4 | needs Docker; one pip install |
| C8 | 5 | 2 319★, release-please, 31 M dl/mo, v4.15.0 |
| C9 | 5 | any container image; OpenFGA + Keycloak modules cover V1 authz tests |
| C10 | 4 | stable 4.x API |

**Verdict: adopt** as the integration-test substrate; we ship our own thin fixtures for RDF stores
(D14). `toxiproxy` gives network-fault injection to test T1/T4 degradation honestly.

## 3. Topic findings

### 3.1 Schema evolution & data migration

**What exists (DEC-5 status).**
- *Runner*: mu-migrations-service (fail) — the only RDF-native one. aabs/Sparql.Migrator (1★,
  2020, .NET) — dead. Nothing in Python.
- *Model diff*: **none for LinkML** (no `diff` command among the ~50 CLI scripts,
  `linkml/packages/linkml/pyproject.toml:157-207`; web search found nothing). linkml-dataops has an
  object differ (fail). OWL-level: `robot diff` (pass) on the `gen-owl` output; KGCL (fail) offers a
  change vocabulary (rename, obsolete, move) and kgcl-rdflib applies it to RDF.
- *Data transformation between versions*: linkml-map (pass via org), object/tabular only.
- *Evolution metadata in LinkML*: `version`, `deprecated`, `deprecated_element_has_exact_replacement`,
  `deprecated_element_has_possible_replacement` (`mappings.py:102-106`). `gen-owl` does not emit
  `owl:versionIRI` (grep `versionIRI` in `linkml/src`: no hits) — the ODK/ROBOT pipeline is the
  usual place to stamp `owl:versionIRI`/`owl:priorVersion`.
- *Post-migration checks*: SHACL from `gen-shacl` + pySHACL (pass), or store-native SHACL
  (Fluree, GraphDB, Jena SHACL).
- *History and rehearsal*: Fluree `history()`, `at(t)`, **branches + merge** (angle-stores §3.1)
  — a migration can be applied to a branch, validated, then merged; RDF Delta (fail) gives a patch
  log for point-in-time replay on Fuseki.

**Can a LinkML diff generate SPARQL Update migrations?** Not today, but most changes are
mechanical because the mapping is declarative (`class_uri`, `slot_uri`, `range`, `multivalued`,
enums with `meaning`):

| LinkML change | Generated SPARQL Update (sketch) | Auto? |
|---|---|---|
| slot `slot_uri` changed (rename with `deprecated_element_has_exact_replacement`) | `DELETE {?s old: ?o} INSERT {?s new: ?o} WHERE {?s a C; old: ?o}` | yes |
| class `class_uri` changed | same on `rdf:type` | yes |
| enum permissible value `meaning` changed | `DELETE/INSERT` on the IRI object | yes |
| new required slot with `ifabsent` | `INSERT {?s p default} WHERE {?s a C FILTER NOT EXISTS {?s p ?x}}` | yes |
| slot removed | `DELETE WHERE {?s a C; p ?o}` — destructive, require explicit confirm | gated |
| multivalued → single-valued, range change, datatype change (`xsd:string`→`xsd:date`) | needs a cast/selection rule | scaffold + human edit |
| class split/merge, reshaped aggregate | linkml-map spec (object-level) | human-authored |
| `required` tightened, pattern added | no data change; SHACL report lists violators | check only |

Every generated script runs per named graph (or `GRAPH ?g`) and is validated afterwards with the
new schema's SHACL shapes.

**Patterns catalogue (evolution).**
| Pattern | Where seen |
|---|---|
| EP-1 Ordered, immutable migration files, timestamp id | mu-migrations (`scripts/new/run.sh`), Alembic, Django |
| EP-2 Migration log stored in the store as RDF | mu-migrations (`web.rb:89-97`) |
| EP-3 Staging graph + `ADD`/`MOVE` for atomic bulk load | mu-migrations (`web.rb:105-133`) |
| EP-4 Autogenerate from model diff, then human review | Alembic (`autogenerate/api.py:45,171`) |
| EP-5 Rename hint in the model | LinkML `deprecated_element_has_exact_replacement` |
| EP-6 Up/down; down derived by inversion | Alembic; linkml-map `invert` |
| EP-7 Validate after migrate (SHACL gate) | idea (pySHACL / store SHACL) |
| EP-8 Rehearse on a branch/snapshot, then merge/promote | Fluree branches; Fuseki backup + restore |
| EP-9 Privileged migration identity bypassing the PEP | mu-migrations sudo header |
| EP-10 Schema version stamped in data (`owl:versionIRI`, a `schema:version` triple per graph) | ODK/ROBOT; idea for data graphs |

**Gaps.** No Python RDF migration runner; no LinkML diff; no LinkML→SPARQL migration compiler;
no lock/checksum discipline anywhere in RDF; nobody versions *data graphs* against the schema
version.

### 3.2 Testing

**What exists.** All pass DEC-5: testcontainers-python, pyoxigraph and rdflib Memory (in-memory
fakes with real SPARQL), pytest-bdd and behave, schemathesis, pytest-cov, pySHACL, Cypress +
cypress-cucumber-preprocessor. W3C rdf-tests are run by the stores themselves (Fluree reports
700+ W3C tests in CI — angle-stores §3.1), so we do not need them in our CI; we need a **small
conformance suite of our own** for the SPARQL subset the mapper emits.

**Fit with MWBv2 (≥90 % coverage, Gherkin E2E, TDD).**
| Level | Tool | Store | Notes |
|---|---|---|---|
| Unit (domain, mapper, query builder) | pytest | pyoxigraph in-memory (real SPARQL) or a fake repository | fast; most coverage comes from here |
| Adapter contract (one suite × N stores) | pytest + testcontainers | Oxigraph, Fuseki, GraphDB Free, Fluree, Virtuoso | the rdfproxy matrix (D8); marks per store capability (T7) |
| Fault injection | testcontainers `toxiproxy` | any | proves T1/T4 behaviour on dropped connections |
| API contract | schemathesis on generated OpenAPI | Oxigraph container | property-based; catches 500s and schema drift |
| Service BDD | pytest-bdd (same runner, coverage counted) | container | Gherkin by QA, per bdd-gherkin skill |
| UI E2E | Cypress + cucumber preprocessor | compose stack | runbook's "Cypress + Gherkin" |
| Authz | testcontainers `openfga` / `keycloak`; Zitadel via generic container or a stub JWKS | — | DEC-8 policies tested, not reimplemented |
| Migration tests | apply migration to a fixture dataset, assert SHACL conforms + golden counts | Oxigraph | EV6 |

Recommendation: prefer **pytest-bdd over behave** (one runner, fixtures shared with unit tests,
pytest-cov counts it); keep behave out.

### 3.3 Operations

**Deployment footprint per variant.**
| Variant | Containers (min) | Store backup / restore | Observability hooks | Licence at operation time |
|---|---|---|---|---|
| V1 Oxigraph dev / Fuseki prod | service, Fuseki, Zitadel (+DB), OpenFGA (+DB) | Fuseki `POST /$/backup/{name}` (gzip N-Quads), `/$/compact`, `/$/stats` (Fuseki protocol doc); Oxigraph `Store.backup` (S11) | OTel FastAPI + httpx spans; Fuseki stats | Zitadel **AGPL-3.0** (fine unmodified; patches must be published) |
| V2 semantic.works | identifier, dispatcher, resources, sparql-parser, delta-notifier, migrations, Virtuoso | Virtuoso checkpoint/backup (not verified) | container logs only; sparql-parser logs | Virtuoso **GPL-2.0-only** (service use fine; embedding/distribution care) |
| V3 Fluree | service, Fluree (single binary or Raft cluster; S3/DynamoDB) | `.flpack` archive/restore, content-addressed (`docs/operations/pack-archive-restore.md`) + history | **native OTel; accepts W3C `traceparent`** (`docs/operations/distributed-tracing.md:14,170-177`) | **BUSL-1.1** — legal check before offering a product where customers define schemas |
| V4 GraphDB | service, GraphDB (JVM, licensed cluster) | GraphDB recovery/backup REST (not verified here) | JMX/monitoring (not verified) | commercial |
| V5 CQRS reads | V1 + read replica / policy-filtered endpoint | replica rebuilt from outbox | trace the outbox lag | as V1 |

**Observability.** OpenTelemetry semantic conventions contain **no SPARQL entry** (`gh search code
repo:open-telemetry/semantic-conventions sparql` → 0). Instrumenting httpx/requests gives an HTTP
span per SPARQL call but no query kind, graph or row count. Recommend a thin decorator on the
store port that adds `db.system=sparql`(proposed), `db.operation` (SELECT/CONSTRUCT/UPDATE),
query fingerprint (S14), named graph, result size, and propagates `traceparent` (Fluree joins the
trace natively).

**Performance pitfalls.** N+1 on relationship traversal (Q9 — batch with `VALUES`); unbounded
`CONSTRUCT` for aggregates (stream, S13; page by subject); `COUNT`/`len()` on remote datasets —
**rdflib 8 changes `len(dataset)` to count quads and may issue one remote request per graph**
(`rdflib/docs/upgrade7to8.md:14-32`); `OFFSET` paging degrades on large graphs; batch-size limits
on Virtuoso (T11, the mu-migrations halving loop exists for this).

**Upgrade paths.**
| Component | State (2026-11-03) | Day-2 impact |
|---|---|---|
| rdflib | 7.6.0 released; main is `8.0.0a0` | Python ≥3.11; `len(Dataset)` semantics change (upgrade7to8.md) |
| LinkML | 1.12.1; `linkml-runtime` folded into the `linkml` monorepo (old repo archived) | pin both from one release; generated code must be regenerated per upgrade (golden tests) |
| linkml-map | 0.5.4, deprecations in flight | keep optional |
| Oxigraph | 0.5.13; main 0.6.0-dev; 0.5 dropped RDF-star for RDF 1.2, auto-migrates the on-disk DB, serialization changed (`CHANGELOG.md:170-185`) | dev-only store in V1 → low risk; pin in tests |
| Fluree | v4 (Rust rewrite, 2026-04) → 4.2.5; v5 alpha already | fast churn + BUSL |
| Zitadel | AGPL-3.0 | upgrade via container; no code embedding |

## 4. How it plugs into MWBv2 and an ACL-agnostic rdf-persistence

```
LinkML vN-1 ─┐                ┌─> migrations/NNNN-<slug>.sparql (+ .down.sparql, reviewed)
LinkML vN  ──┴─ schema-diff ──┤
                              └─> SHACL(vN) gate ──> rdf-persistence migrate (runner)
                                                       │ uses the store port (SPARQL Update)
                                                       │ runs as a privileged service identity
                                                       ▼ log: <admin graph> muMigr-like triples
```
- The runner is an **entrypoint** (CLI `make migrate`) calling a service over the same store port
  as the app — so it works with any SPARQL 1.1 store and stays ACL-agnostic: it authenticates as a
  dedicated service principal that the PEP/proxy/store policy allows (EP-9); no bypass inside the
  library.
- Generated pieces (approach B) add: per-version SHACL, migration skeletons, golden fixtures.
  Approach A (runtime mapper) still needs the runner and the diff; approach C (generic service)
  needs the runner most, since nothing typed catches drift.

## 5. Recommendations per variant

| Variant | Evolution | Testing | Operations |
|---|---|---|---|
| V1 | Build EV1 runner + EV2 diff/compiler; SHACL gate with pySHACL; linkml-map for reshapes | testcontainers matrix Oxigraph+Fuseki; schemathesis; pytest-bdd; openfga module | Fuseki backup cron + OTel decorator; Zitadel unmodified |
| V2 | Reuse mu-migrations file format (`.sparql`/`.ttl`/`.graph`) so files run in both runners; our runner adds checksum/lock | `DockerCompose` fixture over mu-project | weakest observability; add OTel only in our service |
| V3 | Rehearse migrations on a **Fluree branch**, validate with native SHACL, merge; history gives audit/rollback | Fluree container in the matrix (SPARQL path) | `.flpack` backups; native OTel + traceparent; BUSL legal check |
| V4 | Same runner; run each migration inside an RDF4J transaction (T3) — real atomic up/down | GraphDB Free container in the matrix | vendor backup; licence |
| V5 | Migrations must also rebuild/replay the read side (outbox replay or replica re-sync) | consistency tests read-after-write lag | monitor replica lag |

## 6. Proposed new features

| Id | Area | Feature | Evidence / source |
|---|---|---|---|
| EV1 | Evolution | Migration runner: ordered immutable `.sparql`/`.ttl` files, log of applied migrations as RDF in an admin graph | mu-migrations (`web.rb:42-98,136-161`) |
| EV2 | Evolution | Migration integrity: checksum per applied file, run lock, log written in the same request as the change, dry-run | gap in mu-migrations; Alembic version table |
| EV3 | Evolution | Schema diff of two LinkML versions → generated SPARQL Update skeletons (renames via `deprecated_element_has_exact_replacement`, class/slot IRI changes, enum meaning, defaults) | idea (none found); LinkML `mappings.py:102-106`; Alembic autogenerate |
| EV4 | Evolution | Down migrations (explicit or derived by inverting a mapping spec) | Alembic; linkml-map `invert` (`session.py:140`) |
| EV5 | Evolution | Object-level data transformation between schema versions (split/merge/reshape aggregates) | linkml-map |
| EV6 | Evolution | Post-migration validation gate (SHACL of the new version must conform; golden counts) | idea; pySHACL |
| EV7 | Evolution | Schema version stamped in data/graphs and checked at startup (refuse to run on a stale store) | idea; Alembic `current`; owl:versionIRI practice |
| EV8 | Evolution | Staged bulk load: temp graph + `ADD`/`MOVE`, adaptive batch size | mu-migrations (`web.rb:105-133`) |
| EV9 | Evolution | Migration rehearsal on a branch/snapshot before promotion | Fluree branches (S16); backup+restore |
| D14 | DevEx | Shipped test fixtures for RDF stores (testcontainers wrappers for Oxigraph, Fuseki, GraphDB, Fluree) — refines D5/D8 | none upstream (testcontainers has no RDF module) |
| D15 | DevEx | Fault-injection tests for store failures (dropped connection mid-unit-of-work) | testcontainers `toxiproxy` |
| D16 | DevEx | API contract fuzzing from the generated OpenAPI | schemathesis |
| D17 | DevEx | Store-port observability: OTel spans with query kind, fingerprint, graph, row count; `traceparent` propagation — refines S14 | idea; Fluree accepts traceparent |
| D18 | DevEx | Ops admin port: backup/restore/compact/stats per store adapter — refines S11 to remote stores | Fuseki `/$/backup`, `/$/compact`, `/$/stats`; Fluree `.flpack` |

## 7. Open questions

1. Is migration authoring generated-then-reviewed (Alembic style) or hand-written only? It decides
   whether EV3 is in scope for the first EPIC.
2. Do data graphs carry the schema version (EV7), and per graph or per dataset?
3. Should our runner stay file-compatible with mu-migrations (V2 reuse) — `.graph` sidecar,
   filename-number ordering?
4. Which principal runs migrations under DEC-8 (service account in Zitadel with a dedicated
   policy)? Must be decided with the authz angle.
5. Is a SPARQL compiler for linkml-map worth contributing upstream rather than building EV3 alone?
6. Does DEC-5 apply to test-only dependencies? (All recommended ones pass anyway.)

## Not checked

GraphDB and Virtuoso backup/monitoring APIs (vendor docs not fetched); Fluree branch-merge
behaviour on conflicting migrations (docs only, code not read); linkml-map performance on large
datasets; no candidate code was run.

## Round 5

Candidates: **MM** mu-migrations-service (44cdbdf), **LM** linkml-map (09667a6), **AL** Alembic
(1bcba93), **TC** testcontainers-python (6146aa1). These are migration and test tools, not
mappers: most v4 features are out of their scope (n.a.), which I state once per group instead of
per row. Absences were confirmed with grep over each clone.

### (a) v4 cross-check

**Groups that are n.a. for all four** (no domain model, persistence, authorization, UI or event
layer in any candidate): B1–B7, B9–B16, PG2–PG4, AZ30–AZ34, AZ36, G28–G36, T12–T14, S20–S22,
X23, X24, E10, I7, I8, P20, U11–U13, D14, D16, D18, D22–D26. Count: 56 ids.

| Id | MM | LM | AL | TC | Evidence |
|---|---|---|---|---|---|
| B8 change-set as an inspectable value | absent | partial | partial | n.a. | LM: `TransformationSpecification` is a value compiled by several compilers (`datamodel/transformer_model.py:168`, `compiler/*.py`). AL: autogenerate returns a `MigrationScript` operation tree (`autogenerate/api.py:171`), rendered as SQL in offline mode (`as_sql`, `runtime/migration.py:138-161`). MM: files sent verbatim (`web.rb:65-67`) |
| PG1 query AST with pluggable renderers | absent | partial (analogue) | n.a. | n.a. | LM: one spec, compilers for Python / SQL / Markdown / Graphviz (`compiler/`); no SPARQL renderer (grep `sparql` in `src/`: docstring only, `transformer_model.py:84`) |
| AZ35 policy-filter equivalence test | n.a. | n.a. | n.a. | partial (enabler) | TC ships `openfga` and `keycloak` modules (`src/testcontainers/openfga.py`, `keycloak.py`) to run such tests; no test itself |
| S23 ops admin port (backup, restore, compact, stats) | absent | n.a. | n.a. | n.a. | MM has no backup or restore (grep `backup` in `web.rb`: no hits) |
| D15 parameter redaction in query logs | absent | n.a. | n.a. | n.a. | MM logs every migration query in full (`web.rb:208-211`) |
| D17 inspectable compiled change | partial | partial | present | n.a. | AL offline `--sql` (`migration.py:138-161`); LM `compile` command (`cli.py:555-560`); MM only logs the text (`web.rb:209`) |
| D19 test kit (pytest plugin, in-memory store, fakes) | absent | n.a. | n.a. | partial | TC gives container fixtures, no pytest plugin entry point (grep `pytest11` in `pyproject.toml`: no hits), nothing RDF |
| D20 shipped real-store RDF fixtures | absent | n.a. | n.a. | **absent** | 46 community module dirs, none for Fuseki / GraphDB / Oxigraph / Virtuoso / Fluree (grep over `src/`, `docs/`) |
| D21 tested documentation | absent | not checked | not checked | present | TC `doctests/` + `make doctests` (`Makefile:9,47`) |
| D27 fault-injection tests | absent | n.a. | n.a. | present | `ToxiproxyProxy.add_toxic` (`community/toxiproxy/__init__.py:31-44`) |
| D28 API contract fuzzing | n.a. | n.a. | n.a. | n.a. | schemathesis (desk scan only) |
| D29 store-port observability | absent | n.a. | n.a. | n.a. | MM: log lines only (`web.rb:209`); no OTel anywhere in the four clones (grep `opentelemetry`: no hits) |
| EV1 migration runner, log in the store | **present** | n.a. | present (relational) | n.a. | MM `web.rb:136-161`, log `web.rb:89-97`; AL `alembic_version` (`migration.py:182-202`) |
| EV2 integrity: checksum, lock, same-request log, dry run | absent | n.a. | partial | n.a. | MM: no checksum, no lock, log after the change (`web.rb:89-97`). AL: no checksum (grep `checksum`: no hits); relies on the DB transaction rather than a lock; dry run via offline SQL and `alembic check` (`command.py:320`) |
| EV3 schema diff → generated migration | absent | absent | present (relational) | n.a. | AL `compare_metadata` / `produce_migrations` (`api.py:45,171`). LM `derive-schema` derives a target schema from a spec (`cli.py:597`), the opposite direction; no diff |
| EV4 down migrations | absent | **present** (when invertible) | present | n.a. | LM `invert` (`session.py:140`, `inference/inverter.py`, `NonInvertibleSpecificationError`); AL `downgrade` (`command.py:490`) |
| EV5 object-level transformation between versions | absent | **present** | absent | n.a. | LM `ObjectTransformer.map_object` (`transformer/object_transformer.py:378`) |
| EV6 post-migration validation gate | absent | partial | partial (analogue) | n.a. | LM `validate-spec` checks the spec, not the data (`cli.py:657-694`); AL `check` catches model/DB drift, not data |
| EV7 schema version in data, checked at startup | partial | n.a. | present | n.a. | MM log exists but nothing refuses to start; AL `current` (`command.py:688`) + version table |
| EV8 staged bulk load, adaptive batch size | **present** | n.a. | n.a. | n.a. | `web.rb:105-133` |
| EV9 rehearsal on a branch or snapshot | absent | absent | absent | partial (enabler) | TC can start a throwaway store from a restored snapshot; no candidate does the rehearsal |

**Counts (77 v4 ids × 4 candidates = 308 cells):** present 11 · partial 12 · absent 20 ·
not checked 2 · n.a. 263. The four tools between them cover EV1, EV3, EV4, EV5, EV7
and EV8; **nobody covers EV2 in full, EV6, EV9, D20 or D29**. Those are ours to build.

### (b) Page review (`angles/evolution.adoc`, `building-blocks.adoc` §cross-cutting, `design-implications.adoc` §Day-2, `index.adoc`)

1. evolution.adoc:15 "a ~250-line loop" contradicts :79 "~220 lines". **Fix:** "~220-line loop"
   (`wc -l web.rb` = 219).
2. evolution.adoc:83 "The target never holds half-loaded data." **Overstatement.** True only if
   the store runs `ADD <tmp> TO <target>` atomically. **Fix:** "…provided the store executes
   `ADD` as one atomic operation."
3. evolution.adoc:120 "50+ modules". **Fix:** "46 community modules" (`ls -d community/*/`).
4. evolution.adoc:170 "The stores run the W3C suites themselves (Fluree reports 700+…)". **Over-
   generalised.** Checked for Oxigraph (`oxigraph/testsuite/`), rdflib (`test/data/suites/`) and
   Fluree (docs). **Not verified** for GraphDB, Virtuoso or Fuseki. **Fix:** "Oxigraph, rdflib
   and Fluree run the W3C suites in their own CI…"
5. evolution.adoc:192 Fuseki `/$/compact` has no caveat. **Fix:** add "(TDB2 datasets only)"
   (Fuseki server protocol page).
6. evolution.adoc:199 "(code search: 0 hits)". **Caveat missing:** this was a GitHub code search,
   whose index can miss files. **Fix:** "(GitHub code search over
   open-telemetry/semantic-conventions, 0 hits, 2026-11-03)".
7. evolution.adoc:218 "auto-migrates the on-disk store". **Fix:** "…migrates existing stores on
   first open so that *most* SPARQL queries keep working" (CHANGELOG wording). Whether a migrated
   store can be downgraded was not checked.
8. evolution.adoc:240-257 "Proposed features (no taxonomy id yet)" is now stale. **Fix:** give the
   v4 ids: EV1–EV9; D20 (fixtures), D27 (fault injection), D28 (fuzzing), D29 (observability),
   S23 (ops admin port).
9. evolution.adoc §Alembic (:107-116) misses two ideas that matter for EV2 and EV6. **Fix:** add
   "*offline mode* renders a migration as SQL without running it (`migration.py:138-161`), and
   `alembic check` fails CI when the model has changes no migration covers (`command.py:320`)."
10. design-implications.adoc:149 and index.adoc:60 "Nothing turns a LinkML schema change into
    SPARQL Update migrations". **Caveat missing:** KGCL with kgcl-rdflib applies
    ontology-term changes (rename, obsolete) to an RDF graph. It fails DEC-5 and works on the
    ontology, not on instance data; its code was not read. **Fix:** append "(KGCL edits ontology
    terms, not instance data; fails DEC-5)".
11. design-implications.adoc:151 lists the mu-migrations gaps as "no checksum, lock or down
    migrations". **Most dangerous gap missing:** the applied-migration record is written in a
    separate request *after* the change (`web.rb:89-97`), so a crash in between re-runs a
    migration that may not be idempotent. **Fix:** add "and records a migration only after it has
    run, in a separate request".
12. design-implications.adoc §Day-2 does not mention DEC-8. **Fix:** add "Migrations run as a
    dedicated service principal that the policy enforcement point allows. The library never
    bypasses it (mu-migrations uses a sudo header, AZ16)."

building-blocks.adoc:107-117 checked: no errors found.

### (c) Final verdict and three things to remember

**Verdict:** mu-migrations-service *ideas* · linkml-map *integrate* (optional, offline) · Alembic
*ideas* (benchmark) · testcontainers-python *adopt* (test-only).

1. **A migration is only safe when it is recorded in the same request as it runs.** Put the change
   and its log triple in one SPARQL Update request (and inside an RDF4J transaction on V4). Make
   the runner refuse edited files by checksum and refuse to run twice at once.
2. **The diff is model against model, and LinkML already holds the rename hint.** Generate
   SPARQL Update skeletons from vN-1 against vN (`deprecated_element_has_exact_replacement`, IRI
   changes, enum meanings). A human reviews every skeleton, the new version's SHACL is the gate,
   and linkml-map is used only to reshape aggregates.
3. **We own the RDF test and ops glue.** Nothing upstream gives store fixtures, SPARQL spans or
   one backup interface across stores. Keep them thin, behind the store port: about one fixture
   and one admin method per adapter.

### (d) Variant fit — deep-dived candidates

(Purpose and origin is above, in `## Purpose and origin`.)

| Candidate | V1 | V2 | V3 | V4 | V5 | A | B | C |
|---|---|---|---|---|---|---|---|---|
| mu-migrations-service | ideas (file format, log as RDF) | **supports** (already in mu-project stacks; runs with sudo) | ideas | ideas | ideas | ideas | ideas | ideas (C needs a runner most) |
| linkml-map | supports (offline reshaping) | supports | supports | supports | supports; the read side must be replayed afterwards | supports | **enables** (spec and inverse kept with the schema version) | supports |
| Alembic | pattern only | — | — | pattern (transactional up/down maps onto T3) | — | pattern | **pattern for EV3** (autogenerate, then human review) | pattern |
| testcontainers-python | **enables** (Oxigraph, Fuseki, OpenFGA, Keycloak) | enables (`DockerCompose` over mu-project) | enables (Fluree container, SPARQL path) | enables (GraphDB Free image; licence for CI to check) | enables (writer + replica in one compose) | supports | supports | supports |

Nothing here blocks a variant. The only operational licence concern belongs to the stores (BUSL,
GPL-2.0, commercial), not to these tools.

### (e) New feature (one, justified)

| Id | Area | Feature | Why it matters | Evidence |
|---|---|---|---|---|
| EV10 | Evolution | Pending-migration check in CI: the build fails when the LinkML schema changed and no migration (or explicit "no data change" stamp) covers the diff | It is the cheapest guard against the commonest day-2 failure: a schema release that silently strands existing data. It needs only the diff of EV3, not the compiler, so it can ship in the first EPIC even if EV3 does not. | Alembic `check` (`command.py:320`, since 1.9) |
