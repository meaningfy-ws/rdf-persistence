# Owlready2

- **Repo:** Bitbucket `jibalamy/owlready2`, clone `/home/lps/work/repos/owlready2`
- **Commit analysed:** `762bbd3` (2026-08-11, "Avoid bundling .pyc files…"). The clone is shallow (1 commit), so history comes from the `README.rst` changelog.
- **Version:** 0.52 (`pyproject.toml:7`)
- **Licence:** LGPL-3.0-or-later (`pyproject.toml:12`, `LICENSE.txt`)
- **Size:** about 19.9k Python LOC excluding `test/` and `doc/`. The largest files are `triplelite.py` (1,890), `sparql/main.py` (1,628), `namespace.py` (1,478), `sparql/parser.py` (1,431), `prop.py` (1,213) and a vendored `rply.py` (931). `pymedtermino2/` adds about 2.6k. `test/regtest.py` is 11,754 LOC with 637 `test_` methods. The repo also bundles the HermiT and Pellet jars, Java sources and a Cython extension (`owlready2_optimized.pyx`/`.c`); these are not counted.
- **GitNexus index (`owlready2`):** 157 files, 4,163 symbols, 10,494 edges, 241 clusters, 300 processes.
- **Docs read:** in-repo `doc/sparql.rst`, `doc/sync.rst`, `doc/world.rst`, `doc/observe.rst` and `README.rst`; web pages https://owlready2.readthedocs.io/en/latest/world.html and https://owlready2.readthedocs.io/en/latest/mixing_python_owl.html.

## Summary

Owlready2 is an **ontology-oriented programming** library. It turns OWL classes into real Python classes through a metaclass, properties into Python attributes, and individuals into Python instances. Everything lives in its own **SQLite quadstore** with integer-encoded IRIs (storids). It ships its own RDF/XML, OWL/XML and N-Triples parsers, its own **SPARQL→SQL translator**, and subprocess wrappers around the bundled **HermiT/Pellet** reasoners. It is fast and mature for embedded, ontology-heavy work, and it has zero runtime dependencies.

It does not fit rdf-persistence for three reasons:
- **Embedded only.** It has no client for a remote SPARQL endpoint and no pluggable store; `set_backend` accepts `"sqlite"` only.
- **It reimplements everything DEC-4 says not to:** the RDF model, the parsers, the store and the SPARQL engine.
- **Persistence is write-through Active Record.** It has no rollback API, and the session-level abstractions are thin.

## Architecture (GitNexus plus file reads)

GitNexus clusters are dominated by tests ("Test" clusters of 282, 161, 82 and more symbols), the HermiT Java tree (131), Pymedtermino2 (42) and Sparql (21) (cypher on `Community` ordered by `symbolCount`). The production code is organised as follows:

| Layer | Files | Role |
|---|---|---|
| Driver interface | `driver.py:58-80` (`BaseGraph.BASE_METHODS / ONTO_METHODS`), `BaseMainGraph`, `BaseSubGraph` | A list of method names, not a typed ABC. The backend's methods are copied onto `World`/`Ontology` with `setattr` at `set_backend` (`namespace.py:396-418`). |
| Quadstore | `triplelite.py` (`Graph`, `SubGraph`), `triplelite_update.py` | SQLite schema, indexes, storid allocation, transitive queries, FTS5 full-text search |
| Identity / namespaces | `namespace.py` (`Namespace`, `_GraphManager`, `World`, `Ontology`) | Entity cache, `_load_by_storid`, `get_ontology`/`load`/`save`, SPARQL entry points |
| Metamodel | `entity.py` (`EntityClass`, `ThingClass`), `individual.py` (`Thing`, `FusionClass`), `prop.py` (`PropertyClass`, `ObjectProperty`, `DataProperty`, …), `class_construct.py` (restrictions, And/Or/Not/OneOf), `disjoint.py`, `annotation.py` | OWL→Python mapping |
| Reasoning | `reasoning.py`, `rule.py` (SWRL), `close.py` (local closed world) | Exports N-Triples to a temp file, runs `java -cp HermiT/Pellet`, parses stdout and writes the inferences back |
| SPARQL | `sparql/parser.py` (rply LALR grammar), `sparql/main.py` (`Translator`, `SQLQuery`, `PreparedSelectQuery`/`PreparedModifyQuery`), `sparql/func.py`, `sparql/endpoint.py` | SPARQL→SQL compilation and a read-only Flask/WSGI endpoint |
| Interop | `rdflib_store.py` (`TripleLiteRDFlibStore`), `driver.py` (save to ntriples/nquads/rdfxml), `rdfxml_2_ntriples.py`, `owlxml_2_ntriples.py` | rdflib facade over the quadstore; custom parsers and serialisers |

GitNexus observation: the static call graph records almost no edges into `_abbreviate`, `_add_obj_triple_spo` or `_set_data_triple_spod` (cypher on `CALLS` edges returned 0 calls). The real data access is wired dynamically: `setattr(self, method, getattr(self.graph, method))` at `namespace.py:410-416`. The coupling to the store is therefore implicit and pervasive. `_load_by_storid` (`namespace.py:674-806`, GitNexus `context`) is the hub that turns a storid into a Python class, property or individual. `SQLQuery.parse_triples` (`sparql/main.py:843-1124`) is the core of the SPARQL compiler.

## Implementation principles

### Mapping (OWL → Python)

- `EntityClass.__new__` (`entity.py:110-166`) is a metaclass:
  - `class Pizza(Thing)` inside `with onto:` creates the Python class.
  - It allocates a storid for `namespace.base_iri + name` and registers the class in `world._entities`.
  - It writes `rdf:type owl:Class` and `rdfs:subClassOf` triples **immediately** (`entity.py:157-159`).
- Multiple OWL parents are linearised by a custom `mro` (`entity.py:100-108`). Individuals with several types get a synthetic `FusionClass` (`individual.py:422-470`).
- Properties are classes too (`class price(Thing >> float)`). They are indexed in `world._props` by **`python_name`**, one flat namespace per World.
- `Thing.__getattr__` (`individual.py:264-298`) resolves `attr` through `world._props`:
  - It returns a single value when the property is functional for the class, otherwise a `CallbackList`.
  - The result is cached in `__dict__`.
  - `INVERSE_<prop>` and `INDIRECT_<prop>` (inferred, transitive or inherited values) are magic prefixes.
- `Thing.__setattr__` (`individual.py:300-…`) writes triples at once: `_set_obj_triple_spo` / `_set_data_triple_spod`. It also invalidates the cached inverse on the other object.
- Lists are `CallbackList`s that write on every mutation.
- Class-level attributes map to OWL restrictions (`some`/`only`/`value`), controlled by `class_property_type` (`prop.py:34-106`).
- Python methods can be attached to OWL classes: the ontology annotation `python_module` auto-imports a module (readthedocs *mixing_python_owl*).

### Identity

- Each IRI becomes an integer **storid** in table `resources(storid INTEGER PRIMARY KEY, iri TEXT)`, allocated from `store.current_resource` (`triplelite.py:356-366`). The first 300 storids are reserved for built-ins.
- Blank nodes get negative ints from `store.current_blank` (`triplelite.py:424-428`).
- **Identity map:** `World._entities = weakref.WeakValueDictionary()` keyed by storid (`namespace.py:377`). There is one Python object per IRI per World, collected when unreferenced.
- IRI minting:
  - explicit name under the current namespace;
  - auto-numbered `classname1, classname2…` via `last_numbered_iri` (`triplelite.py:368-394`);
  - `NEWINSTANCEIRI()` or `UUID()` inside SPARQL.
- `World` is the database plus identity map. `Ontology` is a named graph (`c` column) and also a `Namespace`. `Namespace` is a base-IRI prefix used as a context manager.

### Storage schema

Defined at `triplelite.py:178-205`:
- `objs(c,s,p,o INTEGER)` and `datas(c,s,p,o BLOB,d)`, where `d` holds a datatype storid or `"@lang"`.
- Views `quads` and `quads2` (UNION ALL of the two tables).
- `ontologies(c, iri, last_update)`, `ontology_alias`, `resources` (WITHOUT ROWID), `prop_fts`, `last_numbered_iri`.
- Indexes on `(s,p)`, `(o)` and `(c)`.
- Optional FTS5 virtual tables with triggers per property (`triplelite.py:839-851`).
- Pragmas: 200 MB cache, 30 GB mmap, 32 KB pages, `locking_mode=EXCLUSIVE` by default (`triplelite.py:87-103`).

### Transactions and threading

- Writes start `BEGIN IMMEDIATE` via `acquire_write_lock`, which `with onto:` / `with world:` call (`namespace.py:69-82`, `triplelite.py:301-319`).
- Exiting the `with` block **does not commit**. `World.save()` with no file calls `graph.commit()` (`namespace.py:458-460`, `triplelite.py:412-415`).
- **There is no rollback API.** `rollback` appears nowhere in the non-test sources (grep). A user can call `world.graph.db.rollback()`, but cached Python objects (`__dict__` caches, `CallbackList`s) would then be stale. `destroy_entity(e, undoable=True)` (`prop.py:912`) is the only undo primitive.
- Threading:
  - one `sqlite3` connection with `check_same_thread=False`;
  - optional `enable_thread_parallelism` opens a pool of 3 extra **read** connections for parallel SPARQL (`triplelite.py:43-61`, `doc/sync.rst`);
  - custom locks (gevent RLock, multiprocessing RLock) can be passed in.
- Python objects in other processes are **not refreshed** after a write (`doc/sync.rst`). There is no optimistic concurrency.

### Querying

- **Native API:** `world.search(iri=…, is_a=…, <prop>=…)`, compiled to SQL with lazy lists (`triplelite.py:1391-1850`), plus FTS and BM25.
- **SPARQL:** `world.sparql(q, params)`:
  - `Translator.parse` (`sparql/main.py:30-100`) compiles SPARQL into **one SQL query over `objs`/`datas`/`quads`**, using recursive CTEs for property paths (`SQLRecursivePreliminaryQuery`, `sparql/main.py:1490-1604`);
  - the compiled query is `lru_cache`d (`namespace.py:482`);
  - results come back as Owlready objects or Python values;
  - INSERT/DELETE run the WHERE part in SQL and the mutations in Python so that loaded objects get updated (`doc/sparql.rst`; `PreparedModifyQuery.execute`, `sparql/main.py:525`).
- Coverage, from the grammar (`sparql/parser.py`) and the docs:

| Status | SPARQL features |
|---|---|
| Supported | SELECT, INSERT/DELETE…WHERE (plus WITH and USING), OPTIONAL, UNION, FILTER, (NOT) EXISTS, BIND, VALUES, sub-SELECT, GROUP BY/HAVING, aggregates, GRAPH, most property paths, `??` parameters |
| Not supported | ASK, CONSTRUCT, DESCRIBE, INSERT DATA / DELETE DATA / DELETE WHERE, LOAD/CLEAR/DROP/CREATE/ADD/MOVE/COPY, SERVICE, FROM/FROM NAMED, nested repeat paths |

  Most of the unsupported productions are commented out in the grammar (`parser.py:82-112, 181-189, 273-282, 489`).
- **MINUS** is tokenised and parsed into `MinusBlock` (`parser.py:475-477, 1270`), but `sparql/main.py` never handles `MinusBlock` and no test uses it. The docs say MINUS is unsupported, which matches the code.
- Non-standard extensions: `LIKE`, `FTS`, `STORID`, `LOADED`, `NEWINSTANCEIRI`, `DATETIME_ADD`, `PY_FUNC_*` registered Python functions, and `INDEXED BY`.

### Remote stores

There are **none**. `World.set_backend` raises for anything except `"sqlite"` (`namespace.py:396-405`). No SPARQLWrapper or HTTP SPARQL client exists; `urlopen` is used only to download ontology files (`namespace.py:994-1012, 1444`). `sparql/endpoint.py` **exposes** a World as a read-only GET endpoint (CSV/TSV/JSON/XML results). It cannot consume one.

### rdflib interop

`world.as_rdflib_graph()` returns `TripleLiteRDFlibGraph` over `TripleLiteRDFlibStore(rdflib.store.Store)` (`rdflib_store.py:27-240`), which is context-aware: each ontology is one rdflib context. It translates term by term with `_abbreviate`. Its `triples()` also yields virtual inverse-property triples. rdflib can then run full SPARQL 1.1 over the quadstore, but slowly; the docs call the native engine roughly 60× faster on GO (`doc/sparql.rst`). The reverse direction does not exist: Owlready2 cannot use an rdflib Store, pyoxigraph or a remote store as its backend. rdflib is only an optional test dependency (`pyproject.toml:34-35`).

### Reasoning

`sync_reasoner_hermit` / `sync_reasoner_pellet` (`reasoning.py:161-…, 269-…`) work as follows:
1. Serialise the whole world (or listed ontologies) to an N-Triples temp file.
2. Run `java -Xmx… -cp <bundled jars>` as a subprocess.
3. Parse the textual class hierarchy and the property values from stdout.
4. Write the inferred `is_a`/equivalence/property values into an `http://inferrences/` ontology or the current one, and update loaded Python objects (`_apply_reasoning_results`).

Java is required. Reasoning is batch and whole-world; there is no incremental reasoning. `rule.py` adds SWRL rules and `close.py` adds local closed-world closure.

### Serialisation

- Formats: RDF/XML, OWL/XML and N-Triples in; N-Triples, N-Quads and RDF/XML out (`driver.py:337-401`, `README.rst`).
- Missing: Turtle, TriG and JSON-LD (they are available only by going through `as_rdflib_graph().serialize`).
- Literal mapping is a registry, `_universal_datatype_2_abbrev` (`base.py:129-180`), covering int, float, bool, str, date, datetime, time and decimal.
- `locstr` (`util.py:53`) represents language-tagged strings.

## Patterns catalogue

| Pattern | Where |
|---|---|
| Active Record (domain object writes itself on attribute set) | `Thing.__setattr__` `individual.py:300`; `EntityClass.__new__` `entity.py:157-159` |
| Metaclass-based schema mapping (classes *are* the schema) | `EntityClass`, `ThingClass`, `PropertyClass` (`entity.py:63`, `prop.py:39`) |
| Identity Map (weak) | `World._entities` WeakValueDictionary `namespace.py:377` |
| Lazy loading + per-attribute cache | `Thing.__getattr__` caching in `__dict__` `individual.py:291-297`; `_LazyListMixin` search lists `triplelite.py:1437` |
| Observable collections | `CallbackList` (`util.py`) for `is_a`, multi-valued props |
| Context-manager "session" (write lock + current namespace) | `Namespace.__enter__/__exit__` `namespace.py:69-82`, `CURRENT_NAMESPACES` contextvar |
| Query Object / compiled & cached query | `PreparedSelectQuery`/`PreparedModifyQuery` + `lru_cache` `namespace.py:482` |
| Dictionary encoding of IRIs (storid) | `resources` table `triplelite.py:189`, `_abbreviate` `triplelite.py:356` |
| Adapter (expose store to rdflib) | `TripleLiteRDFlibStore` `rdflib_store.py:27` |
| Observer | `observe.py` (`start_observing`, `Observation`, `CoalescedObservations`) |
| Driver interface by method-name lists (implicit Strategy) | `driver.py:58-80`, `namespace.py:410-416` |
| *Absent:* Unit of Work, Repository, Data Mapper, explicit Session, optimistic locking | — |

## Docs vs code

| Claim | Status |
|---|---|
| "Native SPARQL engine translates SPARQL to SQL" (`doc/sparql.rst`) | **Confirmed**: `sparql/main.py` `Translator` → `SQLQuery.sql()`; `PreparedQuery.sql` attribute |
| Supported / unsupported SPARQL list (`doc/sparql.rst`) | **Confirmed** against grammar; MINUS parsed but not translated (consistent with "not supported") |
| "~60× faster than RDFlib on GO" | Claimed; not verified (benchmarks `test/bench_sparql.py` exist, not run) |
| "Beats Neo4J, MongoDB, SQLObject and SQLAlchemy as an ORM" (`README.rst:36`) | Benchmark scripts exist in `test/bench/dbtest_*.py`; results not in repo — **claimed, not reproducible from repo** |
| "Tested up to 1 billion RDF triples" (`README.rst`) | **Claimed, not found in code/tests** (no such test) |
| "Quadstore compatible with RDFlib" | **Confirmed** one-way (`rdflib_store.py`) |
| "Changes written only when `.save()` is called" (readthedocs *world*) | **Confirmed** `namespace.py:458-460` (commit); writes are, however, already in an open SQLite transaction |
| Thread parallelism with 3 connexions (`doc/sync.rst`) | **Confirmed** `_ConnexionPool(nb_connexion=3)` `triplelite.py:54-61` |
| HermiT/Pellet "included" | **Confirmed**: bundled jars, invoked by subprocess (`reasoning.py:182, 293`) — requires a Java runtime |

## Scores C1–C8

| # | Score | Justification | Evidence |
|---|---|---|---|
| C1 Feature coverage | 3 | Strong on CRUD, inverse/functional props, identity map, named graphs (per ontology), typed and lang literals, FTS. Weak on transactions (no rollback). No JSON-LD and no SHACL. | `individual.py:264-380`, `triplelite.py:178-205`, `util.py:53`, `doc/sparql.rst` |
| C2 Approach & patterns | 2 | Coherent but monolithic: metaclass-based Active Record with write-through, no Unit of Work, Repository or Session. Persistence is woven into domain objects; the driver abstraction is method-name lists. | `entity.py:110-166`, `driver.py:58-80`, `namespace.py:410-416` |
| C3 Developer friendliness | 4 | Very short happy path (`with onto: class X(Thing)`, `x.prop = …`) and a rich manual. Weaker on static types (dynamic attributes, no type hints, no IDE completion of properties) and on errors: warnings go to stderr. | readthedocs; `individual.py:264` |
| C4 Adoption | 3 | Zero runtime deps and a pip install. Java is needed for reasoning; the Cython build is optional. Embedded SQLite only, with no remote store. | `pyproject.toml:1-35`, `namespace.py:396-405` |
| C5 Reuse of foundations | 0 | Reimplements the RDF model, parsers (RDF/XML, OWL/XML, N-Triples), the quadstore, a SPARQL parser and engine, and even vendors its parser generator (`rply.py`). rdflib is an optional facade only. | `rdfxml_2_ntriples.py`, `owlxml_2_ntriples.py`, `sparql/`, `rply.py`, `triplelite.py` |
| C6 Data-centric & DDD fit | 2 | Strongly **model-first** (OWL ontology → Python classes, no codegen needed), but domain objects *are* persistence objects. Repository-per-aggregate and cosmic-python layering are not possible without wrapping, and no aggregate boundaries or cascades exist. | `entity.py:157`, `individual.py:300` |
| C7 SPARQL 1.1 portability | 1 | The engine is proprietary and covers a SPARQL subset over its own SQL schema. It cannot target external endpoints, has no Graph Store Protocol, and adds non-standard extensions. It can *serve* a read-only endpoint. | `sparql/parser.py:82-112`, `sparql/endpoint.py` |
| C8 Health | 3 | Large regression suite (637 tests) and long-lived production use with a changelog. There is a **single maintainer** (bus factor 1), no CI config in the repo, no coverage metrics, and the code style is dense with bare `except:`. Last commit 2026-08; clear LGPL-3 licence. | `test/regtest.py`, `git log`, `README.rst` |

## Feature inventory

| Id | Status | Evidence |
|---|---|---|
| M1 | present | `class Pizza(Thing)` in `with onto:`; `entity.py:110` |
| M2 | present (OWL only) | Loads OWL 2 (RDF/XML, OWL/XML, NT); `namespace.py:969` |
| M3 | absent (n.a.) | No codegen needed: classes are created at runtime from the ontology (`_load_by_storid` `namespace.py:674`) |
| M4 | present | `rdfs:subClassOf` ↔ Python bases, custom MRO, FusionClass `entity.py:100-160`, `individual.py:422` |
| M5 | partial | No validation on construct. Consistency comes only from the reasoner (`OwlReadyInconsistentOntologyError`); no SHACL. |
| I1 | present | Explicit name, auto-numbered `last_numbered_iri`, `NEWINSTANCEIRI()`/`UUID()` `triplelite.py:368` |
| I2 | present | Negative storids for bnodes; anonymous class constructs are objects `class_construct.py` |
| I3 | present | `World._entities` WeakValueDictionary `namespace.py:377` |
| R1 | partial | Sets via `CallbackList` (unordered); rdf:List only for OWL constructs, not as a user-level ordered property |
| R2 | present | Functional/non-functional, `inverse_property`, auto inverse maintenance `individual.py:305-320` |
| R3 | partial | Lazy per-attribute load and cache; no depth or eager control |
| R4 | partial | `destroy_entity` removes the entity and its references `prop.py:912`; no aggregate cascade config |
| L1 | present | Datatype registry `base.py:129-180`; `declare_datatype` |
| L2 | present | `locstr`, `d="@lang"` column `util.py:53` |
| P1 | present | Constructor, setattr, `destroy_entity` |
| P2 | present (fixed) | Per-attribute delete+insert, write-through `_set_*_triple_*` |
| P3 | absent | No UoW and no flush; writes go to SQLite immediately |
| P4 | partial | Local SQLite commit via `World.save()`; **no rollback API**; no remote transactions |
| P5 | absent | No versioning; other processes' writes are not reflected in loaded objects (`doc/sync.rst`) |
| P6 | present | One named graph per Ontology (column `c`); `GRAPH` in SPARQL |
| P7 | present | Fast bulk parse (separate parser process for files over 8 MB), N-Triples/N-Quads export `driver.py` |
| Q1 | present | `world["iri"]`, `onto.Name`, `world._get_by_storid` |
| Q2 | partial | `world.search(prop=value, is_a=…)` compiled to **SQL**, not SPARQL `triplelite.py:1391+` |
| Q3 | present | `world.sparql()` returns Owlready objects |
| Q4 | present | ORDER BY, LIMIT/OFFSET, aggregates in SPARQL |
| Q5 | present | Property paths through recursive CTEs (nested repeats not supported); `INDIRECT_` attrs |
| S1 | present (own) | In-memory SQLite (`:memory:`), not rdflib/pyoxigraph |
| S2 | absent | No SPARQL client; `set_backend` is SQLite-only `namespace.py:396` |
| S3 | absent | — |
| S4 | absent (de facto) | `driver.py` method lists, but only one backend; dynamic binding |
| X1 | absent | No JSON-LD (only via `as_rdflib_graph().serialize`) |
| X2 | partial | RDF/XML, OWL/XML, NT, NQ; no Turtle or TriG natively |
| X3 | partial | Read-only SPARQL GET endpoint `sparql/endpoint.py`; no REST/LDP |
| X4 | absent | — |
| X5 | present | `observe.py` listeners and coalesced observations |
| D1 | absent | Dynamic attributes, no type hints |
| D2 | absent | Sync only; gevent cooperative support via custom lock |
| D3 | partial | Flask/WSGI endpoint helper only |
| D4 | present | Extensive readthedocs manual, examples, paper |
| D5 | partial | `World()` on `:memory:` acts as a fake; no fixtures provided |
| O1 | present | Restrictions (`some/only/value/min/max/exactly`), equivalent_to, disjoints, property characteristics, defined classes `class_construct.py`, `disjoint.py` |
| O2 | present | HermiT and Pellet via Java subprocess `reasoning.py:161,269` |
| A1 | n.a. | — |

### Proposed new features

| Proposed id | Area | Feature | Owlready2 |
|---|---|---|---|
| O3 | Ontology | **Ontology-as-schema at runtime**: Python classes and properties materialised dynamically from a loaded OWL ontology (no codegen step) | present (`_load_by_storid`) |
| O4 | Ontology | **Inferred vs asserted views**: separate access to inferred values (`INDIRECT_*`, `ancestors()`), with inferences stored in a dedicated graph | present (`individual.py:264-285`, `_INFERRENCES_ONTOLOGY`) |
| O5 | Ontology | **OWL class-expression API**: restrictions and boolean class constructs as first-class Python objects (`prop.some(C)`, `A & B`) | present (`class_construct.py`) |
| O6 | Ontology | **Local closed-world closure** of individuals/classes | present (`close.py`) |
| O7 | Ontology | **Rule support (SWRL)** | present (`rule.py`) |
| O8 | Ontology | **Ontology import resolution / local ontology path** (`owl:imports`, `onto_path`, catalog) | present (`namespace.py:969+`) |
| O2a | Ontology (O2 refinement) | Reasoner **mode**: batch whole-store vs incremental; **in-process vs out-of-process**; write-back target graph | Owlready2 = batch, out-of-process (Java), write-back to inference graph |
| Q6 | Query | **Full-text search** over literal properties (FTS/BM25) | present (`triplelite.py:839`) |
| Q7 | Query | **Prepared / parameterised queries** with injection-safe parameters | present (`??` params, `prepare_sparql`) |
| Q8 | Query | **User-defined SPARQL functions** registered from Python | present (`register_sparql_function` `namespace.py:490`) |
| M6 | Modelling | **Behaviour attached to schema classes** (Python methods bound to ontology classes via an annotated module) | present (`python_module` annotation) |
| P8 | Persistence | **Concurrency mode** (exclusive / shared readers / thread-parallel reads) | present (`triplelite.py:65-170`) |

## JS-friendliness

Minimal. The read-only SPARQL endpoint returns SPARQL JSON/XML/CSV results (`sparql/endpoint.py`), which a JS SPARQL client can consume. There is no JSON-LD, no OpenAPI or JSON Schema, no TS types and no REST resource layer.

## Reuse verdict for rdf-persistence: **borrow ideas (do not build on it)**

Building an "ontology-driven path" *on* Owlready2 would conflict with DEC-4 and with the portability goal:
- its store, parsers and SPARQL engine are proprietary;
- it cannot sit on rdflib, pyoxigraph or a remote SPARQL 1.1 endpoint;
- write-through Active Record domain objects block cosmic-python layering and Unit of Work.

The rdflib adapter goes the wrong direction for us: it exposes Owlready to rdflib, not rdflib to Owlready. A thin "import from Owlready" bridge is possible as an *optional* interop: `world.as_rdflib_graph()` → copy into our store. The LGPL-3 licence allows dynamic use. This bridge is a nice-to-have, not a foundation.

Ideas to borrow:
1. **Runtime class materialisation from an ontology (O3)** as an alternative to LinkML codegen. Our version would produce pydantic models (or LinkML from OWL) rather than metaclass Active Record.
2. **Asserted vs inferred separation (O4)**: inferences go to a dedicated named graph, and the API distinguishes direct from indirect values. This maps cleanly to SPARQL (`GRAPH <inferred>`, property paths).
3. **Reasoner as an out-of-process port (O2a)**: snapshot → reasoner → write back to an inference graph. In cosmic-python this is an adapter behind a `Reasoner` port; candidates are owlrl in-process, or HermiT/ELK via subprocess or a service.
4. **Weak identity map keyed by IRI** per session (`WeakValueDictionary`).
5. **Functional vs non-functional properties decide scalar vs collection**, with automatic inverse maintenance.
6. **Prepared parameterised SPARQL** with LRU caching and Python-registered functions, though implemented over SPARQL 1.1 bindings and not SQL.
7. **Change observation (`observe.py`)** as a model for X5 domain events.

Ideas to avoid: write-through on attribute set, a global flat property namespace (`python_name` collisions across ontologies), no rollback, magic attribute prefixes (`INVERSE_`, `INDIRECT_`), and method-name-list driver binding.

## Risks / anti-patterns observed

- **No rollback, and cache drift**: after a failed operation the SQLite transaction and the cached Python state can diverge. There is no public `rollback()`.
- **Global mutable state**: `default_world`, the `LOADING` flag, the `CURRENT_NAMESPACES` contextvar, and module-level `_cache` / `_FUNCTIONAL_FOR_CACHE`.
- **Property name collisions**: `world._props` keyed by `python_name` is flat across all ontologies in a World.
- **Dynamic method injection** (`setattr` of backend methods onto World/Ontology) defeats static analysis: GitNexus sees almost no call edges into the store API. IDE completion suffers for the same reason.
- **Bare `except:`** in several places (e.g. `triplelite.py:100-101`, `entity.py:176`), and diagnostics go to stderr `print`.
- **Java runtime dependency** for reasoning; the whole world is serialised on every reasoning call.
- **Bus factor 1** (single author); no CI configuration in the repo.
- **SPARQL dialect lock-in**: extensions such as `INDEXED BY`, `LIKE`, `FTS`, and GROUP BY in INSERT make queries non-portable.

---
**Not checked:** I did not run code, tests or benchmarks (by brief). I did not verify the performance claims, the Cython parser internals, the `pymedtermino2` content or the readthedocs pages beyond *world* and *mixing_python_owl*. Activity history is limited by the shallow clone.

## Round 2 cross-check (taxonomy v1)

Checked against `docs/modules/ROOT/pages/architecture/soa/feature-taxonomy.adoc`, section "v1 features (merged from round 1)". Every "absent" was confirmed by grep over the non-test `*.py` files, plus GitNexus where noted.

**Counts over the 63 v1 features:**

| Status | Count |
|---|---|
| present | 16 |
| partial | 15 |
| absent | 29 |
| n.a. | 3 |

| Id | Status | Evidence |
|---|---|---|
| M6 | present | `World._load_by_storid` builds Python classes and properties at runtime from the quadstore (`namespace.py:674-806`; GitNexus hub for `_get_by_storid`) |
| M7 | partial | The predicate IRI is the namespace base IRI plus the property *class* name (`entity.py:110-111`), with a per-property `python_name` alias (`prop.py:70-102`). Derivation is per property class, not per field. |
| M8 | absent | No JSON-LD anywhere (grep `json-ld\|jsonld\|@context` returns no hits) |
| M9 | partial | One property gives per-language views (`x.label.fr`, `x.label.fr_any`) through `CallbackListWithLanguage.__getattr__` → `LanguageSublist` (`util.py:137-150`). These are views, not separately declared attributes. |
| M10 | present | Methods are defined in OWL class bodies, and the `python_module` annotation auto-imports a module (readthedocs *mixing_python_owl*) |
| M11 | absent | Loading is lenient. It only prints stderr warnings on type conflicts (`namespace.py:764,777,787`). `error_on_undefined_entities` applies to SPARQL text only (`namespace.py:479`), and there is no unmapped-data check. |
| M12 | absent | `rdf:type` is the only discriminator (`individual.py:132-134`); grep finds no discriminator or classification option |
| M13 | absent | No SHACL or constraint emission (grep `shacl` returns no hits). OWL restrictions are stored, not emitted as shapes. |
| M14 | partial | Classes come from any loaded OWL/RDF (M6). Nothing infers a model from untyped instance data. |
| M15 | absent | Grep `domain.json` returns no hits |
| I4 | absent | Blank nodes are negative storids (`triplelite.py:424-428`) and are exported as `_:N`. Grep `skolem\|genid` returns no hits (only a commented line, `reasoning.py:359`). |
| R5 | partial | `Prop.min/max/exactly` build OWL cardinality restrictions (`prop.py:310-312`, `class_construct.py:173-175`). They are checked only by the reasoner, never on assignment. |
| R6 | absent | No xone or exclusive-relation construct. `disjoint.py` covers class and property disjointness, not exclusive choice per individual. |
| R7 | present | Annotations on relations via `owl:Axiom` reification: `AnnotatedRelation` (`annotation.py:25-55`) |
| R8 | present | `x.INVERSE_prop` is computed without a declared inverse (`individual.py:282-290`) |
| L3 | present | `declare_datatype(datatype, iri, parser, unparser)` and `define_datatype_in_ontology` (`base.py:217,235`) |
| P8 | present | Setting an attribute deletes and inserts only that predicate (`individual.py:300-340`, `_set_obj_triple_spo` / `_set_data_triple_spod`); other triples are untouched |
| P9 | absent | Writes go straight through on `__setattr__`, so there is no dirty tracking or diff (`individual.py:300`) |
| P10 | partial | `CallbackList.append/remove` on multi-valued properties emit per-value inserts and deletes (`util.py` `CallbackList`, `prop.py:374`). There are no explicit $set/$add/$remove operators. |
| P11 | partial | `destroy_entity` removes the blank-node constructs the entity owns (`namespace.py:1253`, `prop.py:912+`). There is no general composition model. |
| P12 | absent | The graph is chosen by the caller (`with onto:` or `WITH <iri>`); no rule-based placement exists |
| P13 | partial | Options are set per store, not per transaction: `exclusive`, `read_only`, `journal_mode`, custom `lock` (`triplelite.py:65-170`). No timeouts, bookmarks or read/write transaction types. |
| P14 | partial | Get-or-create by IRI: constructing `Class("name")` for an existing IRI returns and retypes that object (`individual.py:74-107`). No upsert keyed on other properties. |
| P15 | present | Exclusive mode, shared readers, and a 3-connection read pool for parallel SPARQL (`triplelite.py:43-61,87-90,147-150`; `doc/sync.rst`) |
| Q6 | present | `??` / `??N` parameters and `prepare_sparql` with an LRU cache (`namespace.py:479-488`, `doc/sparql.rst`) |
| Q7 | absent | SPARQL comes in as text and goes through the rply grammar (`sparql/parser.py`); there is no public AST builder (grep `Builder` returns no hits) |
| Q8 | absent | Grep `find_by` returns no hits. The closest thing is the kwargs-based `world.search(prop=value)` (`namespace.py:288`). |
| Q9 | absent | Each attribute loads lazily on its own (`individual.py:291-297`). No prefetch or eager include (grep `eager\|preload` returns no hits). |
| Q10 | absent | SPARQL returns flat rows (`PreparedSelectQuery.execute`, `sparql/main.py:313`) |
| Q11 | partial | The endpoint refuses non-SELECT queries in read-only mode (`sparql/endpoint.py:50-51`), and undefined entities raise an error. Result integrity is not checked. |
| Q12 | present | FTS5 tables and triggers per property, plus `FTS()` in SPARQL and BM25 in `search` (`triplelite.py:839-851`, `namespace.py:288`) |
| Q13 | present | `register_sparql_function`, exposed as `PY_FUNC_*` (`namespace.py:490-498`) |
| Q14 | absent | No CQL2 or JSON:API filter support (grep returns no hits) |
| Q15 | absent | No totals or facets API; only `COUNT` in user SPARQL |
| Q16 | absent | Negation and OPTIONAL follow fixed SQL semantics; there is no configuration option |
| Q17 | present | `search(is_a=C)` and `type=` use a transitive `rdfs:subClassOf` recursive CTE (`triplelite.py:1508-1540`); `C.instances()` |
| Q18 | absent | No DESCRIBE (commented out, `sparql/parser.py:110,185`) and no CBD helper (grep `cbd` returns no hits) |
| S5 | absent | Embedded SQLite only (`namespace.py:396-405`) |
| S6 | absent | Not applicable to a remote store. Only the in-process entity cache exists (`namespace.py:338-345`, `World._entities`), with no invalidation across processes (`doc/sync.rst`). |
| S7 | n.a. | No network I/O to a store (grep `retry\|backoff` returns no hits) |
| S8 | partial | It *implements* an `rdflib.store.Store` (`rdflib_store.py:27`) so rdflib can read it. It cannot *consume* one as its backend. |
| X6 | absent | — |
| X7 | partial | The SPARQL endpoint picks the result format from the `Accept` header (`sparql/endpoint.py:20-32,43-47`). No profile negotiation, and no RDF serialisations from the endpoint. |
| X8 | absent | No Hydra support (grep returns no hits) |
| X9 | absent | Only the `python_name` alias exists (`prop.py:70`); there is no API↔storage vocabulary layer |
| X10 | absent | — |
| X11 | partial | `set_render_func` renders entities by label (`__init__.py:138-142`). This affects `repr` only, not API payloads. |
| X12 | partial | `observe.py` provides `Observation` and `CoalescedObservations` per entity and property (`observe.py:88-258`). There is no serialisable insert/delete change-set format and no subscription rules. |
| X13 | absent | — |
| X14 | partial | `ntriples_diff.py` is a CLI that diffs two N-Triples files, handling blank nodes and symmetric relations. It is not a library API over models. |
| D6 | partial | An entity can define `__destroy__(undoer_objs, undoer_datas)`, which `destroy_entity` calls (`prop.py:916`). There are no save or create hooks; observers (`observe.py`) can stand in for post-change hooks. |
| D7 | absent | Sync only; gevent works through `spawn` and a lock (`doc/sync.rst`) |
| D8 | absent | Single store; tests are in `test/regtest.py` |
| D9 | absent | — |
| RAD1 | absent | — |
| RAD2 | n.a. | Out of library scope |
| O3 | present | `class_construct.py` (Restriction, And, Or, Not, OneOf, Inverse); `prop.some/only/value` (`prop.py:300-312`) |
| O4 | present | `INDIRECT_*` attributes (`individual.py:265-280`), and reasoner output written to `http://inferrences/` (`reasoning.py:75,170-171`) |
| O5 | present | `close_world()` (`close.py:28`) |
| O6 | present | SWRL `Imp` (`rule.py`) |
| O7 | present | `owl:imports` resolution, `onto_path` and catalog (`namespace.py:969-1020`) |
| A2 | n.a. | No external store or auth proxy |
| A3 | absent | No read-only or write-only fields (grep `readonly` in `individual.py`/`prop.py` returns no hits) |

**Re-marked v0 features (meaning refined):**

| Id | Status | Evidence |
|---|---|---|
| O2 | present | Mode is batch over the whole store, out of process (Java subprocess) and not incremental. Results are written back to the `http://inferrences/` graph or to the current ontology (`reasoning.py:161-264,269+`). |
| X4 | absent | No Pydantic, JSON Schema or OpenAPI export (grep returns no hits) |
| X5 | present | Observers (`observe.py`). The X12 refinement is only partial (above). |
| D2 | absent | Sync only (see D7) |

### Proposed new features (round 2)

| Proposed id | Area | Feature | Owlready2 evidence |
|---|---|---|---|
| P16 | Persistence | **Undoable destructive operations**: delete returns an undo log that can be replayed | `destroy_entity(e, undoable=True)` (`prop.py:912-914`) |
| I5 | Identity | **IRI refactoring**: rename an entity or rebase a whole namespace, with references kept consistent | `EntityClass.set_iri/set_name` (`entity.py:68-83`), `Ontology.set_base_iri(…, rename_entities=True)` (`namespace.py:856+`), `_refactor_onto` (`triplelite.py:400-408`) |
| P17 | Persistence | **Source freshness / reload-if-newer**: track the last-update time per graph and reload a source only when it changed | `ontologies.last_update` (`triplelite.py:185`), `load(reload_if_newer=True)` (`namespace.py:969-981`) |

## Round 3

Checked against `BRIEF-round3.md`, `RUBRIC.md` (C9 and C10) and the "v2 features" section of `feature-taxonomy.adoc`.

**DEC-5 desk note:** the canonical repo is on Bitbucket (jibalamy), so GitHub stars do not apply. It has one maintainer and the last commit is 2026-08-11 (within 12 months). Whether it qualifies as a *dependency* under DEC-5 is a leader call. On a strict reading of DEC-5 it is ideas-only.

### (a) v2 cross-check

**Counts over the 19 v2 features:**

| Status | Count |
|---|---|
| present | 8 |
| partial | 5 |
| absent | 6 |

| Id | Status | Evidence |
|---|---|---|
| M16 | present | Multi-typed individuals get a synthetic `FusionClass` over all their types (`individual.py:422-470`). A custom deterministic `EntityClass.mro` handles inconsistent hierarchies (`entity.py:100-108`), and base classes are sorted by subclass depth (`entity.py:92-98`). |
| M17 | partial | Some checks happen at definition time: `base_iri` must end in `#`, `/` or `:` (`namespace.py:46`), and property kind conflicts are "fixed" with a stderr WARNING (`namespace.py:764-789`). Nothing checks predicate uniqueness or inverse-pair consistency. |
| I5 | present | `EntityClass.set_iri/set_name` (`entity.py:68-83`), `Ontology.set_base_iri(…, rename_entities=True)` (`namespace.py:856-915`), `Graph._refactor_onto` (`triplelite.py:396-408`) |
| I6 | present | Not needed: the weak identity map guarantees one object per storid per World (`namespace.py:377`), so default object identity is persistent identity |
| P16 | present | `destroy_entity(e, undoable=True)` returns an undo log (`prop.py:912-914`; `triplelite.py:781` `undoer_objs/undoer_datas`). There is no soft delete. |
| P17 | absent | Literals are stored inline in the `datas.o BLOB` column (`triplelite.py:181`). Grep finds no file offloading. |
| P18 | absent | `_add_quads_with_update` (`namespace.py:571`) has no hook; grep `hook` finds only `sys.excepthook` |
| P19 | present | `ontologies.last_update` (`triplelite.py:185`), `load(reload_if_newer=True)` (`namespace.py:969-981`) |
| Q19 | present | SPARQL `REGEX`, `CONTAINS`, `STRSTARTS`, `LIKE` (`sparql/parser.py:62`); `search(label="foo*")` wildcard and case-insensitive options (`namespace.py:288`) |
| Q20 | absent | Grep `vector\|embedding\|similarity` returns no relevant hits. Only BM25 full-text search (Q12). |
| S9 | absent | Single SQLite backend (`namespace.py:396-405`) |
| S10 | partial | `Ontology.load()` fetches a whole ontology document by its IRI over HTTP (`namespace.py:994-1012`) and *persists* it. It is not per-resource, read-only dereferencing. |
| S11 | partial | `Graph.analyze()` (`triplelite.py:249-294`); `set_backend(filename=…)` clones the in-memory store to a file (`triplelite.py:65-72`, `namespace.py:398-401`); `Ontology.destroy()` (`namespace.py:889`). No backup or vacuum API. |
| S12 | present | `owlready2.sparql.execute_many(onto, queries, params)` runs on the 3-connection pool (`doc/sync.rst`; `triplelite.py:54-61`) |
| S13 | present | `PreparedSelectQuery.execute` is a generator over the SQLite cursor (`sparql/main.py:282-334`); the `_LazyListMixin` search lists are lazy too |
| S14 | partial | `set_backend(profiling=True)` counts and times each SQL statement and offers `show_profiling()` (`triplelite.py:106-141`). Output goes to stderr only: no fingerprint, no logging integration. |
| X15 | partial | The Ontology works as a document: its quads share a `c` value and are loaded, saved and destroyed together (`triplelite.py:356-366`, `namespace.py:889,1117`). Fragment-IRI grouping per resource does not exist. |
| X16 | absent | — |
| D10 | absent | Grep `graphviz\|digraph` finds hits only in vendored `rply.py`. `dl_render.py` renders DL *text*, not diagrams. |

### (b) Developer experience (DX) deep-dive

**Shortest complete example: 11 lines.** It is assembled from `doc/intro.rst` (load, create), `doc/sparql.rst` (query) and readthedocs *world* (save). The docs have no single snippet covering all four steps.

```python
from owlready2 import *
default_world.set_backend(filename="pizza.sqlite3")            # world.rst
onto = get_ontology("http://www.lesfleursdunormal.fr/static/_downloads/pizza_onto.owl").load()
with onto:
    p = onto.Pizza("my_pizza")                                  # intro.rst
    p.has_topping = [onto.CheeseTopping(), onto.TomatoTopping()]
rows = list(default_world.sparql("""
    SELECT ?x { ?x a pizza_onto:Pizza }"""))                   # sparql.rst (auto prefix from IRI)
sync_reasoner()                                                 # optional: HermiT reclassification
default_world.save()                                            # commit
```

**Concepts to learn:**
- World, Ontology vs Namespace, storid;
- `with onto:` as the write context;
- functional vs non-functional properties (scalar vs list);
- `python_name`;
- `INDIRECT_` and `INVERSE_` prefixes;
- class constructs (`some/only/value`);
- class-level property semantics (`class_property_type`);
- `sync_reasoner` and its inference graph;
- the open-world assumption (and `close_world`).

The first five are needed for plain CRUD. The rest exists because OWL semantics leak into the object model.

**What developers love:**
- Pythonic access: `x.prop`, `list.append`, `Class(...)`.
- Classes come from the ontology with zero codegen.
- SPARQL results are live objects.
- No runtime dependencies.
- Fast on large ontologies.
- A thorough manual, plus a reference paper.

**What they hate:**
- **Typing and IDE support:** none. Attributes are resolved dynamically through `world._props` (`individual.py:264-298`), there are no type hints, and store methods are injected with `setattr` (`namespace.py:410-416`). Completion and mypy do not work.
- **Error messages:** some are good and actionable, for example
  `ValueError("Property '%s' is not functional, cannot assign directly (use .append() or assign a list).")` (`individual.py:343`) and
  `ValueError("Cannot assert facts in this namespace: it is not linked to an ontology! (it is probably a global namespace created by get_namespace(); please use your_ontology.get_namespace() instead)")` (`namespace.py:70`).
  Others are generic (`AttributeError("'%s' property is not defined.")`, `individual.py:295`) or silent stderr warnings ("I'm trying to fix it…", `namespace.py:764`).

**Footguns:**
1. Writes go through at once but are only committed by `world.save()`. Leaving `with onto:` does not commit, and there is no rollback.
2. Assigning a scalar to a non-functional property raises an error; reading one returns a list. Behaviour depends on whether the property is declared functional for *that class*.
3. A single global `python_name` namespace per World, so property names can collide across ontologies.
4. `default_world` is global, and objects from different Worlds must not be mixed.
5. `set_backend` after triples exist copies them, and fails if the file already exists (`triplelite.py:69-70`).
6. Exclusive mode is the default, so a second process cannot open the file.
7. Open-world reasoning surprises: `only` restrictions do not classify without `close_world`.
8. Other processes' writes never refresh cached objects.

**DX score: 3/5.** The happy path deserves a 5. Missing typing, OWL leaking into CRUD, and the transaction footguns pull it down.

### (c) Authorization seams

- **No access control of any kind.** Grep `acl\|permission\|auth` in the non-test `*.py` files finds no authz code. The only gate is the `read_only` flag on the SPARQL endpoint (`sparql/endpoint.py:35,50`) and SQLite `mode=ro` (`triplelite.py:80-81`).
- **Embedded in-process:** the app and the store share one Python process and one SQLite file. No network hop exists where a PEP could intercept queries; a PEP could only wrap the *application's* API (L4). Graph-level policy would need a wrapper around `World`/`Ontology` methods, but the dynamic `setattr` injection and the write-through `__setattr__` on every entity give no single choke point.
- The exposed endpoint (`EndPoint`) could sit behind an authorizing reverse proxy, but it is read-only GET with no named-graph filtering.
- **DEC-8 implication:** Owlready2 cannot be the runtime store of an ACL-agnostic rdf-persistence. If used at all, it belongs offline or out of the request path (see d), where authorization is irrelevant.

### (d) Layer coverage & codegen fit

| Layer | Coverage | Note |
|---|---|---|
| L0 modelling & codegen | partial | Loads, edits and reasons over OWL; builds classes at runtime (M6). No LinkML, SHACL or Pydantic output, and no codegen. |
| L1 domain & persistence | present (coupled) | Active Record objects are the domain objects |
| L2 stores & transactions | own only | SQLite quadstore; commit only; no remote backends |
| L3 identity & authz | absent | — |
| L4 data-management service | minimal | Read-only SPARQL GET endpoint |
| L5 JS client & UI | absent | — |
| L6 change events | partial | In-process `observe.py` listeners; no external delta stream |

**Role in an ontology-driven variant next to the LinkML one.** Owlready2 is a poor *runtime* L1/L2 choice for MWBv2. It reimplements the RDF stack (DEC-4), has no remote-store port or ACL seam, offers no typing, and has a bus factor of 1. It fits better as an **offline L0 toolchain step**:

1. **Consistency and classification** of the model2owl/LinkML-generated OWL during the build, using `sync_reasoner_hermit/pellet`. Inconsistency or unsatisfiable classes fail the build (a model quality gate).
2. **Materialising inferences** (subclass closure, inverse and transitive values) into an `inferred` named graph, exported as N-Triples or N-Quads and loaded into the real store. This is the O4 asserted/inferred split.
3. **Ontology exploration and scripting** for modellers (notebooks), including import resolution (O7).

The runtime ontology-driven variant should instead be built on rdflib with an owlrl/HermiT reasoner port. Owlready2's runtime-class idea (M6) and its OWL class-expression API (O3) are borrowed as design references only. This keeps the LinkML path (codegen → Pydantic) and the OWL path (reasoning → inferred graph) composable through shared standards: N-Triples/N-Quads and SPARQL 1.1 into the same store.

### (e) C9 and C10 scores

| # | Score | Justification | Evidence |
|---|---|---|---|
| C9 Composability | 1 | **Speaks:** SPARQL results JSON/XML/CSV out of a read-only endpoint; N-Triples, N-Quads and RDF/XML import/export; an rdflib Store facade (one direction only); OWL 2 in. **Lacks:** SPARQL Update over the protocol, GSP, JSON-LD, SHACL, LinkML, RDF/JS, OIDC. Its SPARQL dialect has non-standard extensions. It cannot sit behind a store port because it *is* the store, and the domain objects are bound to it. | `sparql/endpoint.py`, `driver.py:337-401`, `rdflib_store.py:27`, `sparql/parser.py:82-112`, `namespace.py:396-405` |
| C10 Maintainability & operability | 2 | **Good:** zero runtime deps and simple deployment (one SQLite file). **Weak:** bus factor 1; 0.x versioning with no semver promise; schema versioned in-store (`store.version`, `triplelite.py:178-179`, migrated in `triplelite_update.py`); no CI in repo; dense code with bare `except:`; the dynamic method injection blocks static analysis (GitNexus sees almost no call edges into the store API); observability limited to stderr profiling; Java needed for reasoning; Cython optional build. | `triplelite.py:106-141,178`, `triplelite_update.py`, `namespace.py:410-416` |

### (f) Proposed new features (round 3)

| Proposed id | Area | Feature | Owlready2 evidence |
|---|---|---|---|
| G1 | Generation (L0) | **Reasoner-based model quality gate**: build fails on inconsistency or unsatisfiable classes in the generated OWL | `sync_reasoner_*` raises `OwlReadyInconsistentOntologyError` (`reasoning.py`) |
| G2 | Generation (L0) | **Inference materialisation as a build artefact**: inferred triples exported to a dedicated named graph and file, loaded into the runtime store | `_INFERRENCES_ONTOLOGY` (`reasoning.py:75`) + `save(format="nquads")` (`driver.py:368`) |
| T1 | Transactions | **Explicit rollback that also resets cached object state** (Owlready2 shows the failure mode when it is missing: SQLite rollback leaves Python caches stale) | absence: no `rollback` in sources; caches in `Thing.__dict__` (`individual.py:291-297`) |
| E1 | Events | **Coalesced change notifications** (batch per entity and property before notifying) | `CoalescedObservations` (`observe.py:226`) |

## Round 4

Checked against `BRIEF-round4.md`, the "v3 features" section and the Id-mapping appendix of `feature-taxonomy.adoc`, and the integrated pages `index.adoc`, `building-blocks.adoc`, `variants.adoc`, `catalogue.adoc` and `libraries/owlready2.adoc`.

### (a) v3 cross-check

**Counts over the 102 v3 features:**

| Status | Count |
|---|---|
| present | 5 |
| partial | 12 |
| absent | 83 |
| n.a. | 2 |

My round-3 proposals now map to these v3 ids: G1 → G19, G2 → G20, T1 → T10, E1 → E8.

**How absences were confirmed.** Grep over the non-test, non-vendored `*.py` files with `acl|permission|auth|polic|savepoint|DoesNotExist|etag|if-match|outbox` found no relevant hits. The only hit was a licence line in the vendored `rply.py`. GitNexus also shows no store port: data access is injected with `setattr` at `namespace.py:410-416`.

| Id | Status | Evidence |
|---|---|---|
| AZ1–AZ29 | absent (all 29) | No authorization code at all (grep above). The only gates are `EndPoint(read_only=True)` (`sparql/endpoint.py:35,50`) and SQLite `mode=ro` (`triplelite.py:80-81`). The store runs embedded in-process, so there is no store boundary where a PEP could sit (Round 3 (c)). |
| G1 | absent | Classes are built at runtime and are persistence-coupled Active Record (`entity.py:110-166`, `individual.py:300`). Nothing static and persistence-free is generated. |
| G2 | absent | No separate mapper or repository layer; the store methods are injected into World and Ontology (`namespace.py:410-416`) |
| G3 | absent | No generator |
| G4 | absent | No generator. `owl:imports` is resolved at load time (`namespace.py:969+`), not at generation time. |
| G5 | absent | No generated code. At runtime IRIs are entity objects or `str`. |
| G6 | partial | At runtime `locstr` and `rdf:langString` round-trip (`util.py:53-63`, `base.py:320`), and language sublists are available (`util.py:137-150`). There is no schema or codegen side. |
| G7 | absent | No JSON-LD (grep, round 2) |
| G8 | absent | — |
| G9 | absent | — |
| G10 | absent | — |
| G11 | absent | — |
| G12 | absent | — |
| G13 | absent | — |
| G14 | absent | — |
| G15 | absent | — |
| G16 | absent | — |
| G17 | partial | Several OWL files are merged into one runtime model through `owl:imports`, `onto_path` and a catalog (`namespace.py:969-1020`). The target is a live object model, not a LinkML/schema file. There is no SHACL import. |
| G18 | absent | — |
| G19 | present | `sync_reasoner_hermit/pellet` raise `OwlReadyInconsistentOntologyError` (`reasoning.py:195,314`). Unsatisfiable classes become equivalent to `Nothing` (readthedocs *reasoning*; not re-checked in code). |
| G20 | present | Inferences go to the `http://inferrences/` ontology (`reasoning.py:75,170-171`) and can be exported per ontology as N-Triples or N-Quads (`driver.py:337-368`) |
| G21 | absent | — |
| G22 | absent | — |
| G23 | partial | Polymorphic typing comes from multiple `rdf:type` values and the synthetic `FusionClass` (`individual.py:422-470`). There is no designator slot other than `rdf:type` (M12 absent). |
| G24 | partial | OWL `OneOf` enumerations of named individuals, which are IRIs (`class_construct.py` `OneOf`). This is not a schema-to-code enum binding. |
| G25 | absent | — |
| G26 | n.a. | No mapping configuration. Properties form one global, flat namespace per World (`world._props`). |
| G27 | n.a. | No codegen |
| T1 | absent | No remote store; local SQLite only |
| T2 | absent | No version triple or compare-and-swap |
| T3 | absent | — |
| T4 | partial | Undo log only for deletes: `destroy_entity(e, undoable=True)` (`prop.py:912-914`, `triplelite.py:781`). It does not cover general writes. |
| T5 | present | Writes go through on one shared SQLite connection inside `BEGIN IMMEDIATE` (`triplelite.py:87,301-303`), so later reads and SPARQL in the same process see uncommitted writes before `World.save()` |
| T6 | absent | — |
| T7 | absent | — |
| T8 | absent | Grep `savepoint` returns no hits |
| T9 | absent | — |
| T10 | absent | Grep `rollback` returns no hits in the sources (round 1). Cached `__dict__` values and `CallbackList`s would go stale after a raw `db.rollback()` (`individual.py:291-297`). |
| T11 | absent | Parsing batches 30,000 triples per queue message (`driver.py:237-242`). That is a bulk-load detail, not an update-size limit. |
| E1 | absent | — |
| E2 | absent | — |
| E3 | absent | — |
| E4 | absent | — |
| E5 | absent | — |
| E6 | absent | — |
| E7 | absent | — |
| E8 | present | `CoalescedObservations` (`observe.py:226-258`) |
| E9 | absent | — |
| U1 | absent | — |
| U2 | absent | — |
| U3 | absent | — |
| U4 | partial | `instance_editor.py` and `editor.py` (EditObj3, desktop GTK/Qt) build edit forms at runtime from ontology classes and property domains/ranges (`instance_editor.py:31-116`, `editor.py:1-40`). Not web, not SHACL. |
| U5 | partial | `OntologyInstanceEditor` (`instance_editor.py:116`) is a desktop, schema-introspected instance browser and editor. It is not driven by an API description. |
| U6 | absent | — |
| U7 | absent | — |
| U8 | absent | — |
| U9 | absent | — |
| U10 | absent | — |
| RAD3 | absent | — |
| RAD4 | partial | The SPARQL endpoint is read-only by default (`EndPoint(read_only=True)`, `sparql/endpoint.py:35`). Mutations are enabled globally, not per class. |
| X17 | absent | — |
| X18 | absent | — |
| X19 | absent | Grep `etag\|if-match` returns no hits |
| X20 | absent | — |
| X21 | absent | The endpoint takes `?query=` over GET only (`sparql/endpoint.py:41-60`); there are no patch bodies on resources |
| X22 | absent | — |
| D11 | partial | Reasoner failures surface the Java message: `OwlReadyInconsistentOntologyError("Java error message is: %s")` (`reasoning.py:314`). SQLite errors propagate raw. |
| D12 | absent | Grep `DoesNotExist` returns no hits. Missing entities return `None` (`World.get`, `namespace.py:653-659`). |
| D13 | partial | Errors name the property but not the model, e.g. `"Property '%s' is not functional, cannot assign directly…"` (`individual.py:343`) and `"'%s' property is not defined."` (`individual.py:295`) |
| S15 | absent | — |
| S16 | absent | — |
| S17 | partial | `Ontology.load(reload=True / reload_if_newer=True)` replaces an ontology's triples wholesale from its file (`import_triples_from_queue(delete_existing_triples=True)`, `triplelite.py:890-895`). This is a full replace, not a diff. |
| S18 | present | Bulk parse runs in a separate process (fork) for files over 8 MB, with batched raw inserts (`driver.py:237-283`; `doc/sync.rst` "Parallelized file parsing"). It is separate from the per-attribute write path. |
| S19 | partial | Only `ontologies.last_update` per graph (`triplelite.py:185`, `namespace.py:956-960`). No message, author or digest. |

### (b) Purpose and origin

- **Built for:** *ontology-oriented programming* in biomedical informatics. Jean-Baptiste Lamy (LIMICS lab, Université Sorbonne Paris Nord) built it so that clinicians' and researchers' OWL ontologies (GO, UMLS through PyMedTermino2, drug ontologies) could be loaded, edited, *reasoned over* and scripted as ordinary Python objects. Reference paper: Lamy, *Artificial Intelligence in Medicine* 2017;80:11-28 (`README.rst`).
- **Context:** a single academic maintainer since about 2017 (Owlready 1 predates it). It is distributed through PyPI and conda-forge.
- **Desk scan (round 4):**

  | Source | Data |
  |---|---|
  | Bitbucket (canonical) | Commit 2026-08-11 |
  | GitHub mirror `pwin/owlready2` | 218 stars, but last push 2023-01-30 (stale) |
  | PyPI | Latest release 0.51 (the clone is at 0.52, unreleased) |
  | pypistats | About 102k downloads in the last month |

- **Design angle:**
  - **Ontology-first:** OWL TBox and ABox are one Python object graph.
  - **Store-first:** its own optimised SQLite quadstore, chosen for speed on large ontologies.
  - **Reasoning-first:** HermiT and Pellet bundled.

  Web APIs, remote triple stores, multi-user transactions and authorization were never goals. That explains the zero dependencies, the reimplemented RDF stack, Active Record write-through, and having no remote-store or ACL seam.
- **Therefore where it fits:**
  - Only **L0**, as an *offline* build or modeller tool: reasoner quality gate (G19), inference materialisation (G20), ontology exploration and scripting, import resolution (O7).
  - It does not fit L1/L2 in any variant: no SPARQL 1.1 client, no store port, Active Record coupling, no rollback, DEC-4.
  - It does not fit L3, L4, L5 or L6: no authz, only a read-only endpoint, no web UI, in-process observers only.

### (c) Variant fit

| Variant / approach | Effect | Why |
|---|---|---|
| V1 Portable Python core | neutral (L0 build step only); **blocks** if used at runtime | V1 needs any SPARQL 1.1 store behind rdf-persistence. Owlready2 is its own embedded store (`namespace.py:396-405`). As a CI step it can check and materialise OWL before loading into Oxigraph or Fuseki. |
| V2 semantic.works-compatible | neutral (L0 only) | Virtuoso holds the data. Inferred triples (G20) could be loaded as an `inferred` graph; the authz proxy is unaffected. |
| V3 Fluree | neutral (L0 only) | Fluree does its own RDFS-level reasoning for policy class targeting. OWL DL classification would stay a build step. |
| V4 GraphDB | neutral to redundant | GraphDB has built-in OWL2-RL/QL rulesets at load time, which makes a build-time materialisation partly redundant. A DL consistency gate (HermiT) still adds value. |
| V5 Graph-direct reads | neutral | Its endpoint is not policy-aware and only serves its own store, so it cannot be the read path |
| A Runtime mapper | enables idea only | Runtime class materialisation (M6) is the OWL analogue of reading `class_uri`/`slot_uri` at runtime. Borrow the idea, not the code. |
| B Generated mapper and routes | supports (build-time) | G19/G20 can be added as CI gates next to LinkML generation and the golden-file diff (G27) |
| C Generic service | idea only | It "interprets the schema at runtime", but for OWL and without any service layer |

**Headline:** Owlready2 supports no runtime variant and blocks none, as long as it stays an offline L0 tool. Using it as the runtime store would block V1, V3, V4 and V5 (no port, no remote store, no ACL seam).

### (d) Corrections to the integrated docs

1. **`libraries/owlready2.adoc`, "Proposed by this report":** it still lists the round-3 ids G1, G2, T1 and E1. They are now **G19, G20, T10 and E8** (Id-mapping appendix).
2. **`libraries/owlready2.adoc` "Activity" and `catalogue.adoc:135-140`, "GitHub stars do not apply":**
   - A GitHub mirror `pwin/owlready2` exists with **218 stars**, last pushed **2023-01-30**. It is a stale, third-party mirror.
   - The canonical Bitbucket repo has a 2026-08 commit.
   - Strictly, DEC-5 still fails on GitHub data (the stars belong to a mirror without recent commits), and Bitbucket has no star metric. Suggested wording: "No qualifying GitHub repo: mirror pwin/owlready2 has 218 stars but is stale since 2023; canonical Bitbucket active (2026-08); 0.51 on PyPI, about 102k downloads/month."
   - Also note that PyPI's latest release is **0.51**, while the analysed commit is 0.52.
3. **`catalogue.adoc` verdict "build-time" vs DEC-5.** If DEC-5 is read strictly as ideas-only, then using Owlready2 even as a build-time CI dependency needs an explicit leader exception. `building-blocks.adoc:36-37` presents it as "optional reasoner check" without noting this.
   - The reasoner check itself is HermiT or Pellet. An alternative build tool that runs HermiT/ELK directly from the command line is ROBOT (`robot reason`). It is not analysed here and is an open question.
   - Either way a **Java runtime is required in CI** (`reasoning.py:182,293`).
4. **`index.adoc:119` (Queries row).** It credits Owlready2 among the sources for "Typed SPARQL syntax tree, safe parameter binding; … errors that name model and property". Owlready2 contributes **only safe parameter binding** (`??` parameters, Q6):
   - it has **no typed SPARQL AST** (Q7 absent: SPARQL text goes through an rply grammar);
   - its errors name the **property, not the model** (D13 partial).

   Suggest narrowing the attribution.
5. **No contradiction found** in `variants.adoc` or the index score row (`index.adoc:62`, scores match the raw report). The round-1 feature counts in `libraries/owlready2.adoc` (22/10/10/1) match a recount of the raw table.

### (e) Proposed new features (round 4)

| Proposed id | Area | Feature | Owlready2 evidence |
|---|---|---|---|
| G28 | Generation | **Toolchain runtime prerequisites declared and checked** (e.g. a Java runtime for reasoner gates; the gate fails clearly when it is missing) | `owlready2.JAVA_EXE` and subprocess calls (`reasoning.py:182,293`) |
| G29 | Generation | **Reasoner profile choice for the gate** (DL consistency with HermiT/Pellet vs a cheaper EL/RL profile), with a datatype-support check (`ignore_unsupported_datatypes`) | `sync_reasoner_hermit(…, ignore_unsupported_datatypes=False)` (`reasoning.py:161`) |
| U11 | UI and client | **Desktop / notebook ontology instance editor** generated from the ontology (modeller tooling, not end-user UI) | `instance_editor.py:116`, `editor.py` |

## Round 5

Checked against `BRIEF-round5.md`, the "v4 features" section of `feature-taxonomy.adoc` (77 ids), and `libraries/owlready2.adoc` as published. Per the Id-mapping appendix, my round-4 proposals G28, G29 and U11 are now **G31, G32 and U12**.

### (a) v4 cross-check

**Counts over the 77 v4 features:**

| Status | Count |
|---|---|
| present | 3 |
| partial | 7 |
| absent | 63 |
| n.a. | 4 |

**How absences were confirmed.** Grep over the non-test `*.py` files with `on_commit|after_commit|opentelemetry|did you mean|redact|savepoint|etag|polic` found no relevant hits. Earlier rounds already showed there are no aggregates, no unit of work and no authz. Owlready2 has no store port at all (GitNexus: store methods injected with `setattr`, `namespace.py:410-416`), so no port-level feature can exist.

| Id | Status | Evidence |
|---|---|---|
| B1–B14, B16 | absent (15) | No aggregate concept, unit of work, change-set, outbox or version triple. Writes go through per attribute (`individual.py:300`). `destroy_entity` removes *all* inbound references (`prop.py:912+`, `triplelite.py:716-781`), which is the opposite of boundary-aware deletion (B13). |
| B15 | n.a. | There are never pending changes, because writes go through at once; reads always see them (T5, round 4) |
| PG1 | partial | SPARQL text is parsed into an internal block AST (`sparql/parser.py`, e.g. `MinusBlock` `:1270`) and rendered to **SQL** by `SQLQuery.sql()` (`sparql/main.py:684`). It has one internal renderer, is not pluggable, and does not render SPARQL. |
| PG2 | absent | — |
| PG3 | partial | Qualified relations via `owl:Axiom` reification (`AnnotatedRelation`, `annotation.py:25-55`). No RDF 1.2 triple terms and no LPG mapping. |
| PG4 | absent | — |
| EV1 | absent | `triplelite_update.py:25+` (`update_graph(graph, version)`) migrates the *internal quadstore format* on open, not user data. No migration runner. |
| EV2–EV6 | absent | — |
| EV7 | partial | The store-format version is stamped in `store.version` (`triplelite.py:178-179`) and checked and upgraded at open (`triplelite_update.py:25-33`). There is no domain-schema version check (`owl:versionIRI` is not used as a guard). |
| EV8 | absent | — |
| EV9 | absent | — |
| AZ30–AZ36 | absent (7) | No authorization code (rounds 3 and 4) |
| G28 | n.a. | It publishes no contracts |
| G29 | absent | Imports are lenient and only print stderr warnings when they "fix" something (`namespace.py:764-789`). No lossiness report. |
| G30 | absent | — |
| G31 | partial | The Java executable is configurable (`JAVA_EXE = "java"`, `__init__.py:22`), but it is not checked up front. A missing JVM surfaces as a raw subprocess error from `reasoning.py:192/304`. |
| G32 | partial | There is a choice between two DL reasoners (`sync_reasoner_hermit` / `sync_reasoner_pellet`, `reasoning.py:161,269`) and a datatype flag (`ignore_unsupported_datatypes`, `reasoning.py:161`). There is no EL/RL profile. |
| G33 | n.a. | No generated classes |
| G34 | absent | — |
| G35 | absent | Queries use kwargs (`world.search(prop=…)`, `namespace.py:288`) or SPARQL text. No typed field metamodel. |
| G36 | absent | — |
| T12 | absent | — |
| T13 | present | `EndPoint(read_only=True)` (the default) refuses non-SELECT queries (`sparql/endpoint.py:35,50`). The store can also open with `read_only=True` → SQLite `mode=ro` (`triplelite.py:79-81`). |
| T14 | absent | Worlds are independent stores. There is no cross-World session. |
| S20 | absent | — |
| S21 | absent | — |
| S22 | absent | — |
| S23 | absent | Local `Graph.analyze()` only (S11 partial). No remote stores. |
| X23 | absent | No JSON-LD |
| X24 | absent | — |
| E10 | absent | — |
| I7 | present | IRI = `namespace.base_iri + name`, and `entity.name` / `entity.iri` recover either part (`entity.py:67-83`, `individual.py:54-72`). Full IRIs resolve via `world["…"]`. |
| I8 | absent | Storids and IRIs are minted at construction (`individual.py:109-134`) |
| P20 | n.a. | No unit of work; writes go through in call order |
| U11 | absent | — |
| U12 | present | `instance_editor.py:31-116` (`OntologyInstanceEditor`) and `editor.py` (EditObj3 desktop UI) |
| U13 | absent | — |
| D14 | absent | — |
| D15 | absent | — |
| D16 | absent | — |
| D17 | partial | `PreparedQuery.sql` exposes the compiled SQL (`sparql/main.py:274-280`; `doc/sparql.rst`). `set_backend(profiling=True)` logs per-statement counts and times (`triplelite.py:106-141`). Bound values are not shown, and the target is SQL, not SPARQL. |
| D18 | absent | Attributes load lazily on first access (`individual.py:291-297`). There is no sentinel. |
| D19 | absent | — |
| D20 | absent | — |
| D21 | absent | Doc examples are `.rst` literal blocks. `test/regtest.py` is separate, and no doctest runner exists. |
| D22 | partial | SPARQL gets auto prefixes from ontology names (`doc/sparql.rst`), and `repr` is CURIE-like (`onto.Pizza`). Id arguments to `world[...]` need full IRIs (`namespace.py:653-659`). |
| D23 | absent | — |
| D24 | absent | — |
| D25 | absent | Multi-valued values come back in SQL row order, with no `ORDER BY` in the per-attribute getters (`prop.py:570-590`) |
| D26 | absent | — |
| D27 | absent | — |
| D28 | absent | — |
| D29 | absent | — |

### (b) Page review: `libraries/owlready2.adoc`

| # | Page text (quoted) | Problem | Fix |
|---|---|---|---|
| 1 | "Jean-Baptiste Lamy (LIMICS, Université Sorbonne Paris Nord; …)" (At a glance and Purpose and origin) | The university affiliation is not in the repo evidence. `README.rst` says only "the LIMICS reseach lab". | "Jean-Baptiste Lamy (LIMICS research lab, per `README.rst`)", or mark the university as external knowledge |
| 2 | "Single academic maintainer since about 2017 (Owlready 1 predates it)" | The clone is shallow (1 commit), so the history is not visible. The date comes from the 2017 paper. | Add "(per the 2017 paper; history not visible in the shallow clone)" |
| 3 | "L4 minimal (read-only SPARQL endpoint)" / "`sparql/endpoint.py` *serves* a read-only GET endpoint" / "it is read-only GET with no named-graph filtering" | Overstatement. It is read-only **by default**. `EndPoint(world, read_only=False)` executes INSERT/DELETE sent in the GET `?query=` parameter (`sparql/endpoint.py:35,50`). | "a GET SPARQL endpoint, read-only by default (`read_only=True`); with `read_only=False` it also runs INSERT/DELETE via GET, with no authentication" |
| 4 | "`with onto:` opens `BEGIN IMMEDIATE`" | Missing caveat. With a custom `lock=` (e.g. gevent) the context only takes the lock and does not start a transaction (`triplelite.py:306-308`). | Add "(default lock; with a custom `lock=` it only acquires the lock)" |
| 5 | "`sync_reasoner_hermit/pellet` serialise the whole world to N-Triples" | Slight overstatement. A list of ontologies can be passed, and then only those are saved (`reasoning.py:162-180`). | "serialise the world, or the listed ontologies, to N-Triples" |
| 6 | V4 row: "GraphDB's OWL2-RL/QL rulesets make materialisation partly redundant" | Not backed by evidence in this review | Append "(GraphDB documentation; not verified here)" |
| 7 | "Round-4 proposals (no id yet): …" | These now have ids | "Round-4 proposals now in the taxonomy: G31 toolchain prerequisites, G32 reasoner profile choice, U12 desktop instance editor" |
| 8 | Feature coverage table | Missing the round-5 row | Add "Round 5 (v4 additions, 77) \| 3 \| 7 \| 63 \| 4". Notable: T13 read-only guard, I7 reversible IRIs, U12 instance editor (present); PG1 internal SPARQL→SQL AST, EV7 store-format version, D17 inspectable SQL (partial). |

The rest of the page matches my evidence. In particular the scores, the transaction and rollback statements, the SPARQL coverage, the DEC-5 and mirror wording, and the variant table were all checked against the code citations.

### (c) Final verdict and three things to remember

**Final verdict: build-time.** It can be an offline L0 reasoner check and inference export, but only with an explicit DEC-5 exception and a Java runtime in CI. Otherwise it is ideas only. Never a runtime store or ORM for rdf-persistence.

**Three things a system architect must remember:**
1. **It is its own triple store, not an ORM over yours.** It runs embedded on SQLite, with its own parsers and a SPARQL subset compiled to SQL. It has no SPARQL 1.1 client, no store port and no ACL seam, so it cannot sit behind rdf-persistence or a PEP.
2. **Its persistence semantics are unsafe for services.** Attribute writes go straight to SQLite, only `World.save()` commits, and there is no rollback. Cached objects go stale across processes and after a failure.
3. **Its lasting value is OWL reasoning at build time.** That means HermiT/Pellet consistency and classification on the generated OWL, with inferences kept in a separate named graph (the asserted vs inferred split). The JVM is still needed, and ROBOT is the unanalysed alternative for the same gate.

### (d) Purpose and origin / variant fit

Already written in Round 4 (b) and (c).

### (e) New features

None. The taxonomy covers everything found.
