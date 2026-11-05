# SuRF (Semantic Universal Resource Framework)

- **Repo:** clone `/home/lps/work/repos/surfrdf` (upstream `github.com/cosminbasca/surfrdf`)
- **Commit analysed:** `91fb072` (2017-10-13, "Merge pull request #16"); shallow clone, 1 commit visible
- **Version:** 1.2.0 in `surf/__version__.py`; last PyPI release **SuRF 1.1.9 (2016-05-05)**, classifiers Python 2.6/2.7 only
- **Licence:** BSD-3 (DERI / NUI Galway), header in every file (`setup.py:1-33`)
- **Size:** library `surf/` + `plugins/` = 59 `.py` files, **7,802 LOC** (excluding tests); tests **1,487 LOC, 68 test functions** (`surf/test/`, py.test). Repo total 10,305 LOC, including `ez_setup.py` and `docs/source/conf.py`.
- **Python:** **Python 2 only.** The code uses `except X, e:` and `raise E, msg, tb` (`surf/plugin/sparql_protocol/writer.py:198-205`), `unicode`, `iteritems` and `__metaclass__`. `setup.py` has a PY3 branch, but the package does not parse on Python 3. CI (`.travis.yml`) runs on py2.6, py2.7 and pypy.
- **Dependencies:** `rdflib>=4.2.1`, `SPARQLWrapper>=1.7.6`, `six` (`requirements.txt`)
- **GitNexus index:** `surfrdf`, 116 files, 1,312 symbols, 2,905 edges, 99 clusters, 109 processes
- **Docs read:** https://surf-rdf.readthedocs.io/en/latest/ (index, `store_session.html`, `resources_classes.html`, `query.html`); in-repo `README.rst`, `CHANGELOG.rst`, `docs/source/*.rst`

## Summary

SuRF is an **Active Record** Object-RDF Mapper inspired by Ruby's ActiveRDF. Python classes are synthesised at runtime from an `rdf:type` IRI (`session.get_class(ns.FOAF.Person)`). Attributes follow the `prefix_localname` naming convention (`foaf_name`, inverse `is_foaf_knows_of`) and are resolved lazily, one SPARQL query per attribute. A `Store` is a reader/writer pair of plugins (rdflib, SPARQL protocol, Allegro, Sesame2), and a `Session` registers stores and synthesises classes. It is schema-less: there is no declared model, no validation and no typing. Its dirty tracking, writes and "commit" are coarse, and they use **pre-SPARQL-1.1 SPARUL syntax** (`INSERT INTO`, `DELETE FROM`, `OR`/`AND` in filters). It is dead: Python 2 only, single maintainer, last release in 2016.

## Architecture (GitNexus + source)

GitNexus clusters (by size): Sesame2 plugin (18 symbols), Query (17 + 11), Plugin (15), Resource (10/9/9/7), Translator (8), Sparql_protocol (7 + 7). The key classes (cypher `MATCH (c:Class)`):

| Layer | Classes | File |
|---|---|---|
| Session / factory | `Session` | `surf/session.py:61-356` |
| Domain base (Active Record) | `ResourceMeta`, `Resource` | `surf/resource/__init__.py:49, 99` |
| Lazy values | `LazyResourceLoader` (a `list` subclass) | `surf/resource/lazy.py` |
| Query object | `ResultProxy` (chainable `get_by/filter/order/limit/offset/full/context`) | `surf/resource/result_proxy.py:8` |
| Store facade | `Store` (reader + writer) | `surf/store.py:51` |
| Plugin SPI | `Plugin`, `RDFReader`, `RDFWriter`, `RDFQueryReader`, `NoneReader`/`NoneWriter` | `surf/plugin/*.py` |
| Plugins | rdflib, sparql_protocol (bundled); allegro_franz, sesame2 (external) | `surf/plugin/{rdflib,sparql_protocol}`, `plugins/` |
| Query AST | `Query`, `Group`, `NamedGroup`, `OptionalGroup`, `Union`, `Filter`, `QueryUpdate` | `surf/query/__init__.py`, `surf/query/update.py` |
| Translators | `SparqlTranslator`, `SparulTranslator` | `surf/query/translator/` |
| REST helper | `Rest` (Pylons-style index/create/update/delete/show) | `surf/rest.py:43` |

**Execution flows** (GitNexus processes, longest first):

- `Get_resource → _unicode` (9 steps): `Session.get_resource` → `map_instance` → `map_type` (synthesises the class with `type()`) → `Resource.__init__` → optional `load()`.
- `Load → _unicode` (8 steps): `Resource.load` → `Store.load` → `RDFQueryReader._load` → `query_s` → `SparqlTranslator`.
- `__instance_factory → __add_direct` (7 steps): builds resources from `get_by` results.
- `_save → Delete` / `_save → Insert`, and `_update → Delete` / `_update → Insert` (3 steps each): the writer builds a delete query, then an insert query.

## Implementation principles

- **Mapping:** there is none ahead of time. `Session.map_type(uri)` builds a class with `type(name, (Resource, *mixins), {'uri', 'store_key', 'session'})` (`session.py:245-266`). The optional `session.mapping = {type_iri: MixinClass}` adds behaviour per RDF type. `attr2rdf("foaf_name")` resolves the attribute name to a predicate through a global namespace registry (`surf/util.py:140`, `surf/namespace.py`).
- **Identity:** a resource is its subject IRI. `__eq__` and `__hash__` compare and hash on `subject` (`resource/__init__.py:896-908`). Without a subject, `uuid_subject(namespace)` mints a UUID IRI (`resource/__init__.py:187`). There is **no identity map**: every `get_resource` or query result builds a new instance (`# TODO: reuse already existing instances - CACHED`, `resource/__init__.py:461`). The docs' claim that the session "keeps a cache of already loaded data" is **claimed, not found in code** (`session.py:70` `# TODO: add cache`).
- **Lazy loading:** `__getattr__` returns a `LazyResourceLoader` wrapping a closure that runs `store.get(resource, predicate, direct)` on first access. That is **one SPARQL query per attribute** (N+1). Two counter-measures exist: `load()` fetches all direct and inverse triples at once, and `ResultProxy.full()` eager-loads in one sub-select query (`query_reader.py:299-330`). The `__full_direct` and `__full_inverse` flags skip queries once a full load has happened.
- **Dirty tracking:** one boolean per resource, stored in a **class-level global set** `Resource._dirty_instances` (`resource/__init__.py:169, 225-242`). That set is shared by every session and store in the process, so it is neither thread-safe nor session-scoped. **Bug:** `__getattr__` sets `self.dirty = False` after reading an unloaded attribute (`resource/__init__.py:517`), so reading an attribute after an edit silently discards the pending change from `commit()`.
- **Unit of work:** `Session.commit()` only loops over the global dirty set and calls `resource.update()` on each (`session.py:351-357`). There is no atomicity, no rollback and no ordering. `auto_persist` is declared but not implemented (`#TODO: add the auto_persist feature`, `resource/__init__.py:380`).
- **Update generation:** the writers use **replace strategies, not diffs**.
  - `save()` deletes every triple of the subject, then inserts every `rdf_direct` triple.
  - `update()` deletes `(s, p, *)` for each predicate held in memory, then inserts (`plugin/sparql_protocol/writer.py:154-166`; the rdflib equivalent is at `plugin/rdflib/writer.py:83-104`).
  - The SPARQL writer emits **SPARUL 1.0 / Virtuoso dialect**: `INSERT INTO <g> {…}`, `DELETE FROM <g> {…} WHERE`, and filters joined with `OR`/`AND` instead of `||`/`&&` (`writer.py:90, 119`; `translator/sparul.py:84, 101`). None of this is valid SPARQL 1.1 Update. The delete and insert are sent as **two HTTP requests** unless `combine_queries` is set, which concatenates them with `\n` instead of `;`.
- **Named graphs:** each resource has a `context` (graph IRI), and the SPARQL writer groups resources by context (`_group_by_context`). The rdflib writer **ignores the context** (`self._graph.add((s, p, o))`, `plugin/rdflib/writer.py:128`), so behaviour differs between stores.
- **Querying:** `Class.all()` and `Class.get_by(foaf_name="John")` return a lazy `ResultProxy`. `.filter(foaf_age="(%s > 15)")` pastes raw SPARQL text (an injection risk). The fluent `surf.query` builder (`select().where().filter()`) builds an AST that a translator turns into a string. Raw SPARQL goes through `store.execute_sparql()` and is **not** mapped back to objects (confirmed by the docs `query.html`).
- **Serialisation:** `resource.serialize(format)` goes through an rdflib graph. Its JSON format is **RDF/JSON (Talis), not JSON-LD** (`surf/serializer.py:46`). `rest.py` builds a resource from flat `json_params` keyed by `ns_predicate`.
- **Transactions:** none at the session level. The rdflib writer calls `graph.commit()` after each write. The Sesame2 plugin has an `RDFTransaction` XML document (`plugins/surf.sesame2/sesame2/sesame2.py:106`), which is store-specific.

## Patterns catalogue

| Pattern | Where |
|---|---|
| Active Record (persistence methods on the domain object) | `Resource.save/update/remove/load` (`resource/__init__.py:760-795`) |
| Dynamic class synthesis / metaclass | `Session.map_type` (`session.py:245`), `ResourceMeta` (`resource/__init__.py:49`) |
| Mixin per RDF type | `Session.mapping` (`session.py:258-262`) |
| Lazy load / virtual proxy | `LazyResourceLoader` (`resource/lazy.py`), `__getattr__` closures |
| Query Object (fluent, lazy) | `ResultProxy` (`resource/result_proxy.py`) |
| Interpreter / AST → string translator | `surf/query` + `translator/sparql.py`, `sparul.py` |
| Plugin / Strategy (store SPI, reader/writer split) | `Store`, `RDFReader`, `RDFWriter`, entry-point plugin manager (`plugin/manager.py`) |
| Null Object | `NoneReader`, `NoneWriter` (`plugin/reader.py:170`, `plugin/writer.py:193`) |
| Unit of Work (degenerate: global dirty set) | `Session.commit` + `Resource._dirty_instances` |
| Identity Map | **absent** (TODO in code) |

## Docs vs code

| Claim (source) | Status |
|---|---|
| "Session … keeps a cache of already loaded data" (`store_session.html`) | **Claimed, not found in code**: `session.py:70` `# TODO: add cache` |
| `auto_persist`: "resources are persisted … each time a modification occurs" (`session.py` docstring) | **Claimed, not found in code**: `#TODO: add the auto_persist feature` (`resource/__init__.py:380`) |
| Lazy loading of attributes; `load()` for bulk (`resources_classes.html`) | Confirmed (`__getattr__`, `load`) |
| `.first` / `.one` on multi-values (`resources_classes.html`) | Confirmed (`resource/lazy.py`, `result_proxy.py:238-260`) |
| "SuRF is an ORM similar to SQLAlchemy" (`README.rst`) | Overstated: no declared mapping, no identity map, no transactions |
| Named graph (context) support | Partial: SPARQL writer only; the rdflib writer ignores it |
| Queries documented: raw SPARQL + `select()` builder (`query.html`) | Confirmed. `get_by/filter/order/limit/full` exist in code but are documented only in docstrings. |

## Scores C1–C8

| # | Score | Justification | Evidence |
|---|---|---|---|
| C1 Feature coverage | 2 | CRUD, inverse properties, a query object and named graphs (partial) are present. There is no identity map, real UoW, transactions, validation or JSON-LD. Lang/typed literals exist only through rdflib `Literal` or `(value, lang)` tuples. | `util.py:321-346`, `session.py:351`, `serializer.py:46` |
| C2 Approach & patterns | 2 | Clear patterns (Active Record, Query Object, Plugin SPI, lazy proxy), but persistence sits inside the domain objects, and dirty state is global and buggy. | `resource/__init__.py:169, 517` |
| C3 Developer friendliness | 2 | The happy path is short (`get_class` → `get_by`), but there are no types, attributes are invisible to the IDE (`__getattr__`), `ns_predicate` naming is awkward, and the API docs are thin. | `resources_classes.html`, `util.py:140` |
| C4 Ease of adoption | 1 | Only 3 dependencies, but Python 2 only. It cannot be installed on a modern interpreter. | `.travis.yml`, `writer.py:198` |
| C5 Reuse of foundations | 3 | Builds on rdflib terms/graphs/parsers and SPARQLWrapper. It does reimplement a SPARQL query AST and string translator (its own query builder). | `query/`, `plugin/sparql_protocol/writer.py:131` |
| C6 Data-centric & DDD fit | 1 | Schema-less (classes come from `rdf:type` IRIs at runtime). Domain objects are Active Records. A repository layer is not possible without wrapping everything. | `session.py:245` |
| C7 SPARQL 1.1 portability | 1 | Writes use SPARUL 1.0 / Virtuoso syntax (`INSERT INTO`, `DELETE FROM`, `OR`/`AND`, `LIKE` in the docs). No Graph Store Protocol. | `translator/sparul.py:84,101`, `writer.py:90,119`, `result_proxy.py` filter docstring |
| C8 Health | 1 | 68 tests, Travis (dead), single maintainer, last release 2016, Python 2. Licence clear (BSD). | `git log`, PyPI JSON |

**JS-friendliness:** minimal. `surf/rest.py` is a Pylons-era CRUD helper that consumes flat JSON params, and output is RDF/JSON (not JSON-LD). It has no HTTP contract, schema export or TS types.

## Feature inventory

| Id | Status | Evidence |
|---|---|---|
| M1 Host-language classes | partial | Classes are synthesised from IRIs, not declared; mixins via `session.mapping` |
| M2 Schema language | absent | None |
| M3 Codegen | absent | None |
| M4 Inheritance → rdf:type | partial | `classes=` and `mapping` add Python bases. No `rdfs:subClassOf` reasoning. `Resource.concept()` picks a type. |
| M5 Validation | absent | `CardinalityException` exists, used only in `.one` |
| I1 IRI minting | present | `uuid_subject(namespace)` (`util.py:239`) |
| I2 Blank nodes | partial | `BNode` subjects accepted; no embedding semantics |
| I3 Identity map | absent | TODO at `resource/__init__.py:461` |
| R1 Single/multi values | partial | All values are lists (`LazyResourceLoader`); `.first`/`.one`; no `rdf:List` |
| R2 Object refs / inverse | present | Values are Resources; inverse via `is_<ns>_<p>_of` |
| R3 Lazy/eager | present | Per-attribute lazy loading; `load()`; `ResultProxy.full()` |
| R4 Cascade | absent | `remove(inverse=True)` deletes incoming triples only |
| L1 Typed literals | partial | Delegated to rdflib `Literal`; `value_to_rdf` |
| L2 Lang strings | partial | `(value, lang)` tuple or dict (`util.py:337-346`) |
| P1 CRUD | present | `save/load/update/remove` |
| P2 Update strategy | partial | Replace-all (`save`) or replace-per-predicate (`update`); no diff |
| P3 UoW / session flush | partial | `Session.commit()` over a global dirty set; buggy |
| P4 Transactions | absent | Not at session level; Sesame-specific only |
| P5 Optimistic concurrency | absent | None |
| P6 Named graphs | partial | Resource `context`; ignored by the rdflib writer |
| P7 Bulk load/export | partial | `store.load_triples(source)` (SPARQL `LOAD`, rdflib `parse`) |
| Q1 Fetch by IRI | present | `session.get_resource(iri, Class)` |
| Q2 Query builder | present | `get_by`, `filter` (raw SPARQL fragments), `surf.query.select()` AST |
| Q3 Raw SPARQL → objects | absent | `execute_sparql` returns raw results |
| Q4 Pagination/order | present | `limit/offset/order/desc` on `ResultProxy` |
| Q5 Property paths | partial | Chain attribute `.get_by()`; no path syntax |
| S1 In-memory | present | rdflib plugin |
| S2 Remote SPARQL | partial | `sparql_protocol` plugin via SPARQLWrapper, SPARUL 1.0 dialect |
| S3 Graph Store Protocol | absent | None |
| S4 Pluggable store | present | Reader/writer plugins via entry points (`plugin/manager.py`) |
| X1 JSON-LD | absent | RDF/JSON only |
| X2 Other formats | present | rdflib serialise/parse |
| X3 HTTP API | partial | `surf/rest.py` (Pylons-style helper, not a server) |
| X4 Schema export | absent | None |
| X5 Change events | absent | None |
| D1 Static typing | absent | None |
| D2 Async | absent | None |
| D3 Framework integration | partial | Pylons docs (`docs/source/integration/pylons.rst`) |
| D4 Docs | partial | Tutorial-ish pages + autodoc; query API under-documented |
| D5 Testing support | partial | rdflib in-memory store usable as a fake |
| O1 OWL semantics | absent | None |
| O2 Reasoner | absent | None |
| A1 ACL hooks | absent | Store credentials only |

### Proposed new features

- **Q6 Eager-load modifier on a query** (`full()` / `direct_only`): fetch subjects plus all their triples in one sub-select to avoid N+1 (`query_reader.py:299`).
- **R5 Inverse-property access by naming convention** (`is_x_of`): navigate incoming arcs without declaring an inverse.
- **M6 Runtime/dynamic classes from rdf:type** (schema-less mode) with optional mixins per type.
- **S5 Reader/writer split per store** (read from one endpoint, write to another).

## Reuse verdict for rdf-persistence: **borrow ideas** (no code; Python 2, dialect-locked)

Worth borrowing:

1. The **reader/writer split in the store port** (CQRS-ish; it lets you read from a replica or SPARQL endpoint and write elsewhere) plus Null Object stores for tests.
2. A **lazy, chainable query object** (`ResultProxy`) with `first()`/`one()` semantics (SQLAlchemy-like `NoResultFound`/`MultipleResultsFound`) and an explicit **eager `full()` mode** in one query.
3. **Inverse-arc navigation** as a first-class concept.
4. **Grouping writes by named graph** before emitting updates.

## Risks / anti-patterns observed

- A **global, class-level dirty set** shared across sessions, and reads that **clear the dirty flag** (`resource/__init__.py:517`). This leads to silent lost updates. rdf-persistence MUST keep dirty state per session or UoW, and per attribute.
- **No identity map:** the same IRI loaded twice gives two objects with diverging state.
- **Replace-all updates** (`DELETE s ?p ?o` then `INSERT`) wipe triples the object never loaded. They also go out as **two non-atomic requests**.
- **Dialect lock-in:** SPARUL 1.0 / Virtuoso syntax.
- **String-built SPARQL** with user fragments (`filter(foaf_name="(%s LIKE 'J%%')")`, `"?s = <%s>"` formatting) is an injection risk.
- `__getattr__` magic plus `ns_predicate` names give no typing and no IDE support.
- Store behaviour diverges between plugins: the rdflib writer ignores named graphs.

## Round 2 cross-check (taxonomy v1)

Checked against `docs/modules/ROOT/pages/architecture/soa/feature-taxonomy.adoc` (v1). Every "absent" verdict was confirmed by a grep of `surf/` and `plugins/` (tests excluded) and by looking where the feature would live. The key greps returned **0 hits** for: hooks (`pre_save|post_save|hook`), `retry|backoff|timeout`, `async|await`, `jsonapi`, full-text (`bif:contains|text:query`), `shacl|sh:`, reification (`rdf:Statement|<<`), `xone|exclusive`, `upsert|get_or_create`, `skolem`, `register_function`.

| Id | Status | Evidence |
|---|---|---|
| M6 Runtime model materialisation | present | `Session.map_type` builds classes with `type()` from an rdf:type IRI (`surf/session.py:245-266`) |
| M7 Convention-based predicate derivation | present | `foaf_name` → `foaf:name` via `attr2rdf` (`surf/util.py:140`). Per-field override only through dict access with a `URIRef` key (`resource/__init__.py:423-431`). |
| M8 JSON-LD context as mapping | absent | Would live in `util.attr2rdf` / `namespace.py`; no JSON-LD code (only RDF/JSON in `serializer.py:46`) |
| M9 Attribute ≠ property | absent | `attr2rdf` is 1:1 (`util.py:140-180`); all language variants come back in one list |
| M10 Behaviour bound to schema classes | present | `Session.mapping = {type_iri: Mixin}` adds methods per RDF type (`session.py:258-262`) |
| M11 Strict / warn-on-unmapped import | absent | Schema-less by design; `Resource.set(graph)` (`resource/__init__.py:812`) accepts everything |
| M12 Alternative type discriminator | absent | `Resource.concept()` / `__instance_factory` use `rdf:type` only (`resource/__init__.py:609-640, 859`) |
| M13 Constraint emission | absent | No schema exists to emit from; no `shacl` hits |
| M14 Reverse engineering from data | absent | M6 builds classes on the fly but generates no model artefact |
| M15 External model-file compat | absent | No model file format |
| I4 Skolemisation policy | absent | Would live in `uuid_subject` (`util.py:239`); `skolem` returns 0 hits; BNodes are passed through raw |
| R5 Cardinality constraints on relations | absent | `CardinalityException` is raised only by `.one()` reads (`resource/lazy.py:73`, `exceptions.py`); never checked on write |
| R6 Mutually exclusive relations | absent | 0 hits |
| R7 Relations with own properties | absent | 0 hits for reification or RDF-star |
| R8 Inverse navigation without declaration | present | `is_foaf_knows_of` naming, `rdf_inverse` dict (`resource/__init__.py:203, 404, 487`; `util.py:181-220`) |
| L3 Pluggable literal-type registry | absent | `value_to_rdf` hard-codes tuple and dict handling and defers to rdflib `Literal` (`util.py:321-350`); no registry |
| P8 Owned-predicate semantics | partial | `update()` deletes only predicates held in `rdf_direct`, so foreign predicates survive (`plugin/sparql_protocol/writer.py:111-124, 161-166`). `save()` deletes **all** subject triples (`:154-159`). |
| P9 Change detection / minimal diff | partial | One dirty boolean per resource in a global set (`resource/__init__.py:169, 225-242`); no diff (replace per predicate) |
| P10 Collection patch operators | partial | `LazyResourceLoader.append/extend/insert/remove/pop` mark the resource dirty (`resource/lazy.py:140-175`), but they are written back by replacing the predicate |
| P11 Orphan cleanup | absent | `remove(inverse=True)` deletes incoming arcs only (`writer.py:168-172`); no composition notion |
| P12 Policy-driven graph placement | absent | The graph is the caller- or store-default `context` (`resource/__init__.py:193-198`); no rules |
| P13 Transaction options | absent | No transactions (`session.py:351`) |
| P14 Bulk upsert / get-or-create | absent | 0 hits; `Store.save(*resources)` is a multi-save, not keyed upsert |
| P15 Concurrency mode | absent | Global `_dirty_instances` with no locking; `Lock` hits only in `log.py` |
| Q6 Injection-safe parameter binding | absent | Values are `.format`-ed into SPARQL (`writer.py:90,119`); `filter()` pastes raw strings (`result_proxy.py:160-197`) |
| Q7 Typed SPARQL AST builder | partial | `Query/Group/NamedGroup/OptionalGroup/Union/Filter` objects (`surf/query/__init__.py`) → `SparqlTranslator`; filters stay raw strings |
| Q8 Derived query methods | absent | `get_by(**kw)` keyword filters only (`resource/__init__.py:669`) |
| Q9 Eager loading / N+1 avoidance | present | `ResultProxy.full()` → one sub-select + UNION query (`result_proxy.py:70`, `plugin/query_reader.py:299-330`); `Resource.load()` |
| Q10 Grouped result mapping | present | Inner `SELECT ?s … LIMIT/OFFSET` sub-query, rows grouped per subject into resources (`query_reader.py:299-330`, `__instance_factory` at `resource/__init__.py:609`) |
| Q11 Query safety checks on user SPARQL | absent | `execute_sparql` passes through (`store.py:160`) |
| Q12 Full-text search | absent | 0 hits; only a Virtuoso `LIKE` example in the `filter()` docstring |
| Q13 User-defined SPARQL functions | absent | 0 hits |
| Q14 Standard external filter language | absent | 0 hits (CQL2, JSON:API) |
| Q15 Totals / facets / counts | partial | `ResultProxy.__len__` runs the full query and counts rows client-side (`result_proxy.py:232-236`); no `COUNT` (0 hits) |
| Q16 Configurable open-world negation | absent | No negation in the query builder |
| Q17 Polymorphic query over subclasses | absent | `get_by` binds an exact `rdf_type` (`resource/__init__.py:684-686`); no `subClassOf` expansion |
| Q18 CBD extraction | partial | `describe()` builder (`query/__init__.py:520`; DESCRIBE semantics are store-defined); `load()` fetches direct + inverse triples without bnode closure |
| S5 Read / write split and routing | present | `Store(reader=…, writer=…)` with separate plugins and endpoints (`store.py:66-87`, `writer.py:131-137`) |
| S6 Client-side cache with invalidation | absent | `session.py:70` `# TODO: add cache` |
| S7 HTTP resilience | absent | 0 hits for retry, backoff or timeout |
| S8 Community-standard store port | partial | Own `RDFReader`/`RDFWriter` SPI; the rdflib plugin wraps any rdflib `Store` (`plugin/rdflib/writer.py:68-76`) |
| X6 Generated JSON:API contract | absent | 0 hits |
| X7 Content negotiation | absent | The `Accept` hits are SPARQL result formats in the readers, not an API |
| X8 Hypermedia contract | absent | No Hydra |
| X9 API ↔ storage vocabulary mapping | absent | — |
| X10 Read models / projections | absent | — |
| X11 Annotated representations | absent | One `label` hit, unrelated |
| X12 Delta / change-set format | absent | — |
| X13 Request-context propagation | absent | — |
| X14 Graph / model diff API | absent | — |
| D6 Lifecycle hooks | absent | 0 hits; would live in `Resource.save/update/remove` (`resource/__init__.py:760-779`) |
| D7 Sync + async single source | absent | 0 hits |
| D8 Multi-store test matrix | absent | Tests cover rdflib and the query reader only (`surf/test/plugin/`) |
| D9 Service template / scaffold | absent | — |
| RAD1 Zero-code CRUD service | partial | `Resource.rest_api(ns)` → `Rest` index/create/update/delete/show per class (`surf/rest.py:43-165`); a helper, not a server |
| RAD2 Declarative routing / gateway | n.a. | Out of library scope |
| O3 OWL class-expression API | absent | — |
| O4 Inferred vs asserted views | absent | — |
| O5 Local closed-world closure | absent | — |
| O6 Rule support | absent | — |
| O7 Ontology import resolution | absent | The `imports` hits are Python imports |
| A2 Auth-proxy compatibility (no GRAPH reliance) | partial | Works without a context, but contexts use `FROM`/`INTO <g>` and `GRAPH` (`translator/sparul.py:84,101`, `writer.py:84-102`) |
| A3 Field-level access modes | absent | — |
| *v0 re-marked:* O2 Reasoner (mode dimension) | absent | No reasoner integration |
| *v0 re-marked:* X4 Schema export incl. Pydantic / JSON Schema | absent | No schema |
| *v0 re-marked:* X5 Change notifications (refined by X12) | absent | — |
| *v0 re-marked:* D2 Async (refined by D7) | absent | — |

**Counts (63 v1 features):** 7 present, 9 partial, 46 absent, 1 n.a.

### Proposed new features (round 2)

- None specific to SuRF beyond those listed in `oldman.md`.

## Round 3

### (a) v2 cross-check

The greps in `surf/` and `plugins/` (tests excluded) for `rename|soft|undo|vector|similar|replicat|backup|stream|timing|elapsed|diagram|graphviz|mtime|Last-Modified|ETag` returned no matches beyond the ones cited below.

| Id | Status | Evidence |
|---|---|---|
| M16 Multi-typed instances, deterministic resolution | partial | `get_class(uri, classes=[…])` plus `session.mapping` give Python MRO over mixins (`session.py:245-266`). But an instance carries one `uri` (rdf:type), and `Resource.concept()` / `__instance_factory` pick the first type (`resource/__init__.py:609-640, 859`). |
| M17 Mapping validation at class-definition time | absent | There is no declared mapping to validate. `attr2rdf` resolves names lazily at access time (`util.py:140`). |
| I5 IRI / namespace renaming | absent | No hits. Changing `subject` is impossible (read-only property, `resource/__init__.py:220`). |
| I6 Equality / hash by persistent identity | present | `__eq__` and `__hash__` on `subject` (`resource/__init__.py:892-908`) |
| P16 Undoable / soft deletes | absent | `remove()` deletes triples (`plugin/sparql_protocol/writer.py:168-172`) |
| P17 Large-literal offloading | absent | No hits |
| P18 Write-path quad-transformation hooks | absent | No hook. The only seam is subclassing a writer plugin (`plugin/writer.py:49-140`). |
| P19 Change-aware reload | absent | `load_triples` / `load_from_source` always re-parse (`plugin/rdflib/writer.py:139-155`, `resource/__init__.py:797`) |
| Q19 Regex / substring filters | present | `Filter.regex(var, pattern, flag)` (`query/__init__.py:92-113`). `ResultProxy.filter(x="(regex(%s,…))")` pastes raw SPARQL text. |
| Q20 Vector / similarity search | absent | No hits |
| S9 Multi-backend replication | absent | `Session` holds several stores (`session.py:94-120`), but each class or resource is bound to one `store_key`. Nothing writes to all stores. |
| S10 Linked Data dereferencing store | partial | `Resource.load_from_source(location=url)` / `Session.load_resource` parse a remote document into one resource (`resource/__init__.py:797-811`, `session.py:325-345`). It is not a store. |
| S11 Embedded-store administration | partial | `store.clear(context)`, `size()`, `load_triples` (`store.py:167-235`). `index_triples` returns False. No backup or optimise. |
| S12 Batched queries in one call | partial | Writer `combine_queries=True` joins the delete and insert into one request (`writer.py:135, 189-196`). Reads are not batched. |
| S13 Streaming large result sets | absent | `ResultProxy.__iterator` yields from a fully materialised result (`result_proxy.py:206-230`) |
| S14 Query observability | partial | Query strings logged at debug level (`writer.py:192`, `query_reader.py`). No timing or fingerprint. |
| X15 Document-centric grouping | absent | No hits for `hashless` or `document` |
| X16 Standard API profile conformance | absent | No hits |
| D10 Model diagram generation | absent | No hits |

v2 counts: 2 present, 6 partial, 11 absent.

### (b) Developer experience deep-dive

**Shortest complete CRUD example.** It is 12 lines, put together from the test fixture and test body in `surf/test/resource/test_resource.py:9-16, 38-46` (create and read). Update and delete come from the Resource API.

```python
store = surf.Store(reader="rdflib", writer="rdflib")
session = surf.Session(store)
Person = session.get_class(surf.ns.FOAF.Person)        # class synthesised at runtime
p = session.get_resource("http://smth", surf.ns.FOAF.Person)
p.foaf_name = "John"; p.save()                          # create
p = session.get_resource("http://smth", surf.ns.FOAF.Person)
list(p.foaf_name)                                       # read (lazy; must "poke" the attribute)
p.foaf_name = "Johnny"; p.update()                      # update (or session.commit())
p.remove()                                              # delete
```

The README's only example (`README.rst:46-65`, 10 lines) is read-only. The test body is also an odd pattern to copy, because it has to "poke" the attribute (`list(instance.foaf_name)`) before using it.

**Concepts to learn (8):** Store (reader and writer plugins plus kwargs), Session (store registry and class factory), the `prefix_localname` / `is_x_of` naming, namespace registration (`surf.ns.register`), `LazyResourceLoader` (list semantics, `.first`, `.one`), `ResultProxy` (chaining, `full()`), the save / update / commit difference, and context (named graph).

**Typing and IDE:** none. Attributes resolve dynamically through `__getattr__`, so there is no autocomplete. A typo such as `p.foaf_nmae` silently becomes a new predicate if the prefix is registered. Python 2 only.

**Real error messages:**
- `AttributeError: Not a predicate: foo` (`resource/__init__.py:478`): clear.
- `SparqlWriterException("Bad query: %s" % query_str)` (`writer.py:208`): at least it echoes the generated query.

**Docs:** short tutorial pages plus autodoc. `get_by`, `filter`, `full` and `order` are documented only in docstrings, and the docs promise a cache that does not exist.

**Footguns:**
1. Reading an attribute clears the dirty flag, so changes are silently not committed (`resource/__init__.py:517`).
2. The dirty set is global across sessions (`:169`).
3. `save()` deletes every triple of the subject, including ones it never loaded.
4. Two instances of the same IRI can hold diverging state, because there is no identity map.
5. The rdflib writer silently ignores named graphs.
6. The write syntax (SPARUL 1.0) fails on strict SPARQL 1.1 endpoints.

**DX score: 2/5.** The happy path is short and pleasantly Pythonic, but the silent data-loss footguns, missing types and Python 2 outweigh it.

### (c) Authorization seams

SuRF has no authorization concept: no principal, no request context, no read-only fields.

- **PEP hook location:**
  - The single choke point is the `Store` facade. Every read (`get`, `load`, `get_by`, `execute_sparql`) and every write (`save`, `update`, `remove`, `*_triple`) passes through `surf/store.py:120-235`.
  - Because readers and writers are plugins, a PEP could instead be a **decorating reader/writer plugin** that wraps a real plugin and filters or blocks calls.
  - Raw `execute_sparql` bypasses any object-level check, so a PEP must sit at or below the store.
- **Behind an authorizing SPARQL proxy** (graph rewriting, for example mu-authorization or sparql-proxy): **poor fit.**
  - Writes use non-standard `INSERT INTO <g>` / `DELETE FROM <g>` and `OR`/`AND` filters (`translator/sparul.py:84,101`, `writer.py:90,119`). A proxy that parses SPARQL 1.1 rejects them.
  - Contexts emit explicit `GRAPH` / `FROM` clauses, which conflicts with proxies that own graph placement.
  - It would work only for reads without a context, and with writes rewritten to SPARQL 1.1.
- **Verdict:** nothing to borrow for authorization except the idea that a reader/writer plugin decorator is a cheap PEP seam.

### (d) Layer coverage and codegen fit

| Layer | Coverage |
|---|---|
| L0 modelling and codegen | none. Classes are synthesised at runtime from `rdf:type`, with no schema input. |
| L1 domain and persistence | yes (Active Record core) |
| L2 stores and transactions | partial: plugin store SPI, no transactions |
| L3 identity and authorization | none |
| L4 data-management API | minimal: `surf/rest.py` Pylons-style CRUD helper |
| L5 JS client and UI | none (RDF/JSON output only) |
| L6 change events | none |

**Codegen fit:** there is no model input, so LinkML output has nowhere to plug in. The closest analogue is `session.mapping`, which could take generated mixins per `class_uri`, but types and validation would be lost.

### (e) C9 and C10

| # | Score | Justification | Evidence |
|---|---|---|---|
| C9 Composability / ecosystem fit | 1 | Uses rdflib and SPARQLWrapper, but writes a pre-1.1 SPARUL dialect, serialises RDF/JSON (not JSON-LD), and has its own store SPI (not the RDF/JS or rdflib Store port). No SHACL, LinkML or GSP. | `translator/sparul.py:84,101`, `serializer.py:46`, `plugin/writer.py:49` |
| C10 Maintainability and operability | 1 | 7.8k LOC with moderate surface. But it is Python 2 only, has global mutable state, depends on entry-point plugin discovery (`plugin/manager.py`), and has a dead upstream (single maintainer, last release 2016) with no upgrade path. Logging only, no observability. | `.travis.yml`, `resource/__init__.py:169`, PyPI JSON |

### (f) Proposed new features (round 3)

- **AZ1 PEP as a store-port decorator:** an authorization wrapper around the reader/writer port. Every object-level and raw-SPARQL call passes through it (SuRF `Store` facade plus plugin SPI).

## Round 4

### (a) v3 cross-check (102 features)

I confirmed each absence by grep over `surf/` and `plugins/` (tests excluded). The patterns `policy|permission|acl|principal|tenant|outbox|notify|websocket|mercure|etag|if-match|cursor|openapi|graphql|frame|typescript|savepoint|idempot|history|batch_size` hit nothing except licence text ("written permission"). The Id-mapping appendix maps my round-3 proposal AZ1 to v3 **AZ1**; I record it here as a seam only.

| Id | Status | Evidence |
|---|---|---|
| AZ1 | absent | There is no decorator. The seam is the `Store` facade, which every read and write passes through (`store.py:120-235`), and the reader/writer plugin SPI. Greps for `policy`, `acl`, `principal` and `permission` found only licence text. |
| AZ2 | absent | No policy injection. Queries are built in `plugin/query_reader.py:47-330`. |
| AZ3 | absent | The `surf.query` AST exists (`query/__init__.py`) but has no policy nodes. |
| AZ4 | absent | No PDP integration |
| AZ5 | absent | No changeset. `Session.commit` iterates a global dirty set (`session.py:351-357`). |
| AZ6 | absent | `rest.py` has no hooks |
| AZ7 | absent | — |
| AZ8 | absent | — |
| AZ9 | absent | — |
| AZ10 | absent | — |
| AZ11 | absent | — |
| AZ12 | absent | — |
| AZ13 | absent | Contexts are fixed per resource or store (`resource/__init__.py:193-198`); no templates |
| AZ14 | absent | — |
| AZ15 | absent | — |
| AZ16 | absent | — |
| AZ17 | absent | — |
| AZ18 | absent | — |
| AZ19 | partial | Static credentials per writer instance only (`setCredentials(user, password)`, `plugin/sparql_protocol/writer.py:137-142`); nothing per request |
| AZ20 | absent | — |
| AZ21 | absent | No principal or trust parameter on `save`/`update` |
| AZ22 | n.a. | No client cache (`session.py:70` TODO) |
| AZ23 | absent | — |
| AZ24 | absent | Exceptions are store and cardinality errors only (`exceptions.py`) |
| AZ25 | absent | — |
| AZ26 | absent | — |
| AZ27 | absent | — |
| AZ28 | absent | — |
| AZ29 | absent | No model to generate from |
| G1 | absent | No generated classes; classes are built with `type()` at runtime (`session.py:245`) |
| G2 | absent | — |
| G3 | absent | — |
| G4 | absent | — |
| G5 | absent | — |
| G6 | absent | Language is only a `(value, lang)` tuple at runtime (`util.py:337`) |
| G7 | absent | No JSON-LD at all (`serializer.py:46` is RDF/JSON) |
| G8 | absent | — |
| G9 | absent | — |
| G10 | absent | `rest.py` is a hand-wired helper, not generated |
| G11 | absent | No Hydra |
| G12 | absent | — |
| G13 | absent | — |
| G14 | absent | — |
| G15 | absent | — |
| G16 | absent | — |
| G17 | absent | — |
| G18 | absent | — |
| G19 | absent | — |
| G20 | absent | — |
| G21 | absent | — |
| G22 | absent | — |
| G23 | absent | The type is taken from `rdf:type` (`resource/__init__.py:609-640`); no designator slot |
| G24 | absent | — |
| G25 | absent | — |
| G26 | absent | No mapping config to inherit; Python MRO over mixins only |
| G27 | absent | — |
| T1 | partial | `combine_queries` joins DELETE and INSERT into one request per context group, but separates them with `\n`, not `;` (`plugin/sparql_protocol/writer.py:189-196`). Otherwise it sends two requests. |
| T2 | absent | No version triple. Greps for `version` and `etag` found nothing in the writers. |
| T3 | partial | The Sesame2 plugin posts an `application/x-rdftransaction` document (`plugins/surf.sesame2/sesame2/sesame2.py:106-130`). It is vendor-specific and single-request. |
| T4 | absent | — |
| T5 | absent | — |
| T6 | absent | — |
| T7 | absent | `index_triples` returns False and `_size` raises `NotImplementedError` (`writer.py:286, 175-177`), but there is no capability descriptor |
| T8 | absent | — |
| T9 | absent | — |
| T10 | absent | No rollback; `commit` does not reset objects |
| T11 | absent | — |
| E1 | absent | Greps for `outbox`, `notify`, `websocket` and `mercure` found nothing |
| E2 | absent | — |
| E3 | absent | — |
| E4 | absent | — |
| E5 | absent | — |
| E6 | absent | — |
| E7 | absent | — |
| E8 | absent | — |
| E9 | absent | — |
| U1 | absent | — |
| U2 | absent | — |
| U3 | absent | — |
| U4 | absent | — |
| U5 | absent | — |
| U6 | absent | — |
| U7 | absent | — |
| U8 | absent | — |
| U9 | absent | — |
| U10 | absent | — |
| RAD3 | absent | — |
| RAD4 | absent | `Rest` exposes create, update and delete for every class (`rest.py:78-130`) |
| X17 | absent | — |
| X18 | absent | — |
| X19 | absent | No ETag or If-Match |
| X20 | absent | Offset only (`result_proxy.py:63`) |
| X21 | absent | — |
| X22 | absent | — |
| D11 | partial | `SparqlWriterException` carries the SPARQLWrapper exception text and the query (`writer.py:204-210`); no structured store error body |
| D12 | absent | Generic `NoResultFound` / `MultipleResultsFound` (`exceptions.py`) |
| D13 | absent | `AttributeError('Not a predicate: %s')` names the attribute only (`resource/__init__.py:478`) |
| S15 | absent | — |
| S16 | absent | — |
| S17 | absent | `save()` is delete-all-then-insert, with no diff (`writer.py:154-159`) |
| S18 | partial | `store.load_triples(source)` → SPARQL `LOAD` or rdflib `parse`, separate from object writes (`writer.py:294-317`, `plugin/rdflib/writer.py:139-155`) |
| S19 | absent | — |

**v3 counts: 0 present, 5 partial, 96 absent, 1 n.a.** That is expected for a 2009–2016 Active Record ORM: the v3 areas (authorization, generation, transactions, events, UI) came after it.

### Purpose and origin

- **Built for:** treating RDF resources on any triple store as Python objects without declaring a model, in the style of Ruby's ActiveRDF. It came out of the DERI / NUI Galway Semantic Web research context, around 2009.
  - Authors: Cosmin Basca (licence header and `setup.py`) and Peteris Caune (`resource/lazy.py` `__author__`).
  - Activity: last release 2016, last commit 2017. GitHub shows 44 stars and is not archived (`gh api`, pushed 2021-10-22).
- **Design angle:**
  - Schema-less exploration of Linked Data (DBpedia and FOAF examples).
  - Store plugins first, so the same code runs against rdflib, Sesame, Allegro or Virtuoso.
  - Convenience over correctness: Active Record, lazy attributes, SPARUL 1.0, the Virtuoso dialect of its time.
- **Where it could fit:**
  - **L1 and L2 ideas only.** The reader/writer store split, one-query eager loading and inverse navigation are reusable ideas.
  - It does **not fit** L0 (no model, contradicting LinkML-first), L3 (no principal), L4–L6, or any variant as a dependency (Python 2, fails DEC-5).

### (c) Variant fit

| Candidate | V1 Portable core | V2 semantic.works | V3 Fluree | V4 GraphDB | V5 CQRS reads | A Runtime mapper | B Generated | C Generic service |
|---|---|---|---|---|---|---|---|---|
| SuRF (ideas only) | supports (S5 reader/writer split; Q9 `full()` eager load) | blocks if reused as-is: SPARUL `INSERT INTO`/`DELETE FROM` is rejected by a SPARQL 1.1 parsing proxy such as `sparql-parser` | neutral | neutral (the Sesame `x-rdftransaction` idea predates RDF4J transactions, T3) | supports (a reader on the replica or endpoint, a writer elsewhere) | weak: dynamic classes from `rdf:type` are the *schema-less* opposite of A | none | weak: a runtime class factory, but no schema to drive a service |

### (d) Corrections to the integrated docs

1. `catalogue.adoc` (SuRF row) says "2009–2016". The last *release* was 2016-05-05, but the last commit was 2017-10-13 (`91fb072`). Suggest "2009–2017 (last release 2016)".
2. `libraries/surf.adoc` "Writes": "joins them with `\n`". This is correct, and the page should add that the result is therefore **not** valid SPARQL 1.1 (operations must be separated by `;`). So T1 is only partial.
3. `index.adoc` Reads row lists SuRF for "one-query eager loading (VALUES + UNION …)". SuRF's `full()` uses a sub-select plus UNION of direct and inverse triples (`plugin/query_reader.py:299-330`), with no VALUES. OldMan is the one that uses VALUES + UNION (`store/sparql.py:154-175, 255-290`).

No other contradictions were found in `libraries/surf.adoc`. Its round 1–3 counts match this report.

### (e) Proposed new features (round 4)

- None specific to SuRF.

## Round 5

### (a) v4 cross-check (77 features)

I confirmed each absence by grep over `surf/` and `plugins/`. The patterns `aggregate|migrat|schema_version|opentelemetry|traceparent|span|redact|did you mean|error_code|testcontainer|on_commit|after_commit|saga|conformsTo|to_sparql|websocket|mcp` hit nothing relevant. The only hits were `AGGREGATE_FUNCTIONS` in the query builder (`query/__init__.py:152`).

| Id | Status | Evidence |
|---|---|---|
| B1 | absent | No model and no aggregate concept (schema-less, `session.py:245`) |
| B2 | absent | — |
| B3 | absent | `load()` fetches one resource's direct and inverse triples (`resource/__init__.py:530-555`); there is no owned closure |
| B4 | absent | `save()` deletes and re-inserts one subject (`plugin/sparql_protocol/writer.py:154-159`); there is no owned subtree and no diff |
| B5 | absent | References come back as live, lazily navigated `Resource`s (`resource/__init__.py:464-520`) |
| B6 | absent | — |
| B7 | absent | No guards (`writer.py:60-125`) |
| B8 | absent | The change set is built inside the writer as SPARUL strings; there is no inspectable value |
| B9 | absent | — |
| B10 | partial | `context` (named graph) per resource and `store.clear(context)` (`resource/__init__.py:193-198`, `writer.py:318`); no GSP and no aggregate notion |
| B11 | absent | — |
| B12 | absent | No hooks (grep `on_commit\ |
| B13 | absent | `remove(inverse=True)` deletes all inbound triples without any boundary rule (`writer.py:168-172`) |
| B14 | absent | — |
| B15 | absent | Lazy reads clear the dirty flag instead of warning (`resource/__init__.py:517`), the inverse of B15 |
| B16 | absent | — |
| PG1 | partial | Query AST (`surf/query/__init__.py`) with a `QueryTranslator` base and SPARQL/SPARUL translators (`query/translator/__init__.py:40`); "TODO: move the translators … in a pluggable architecture" (`translator/sparql.py:44`) |
| PG2 | absent | — |
| PG3 | absent | — |
| PG4 | absent | — |
| EV1 | absent | grep `migrat` returned 0 |
| EV2 | absent | — |
| EV3 | absent | — |
| EV4 | absent | — |
| EV5 | absent | — |
| EV6 | absent | — |
| EV7 | absent | — |
| EV8 | absent | — |
| EV9 | absent | — |
| AZ30 | absent | — |
| AZ31 | absent | — |
| AZ32 | absent | — |
| AZ33 | absent | — |
| AZ34 | absent | — |
| AZ35 | absent | — |
| AZ36 | absent | — |
| G28 | absent | — |
| G29 | absent | — |
| G30 | absent | — |
| G31 | absent | — |
| G32 | absent | — |
| G33 | absent | — |
| G34 | absent | — |
| G35 | absent | — |
| G36 | absent | — |
| T12 | absent | — |
| T13 | absent | The opposite holds. A `Store` without a writer silently gets `NoneWriter`, whose methods all `pass` (`store.py:80-83`, `plugin/writer.py:193-213`), so writes are swallowed, not refused. |
| T14 | partial | `Session` holds several stores; `commit()` updates each dirty resource in its own store (`session.py:94-120, 351-357`). There is no per-store clustering and no atomicity. |
| S20 | absent | — |
| S21 | absent | — |
| S22 | absent | — |
| S23 | absent | Only `size()` / `clear()` / `load_triples` (`store.py:167-235`) |
| X23 | n.a. | No JSON-LD processing |
| X24 | absent | — |
| E10 | absent | — |
| I7 | absent | `uuid_subject` mints opaque IRIs (`util.py:239`) |
| I8 | absent | IRIs are minted on construction (`resource/__init__.py:186-187`) |
| P20 | absent | `commit()` iterates an unordered set (`session.py:356`) |
| U11 | absent | — |
| U12 | absent | — |
| U13 | absent | — |
| D14 | absent | — |
| D15 | absent | Full query text is logged at debug level (`writer.py:192`); no redaction hook |
| D16 | absent | — |
| D17 | partial | `unicode(query)` renders a `surf.query` object to SPARQL (`query/__init__.py:386-391`), and queries are debug-logged. `ResultProxy` has no `to_sparql()`. |
| D18 | absent | Lazy loading is the default (`resource/__init__.py:464-520`), the opposite of D18 |
| D19 | absent | — |
| D20 | absent | — |
| D21 | absent | README examples are not executed (`README.rst:46-65`) |
| D22 | partial | `get_class` accepts a URI, a class name such as `SiocPost` or a `namespace_symbol` string such as `sioc_post` (`session.py:272-287`); no CURIE `repr` |
| D23 | absent | — |
| D24 | absent | — |
| D25 | absent | Values come back in store order (`resource/lazy.py`) |
| D26 | absent | — |
| D27 | absent | — |
| D28 | absent | — |
| D29 | absent | grep `opentelemetry\ |

**v4 counts: 0 present, 5 partial (B10, PG1, T14, D17, D22), 71 absent, 1 n.a. (X23).**

### (b) Page review: `libraries/surf.adoc`

1. **Lines 40, 81, 117 and 141 overstate the eager loading.** They say ``ResultProxy.full()` eager-loads in one query`.
   - `full()` uses the one-query sub-select only when the reader is configured with `use_subqueries=True`. The default is `False` (`plugin/query_reader.py:202-206`).
   - Otherwise it falls back to `_get_by_n_queries`, which is 1 + 2N queries (`:236-239, 270-297`).
   - **Fix:** "one query when `use_subqueries=True` (default off); otherwise 1 + 2N queries". The same caveat applies to my own round-1 R3 and round-2 Q9 "present" marks: the feature is present but opt-in.
2. **Line 80 is a footgun recommended as a borrow.** It says "plus Null Object stores (`NoneReader`, `NoneWriter`) for tests".
   - `NoneWriter` is also the **silent default** when a `Store` gets no writer (`store.py:80-83`), and every method is `pass` (`plugin/writer.py:193-213`), so saves vanish without an error.
   - **Fix:** "borrow only as explicit test fakes; a missing or read-only writer must fail loudly (T7, T13)". Add this to "What to avoid".
3. **The page does not mention aggregates in the query builder.** My round-2 note "no `COUNT` (0 hits)" was a case-sensitive grep miss. The `select()` builder accepts `count`, `min`, `max` and `avg` expressions (`query/__init__.py:120-152`). There is still no count on `ResultProxy`, so Q15 stays partial.
   - **Fix:** no page change is required, but the Feature coverage summary could note "aggregates via raw `select()` only".
4. **Line 12 and line 72 are inconsistent.** They say "GitHub: 44 stars, 7 contributors" and "one maintainer".
   - **Fix:** "one main maintainer (Cosmin Basca), 7 contributors".

No other errors were found. The SPARUL dialect, the dirty-flag bug, the variant table and the round counts all match the evidence.

### (c) Final verdict

**ideas.** No code, because it is Python 2, uses the SPARUL 1.0 dialect and fails DEC-5.

Three things a system architect must remember:
1. A store port with **separate reader and writer** is cheap and useful (replicas, V5, PEP decorators), but a missing writer must **fail loudly, never no-op**.
2. **Dirty state must be per session and per attribute.** SuRF's process-global dirty set, cleared by reads, is the canonical lost-update bug.
3. **One-query eager loading must be the default, not an opt-in flag.** Otherwise N+1 is what developers actually get.

### (d) n.a. (SuRF is a library report, not an angle)

### (e) No new features proposed

The taxonomy covers SuRF's behaviour. The silent `NoneWriter` is already captured by T7 ("no silent no-op commit").
