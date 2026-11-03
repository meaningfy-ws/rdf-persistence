# OldMan (Object Linked Data Mapper)

- **Repo:** clone `/home/lps/work/repos/OldMan` (upstream `github.com/oldm/OldMan`)
- **Commit analysed:** `5661e5a` (2015-03-21, "Update installation.rst"); shallow, `master` only
- **Version:** `0.2` in `setup.py`, Alpha
- **Licence:** BSD (`LICENSE.txt`, `setup.py`)
- **Size:** library `oldman/` = 40 `.py` files, **5,365 LOC**; tests **3,224 LOC, 132 test functions** (nose, `tests/`). Repo total 9,206 LOC.
- **Python:** **Python 2.7 only** (`print` statements in examples, `unicode`, `iteritems`; `.travis.yml` has py3 commented out)
- **Dependencies:** `rdflib`, `rdflib-jsonld`, `SPARQLWrapper`, `validate_email`, `dogpile.cache`, `requests`, `negotiator` (`setup.py`)
- **PyPI:** the name `oldman` is now taken by an **unrelated 2026 MIT package** (v0.8.0, author "Alex"). Do not confuse the two.
- **GitNexus index:** `OldMan`, 112 files, 1,143 symbols, 2,172 edges, 74 clusters, 82 processes
- **Docs read:** https://oldman.readthedocs.io/en/latest/ (index, `core_concepts.html`, `quickstart.html`); in-repo `README.rst`, `docs/foreword.rst`, `docs/core_concepts.rst`, `examples/quickstart*.{py,jsonld,ttl}`. The published "Core concepts" page says "THIS PAGE IS OUT-DATED".

## Summary

OldMan's thesis is **"declare your models using RDF triples and JSON-LD contexts instead of Python classes."** It splits the model into three parts:

- an RDF **schema graph** using the Hydra vocabulary (`hydra:supportedProperty` with `hydra:required`, `readonly`, `writeonly`; `rdfs:subClassOf` for inheritance);
- a **JSON-LD context** that gives property short names, datatypes, languages and containers (`@set`, `@list`, `@language`);
- Python **methods** attached per RDFS class at runtime.

`Model` objects (not classes) are built from these. Resources carry **per-attribute former/current snapshots**, and `save()` emits a minimal **`DELETE DATA ; INSERT DATA`** diff through rdflib `Graph.update` (SPARQL 1.1). It ships a Hydra-aware `HTTPController` with content negotiation (JSON-LD default) and a client/store model split with converters. It is dead: Python 2, single author, 2015, alpha. But it is the closest prior art to the "JSON-LD/JS-friendly middleware" goal.

## Architecture (GitNexus + source)

Clusters: Resource (9/8/8), Model (7/7), Store (7/7), Validation (10/7), Oldman (10/7), plus Tests. Key classes (cypher `MATCH (c:Class)`):

| Layer | Classes | File |
|---|---|---|
| Facade / entry | `ClientResourceManager` | `oldman/resource/manager.py:8` |
| Resources | `Resource` (abstract), `StoreResource` (persistable, picklable), `ClientResource` (end-user, not picklable) | `oldman/resource/resource.py:11, 617, 794` |
| Models | `Model`, `ClientModel`, `ModelManager`, `ClientModelManager`, `ModelRegistry`, `ClassAncestry` | `oldman/model/*.py` |
| Client ↔ store mapping | `ModelConversionManager`, `ModelConverter`, `DirectMappingModelConverter`, `EquivalentModelConverter` | `oldman/model/converter.py` |
| Attributes / dirty state | `OMProperty`, `OMAttribute`, `ObjectOMAttribute`, `Entry` | `oldman/model/property.py`, `attribute.py:16, 399, 459` |
| Schema parsing | `HydraPropertyExtractor`, `JsonLdContextAttributeMdExtractor`, `HydraOperationExtractor`, `HydraSchemaAdapter` | `oldman/parsing/**`, `oldman/schema/hydra.py` |
| Validation | `ValueFormat` family (XSD typed, IRI, email, hexBinary, signed ints) | `oldman/validation/value_format.py` |
| Identity | `IriGenerator`, `PrefixedUUIDIriGenerator`, `BlankNodeIriGenerator`, `IncrementalIriGenerator`, `UUIDFragmentIriGenerator` | `oldman/iri.py` |
| Stores | `DataStore` (abstract), `SPARQLDataStore`, `HttpDataStore` (read-only Linked Data fetch), `DataStoreSelector`, `ResourceCache` (dogpile) | `oldman/store/*.py` |
| HTTP | `HTTPController` (GET/HEAD/POST/PUT/DELETE/OPTIONS; PATCH is a TODO), `HashLessCRUDer` | `oldman/rest/controller.py:12`, `rest/crud.py:10` |

**Execution flows** (GitNexus processes):

- `_filter → _filter_eagerly → _new_resource_object → load_from_graph → update_from_graph` (6–7 steps). This is the load path. GitNexus also lists a `→ save` step, but `load_from_graph` passes `save=False` (`resource.py:641`), so that step is a static over-approximation.
- `Update → _check_iris` / `_alter_bnode_triples` (4 steps): PUT-from-graph with an IRI-safety check.
- `Convert_store_to_client_resources → _extract_types_from_store_resource` (3 steps): client/store model conversion.
- `__init__ → _create_iri_generator` (4 steps): model creation chooses the IRI strategy.
- `Extract → Get_operation_function` (4 steps): Hydra operations are bound to Python callables.

## Implementation principles

- **Model from schema + context:** `data_store.create_model("LocalPerson", ctx_iri, iri_prefix=…, iri_fragment="me", incremental_iri=True)` (`store/datastore.py:241`, `model/manager.py:98`).
  - `HydraPropertyExtractor` reads property constraints from the schema graph with SPARQL (`parsing/schema/property.py:27-80`).
  - `JsonLdContextAttributeMdExtractor` maps each property IRI to context terms through `rdflib_jsonld.Context.find_term` (`parsing/schema/context.py:22-66`).
  - **One property can have several attributes**: `bio:olb` becomes `short_bio_en` (`@language: en`) and `short_bio_fr`, as in `examples/quickstart_context.jsonld`.
  - Inheritance comes from `rdfs:subClassOf` (`ClassAncestry`). Model order sets method and attribute priority.
- **Python behaviour without classes:** `manager.declare_method(fn, name, class_iri)` attaches functions to every descendant model (`resource/manager.py:31-50`). `Resource.__getattr__` resolves attribute, then method, then Hydra operation, across the ordered models (`resource.py:265-294`).
- **Identity:** every resource has an IRI. Blank nodes are **skolemised** (`/.well-known/genid/`) and treated as bnodes on export (`resource.py:898-907`). Pluggable `IriGenerator`s are available: UUID, prefix + incremental counter (stored in the graph as `oldman:nextNumber`, bumped by SPARQL DELETE/INSERT under a *process-local* `Lock`; `store/sparql.py:16-34`), and hash-fragment. There is **no identity map**: `ObjectOMAttribute.get` stores only IRIs and resolves each access through `get_related_resource` → `store.get` (`attribute.py:409-424`). An optional dogpile `ResourceCache` (pickled `StoreResource`s) stands in for it.
- **Dirty tracking (the most valuable idea):** each `OMAttribute` keeps `WeakKeyDictionary[resource → Entry]` (`attribute.py:58`). An `Entry` holds `_former_value` and `current_value`. `has_changed()` and `diff()` compare them, and `receive_storage_ack()` promotes current to former after a successful save (`attribute.py:459-497`). Types are tracked the same way (`_former_types`).
- **Update generation:** `SPARQLDataStore._save_resource_attributes` (`store/sparql.py:337-371`) does the following:
  - for each changed attribute only, serialises the **former** value to N-Triples (`value_to_nt`) and the new one (`to_nt`);
  - adds or removes `rdf:type` lines from the type diff;
  - sends **one request**, `DELETE DATA {…} ; INSERT DATA {…}`, via `data_graph.update()`. That is valid SPARQL 1.1 Update and atomic on stores that execute a request atomically. It works with rdflib in-memory or `SPARQLUpdateStore`.
  - **Caveat:** `DELETE DATA` removes only the values OldMan believes were there, so concurrent edits are neither detected nor merged (no versioning).
- **Cascade / aggregates:** on `save` or `delete`, replaced or removed object values that are **local skolem bnodes** are deleted recursively (`should_delete_resource`, `resource.py:910-916`; `StoreResource.save` at `resource.py:705-755`). This treats embedded bnodes as part of the aggregate (`#TODO: make sure these blank nodes are not referenced somewhere else`).
- **Validation:** happens on set (`check_value`: datatype or `ValueFormat`, container type) and on save (`check_validity`: `hydra:required`; `hydra:readonly` enforced when `is_end_user=True`) (`attribute.py:125-160`). `update(full_dict, allow_new_type, allow_type_removal)` guards against type injection from client JSON (`resource.py:479`).
- **Querying:** `get(id=…)` / `get(**attr)`. `filter(types, hashless_iri, limit, eager, pre_cache_properties, **attr_values)` compiles to `SELECT DISTINCT ?s WHERE {…} LIMIT n`, with equality on attribute values only (`store/sparql.py:209-253`). An eager mode fetches the triples of all matched subjects in one query (`_filter_eagerly`, `:255`). `sparql_filter(query)` maps the first SELECT variable back to Resources (`:67`). There are no order or offset options and no comparison operators. `hashless_iri` is pasted into a `REGEX(...)` string without escaping.
- **Serialisation:** `to_dict()`, `to_json()`, `to_jsonld()` (compact output with the model's context IRI) and `to_rdf(fmt)` (`resource.py:376-447`). The `@set`, `@list` (`rdf:List` read via a list-items query) and `@language` (dict) containers are honoured. `@index` is not supported (`attribute.py:49-63`).
- **Client/store split:** `ClientResourceManager` works on client models. `ClientResource.save()` converts itself to a `StoreResource` through a `ModelConverter` (direct mapping or *equivalent* class/property mapping) and saves that (`resource.py:834-858`, `model/converter.py`). So the vocabulary of the API can differ from the vocabulary of storage. `DataStoreSelector` is designed for multi-store routing but raises `NotImplementedError` for more than one store (`store/selector.py`).
- **HTTP:** `HTTPController` negotiates `application/ld+json` by default, then Turtle and others (`rest/controller.py:38-53`).
  - GET serialises the resource.
  - PUT replaces it (`HashLessCRUDer.update`, from a graph, with an IRI check).
  - POST dispatches to a **Hydra `supportedOperation`** bound to a Python function (`get_operation(HTTP_POST)`, `rest/controller.py:86-121`); there is no generic create.
  - DELETE deletes.
  - PATCH is a TODO.
  - Transactions across a multi-resource PUT: `#TODO: improve it as a transaction` (`rest/crud.py:127`).
- **Named graphs:** writes go to one `data_graph`; reads go to a `union_graph` (a Dataset or ConjunctiveGraph union) (`store/sparql.py:35-40`). There is no per-resource graph.

## Patterns catalogue

| Pattern | Where |
|---|---|
| Metadata Mapping (declarative: RDF schema + JSON-LD context) | `parsing/schema/*`, `model/model.py` |
| Type Object (Model objects instead of classes) | `Model`, `ModelRegistry` |
| Active Record (`resource.save()/delete()`) | `resource.py:349-366, 705-790` |
| Snapshot dirty tracking (former/current per attribute) | `Entry` (`attribute.py:459`) |
| Data Mapper-ish client/store split + converters (anti-corruption layer) | `ClientResource` ↔ `StoreResource`, `model/converter.py` |
| Strategy (IRI generation) | `oldman/iri.py` |
| Strategy / Template Method (stores) | `DataStore._get_by_id/_filter/_save_resource_attributes` |
| Cache-aside (dogpile) | `store/cache.py`, `DataStore.get/save/delete` |
| Mixins at runtime (methods per RDFS class) | `declare_method` |
| Hypermedia API (Hydra operations → callables) | `parsing/operation.py`, `model/operation.py`, `rest/controller.py` |
| Identity Map / Unit of Work | **absent**: save is per resource, immediate |

## Docs vs code

| Claim (source) | Status |
|---|---|
| Models declared with RDF + JSON-LD context, not Python classes (`README.rst`, foreword) | Confirmed (`create_model`, extractors) |
| Validation via `hydra:required/readonly/writeonly`, XSD literals, `foaf:mbox` (foreword) | Confirmed (`HydraPropertyExtractor`, `value_format.py`, `EmailValueFormat`) |
| JSON-LD collections: set, list, language maps (foreword) | Confirmed; `@index` not supported (`attribute.py:62`) |
| "Extensibility to various sorts of data stores" (foreword) | Partial: `DataStore` is abstract; only SPARQL is writable; `HttpDataStore` is read-only; multi-store raises `NotImplementedError` |
| "By default, resources are not cached" (quickstart) | Confirmed (`ResourceCache(None)` no-op) |
| Hydra-driven REST controller | Code exists but is undocumented (no docs page); PATCH and multi-resource transaction are TODOs; 142 TODOs in the package |
| Core concepts (Resource, ClientResourceManager, Model, DataStore) | Page marked "OUT-DATED"; describes `ResourceManager`, while the code has `ClientResourceManager` plus store managers |

## Scores C1–C8

| # | Score | Justification | Evidence |
|---|---|---|---|
| C1 Feature coverage | 3 | CRUD, diff updates, validation, JSON-LD in/out, lang maps, lists, IRI minting, inheritance and inverse (`@reverse`) are present. There is no UoW, identity map, transactions, ordering/pagination, or per-resource named graphs. | `store/sparql.py:337`, `attribute.py:49`, `iri.py` |
| C2 Approach & patterns | 3 | Strong metadata-mapping and snapshot-diff design with a client/store anti-corruption layer. But it is still Active Record, has no session, and the code is TODO-heavy. | `resource.py`, `converter.py` |
| C3 Developer friendliness | 2 | Short JSON-like API (`model.create(name=…)`), good typed errors (`OMAttributeTypeCheckError`, …). But attributes are dynamic (no IDE or type support), the docs are outdated, and the API is alpha. | `exception.py`, `core_concepts.html` |
| C4 Ease of adoption | 1 | Python 2 only, 7 dependencies, a few abandoned (`rdflib-jsonld`, `negotiator`); PyPI name now hijacked by an unrelated project. | `setup.py`, PyPI JSON |
| C5 Reuse of foundations | 4 | rdflib for graphs, SPARQL execution, parsing and skolemisation; `rdflib_jsonld.Context` for term resolution; dogpile for cache; requests for HTTP. It reimplements only small SPARQL string building. | `parsing/schema/context.py:2`, `utils/sparql.py` |
| C6 Data-centric & DDD fit | 3 | Model-first from a schema graph and JSON-LD context. Domain objects still carry `save()`. The client/store split helps a repository layer. | `create_model`, `ClientResource.save` |
| C7 SPARQL 1.1 portability | 4 | `DELETE DATA ; INSERT DATA`, standard SELECT/ASK, through rdflib `Graph.update` (works with `SPARQLUpdateStore`). Uses `REGEX` for hash-less IRIs. No Graph Store Protocol. | `store/sparql.py:362-369` |
| C8 Health | 1 | 132 tests, coverage via coveralls (dead), single author, last commit 2015, alpha, Python 2. Licence clear (BSD). | `git log`, `.travis.yml` |

## JS-friendliness

**High in intent; the best of the prior art reviewed so far.**

- Attribute names are the JSON-LD context terms, so `to_json()` and `to_jsonld()` produce a JS-friendly JSON object that is also valid JSON-LD.
- The schema (Hydra `supportedProperty`, `supportedOperation`) can be **published to hypermedia clients**.
- `HTTPController` does content negotiation with `application/ld+json` as the default and parses POST JSON with the resource's context.
- Missing: OpenAPI, JSON Schema or TS type generation; collections and pagination (`hydra:Collection` only appears in tests and process names).

## Feature inventory

| Id | Status | Evidence |
|---|---|---|
| M1 Host-language classes | absent | By design. Models are objects; methods attached via `declare_method` |
| M2 Schema language | present | RDF/Hydra schema graph + JSON-LD context |
| M3 Codegen | absent | Runtime interpretation only |
| M4 Inheritance → rdf:type | present | `rdfs:subClassOf` → `ClassAncestry`; model priority ordering |
| M5 Validation | present | On set (datatype/format/container), on save (required/readonly) |
| I1 IRI minting | present | 4 `IriGenerator` strategies (`iri.py`) |
| I2 Blank nodes | present | Skolem IRIs; bnode-style export; cascade delete |
| I3 Identity map | absent | Refs re-fetched; optional dogpile cache only |
| R1 Single/multi values | present | `@set` → set, `@list` → list (`rdf:List`), `@language` → dict |
| R2 Object refs / inverse | present | `@type: @id` attributes; `hydra:reversed` / `@reverse` terms |
| R3 Lazy/eager | present | Refs lazy by IRI; `eager=True` + `pre_cache_properties`; `eager_with_reversed_attributes` |
| R4 Cascade | partial | Skolem-bnode objects deleted with owner |
| L1 Typed literals | present | Context `@type: xsd:*` + `ValueFormat` validation |
| L2 Lang strings | present | `@language` per term, or language maps |
| P1 CRUD | present | `new/create/get/filter/save/delete` |
| P2 Update strategy | present | Per-attribute diff → `DELETE DATA ; INSERT DATA` |
| P3 UoW / session flush | absent | Per-resource immediate save |
| P4 Transactions | absent | Single-request atomicity only; TODO in `rest/crud.py:127` |
| P5 Optimistic concurrency | absent | None |
| P6 Named graphs | partial | One write graph + union read graph |
| P7 Bulk load/export | absent | `parse_graph_safely` helper only |
| Q1 Fetch by IRI | present | `get(id=…)` |
| Q2 Query builder | partial | `filter(**attr_equals, types, limit)`; no operators |
| Q3 Raw SPARQL → objects | present | `sparql_filter(query)` |
| Q4 Pagination/order | partial | `limit` only |
| Q5 Property paths | absent | None |
| S1 In-memory | present | rdflib `Graph()` as `data_graph` |
| S2 Remote SPARQL | present | rdflib `SPARQLUpdateStore` |
| S3 Graph Store Protocol | absent | None (`HttpDataStore` = LD dereferencing, read-only) |
| S4 Pluggable store | partial | `DataStore` ABC; selector single-store only |
| X1 JSON-LD | present | `to_jsonld`, POST/PUT parse with context |
| X2 Other formats | present | `to_rdf(fmt)`, negotiation |
| X3 HTTP API | partial | `HTTPController` (Hydra ops, PUT, DELETE; PATCH TODO) |
| X4 Schema export | partial | Hydra schema graph is publishable; no JSON Schema/OpenAPI/TS |
| X5 Change events | absent | None |
| D1 Static typing | absent | None |
| D2 Async | absent | None |
| D3 Framework integration | absent | Framework-agnostic controller (no Flask/Django glue) |
| D4 Docs | partial | Quickstart + example; core concepts outdated |
| D5 Testing support | partial | In-memory rdflib store; `reset_instance_counter` "for test purposes" |
| O1 OWL semantics | absent | RDFS subclass only |
| O2 Reasoner | absent | None |
| A1 ACL hooks | partial | `is_end_user` flag bypasses readonly (noted only) |

### Proposed new features

- **M7 JSON-LD context as the object↔RDF mapping** (term = attribute name; `@type`, `@language`, `@container` drive typing and cardinality).
- **M8 Multiple attributes per property** (for example one attribute per language tag) / attribute ≠ property.
- **M9 Behaviour attached per RDF class at runtime** (`declare_method`), resolved by class-ancestry priority.
- **P8 Snapshot dirty tracking per attribute** (former/current + storage ack) → minimal `DELETE DATA ; INSERT DATA` diff.
- **I4 Skolemisation policy** (`/.well-known/genid/`) to give bnodes IRIs internally and re-hide them on export.
- **X6 Hypermedia contract** (Hydra `supportedProperty`/`supportedOperation`, readonly/writeonly) driving validation and HTTP verbs.
- **X7 Content negotiation** on the HTTP layer (JSON-LD default, Turtle, etc.).
- **X8 API-vocabulary ↔ storage-vocabulary mapping** (client/store model converters).
- **V1 Field-level access modes** (readonly/writeonly enforced for end-users; type-change guard on update from client payloads).

## Reuse verdict for rdf-persistence: **borrow ideas** (strongest idea source for the JSON-LD middleware; no code reuse)

Worth borrowing:

1. **JSON-LD context as the projection layer.** A LinkML schema can *generate* a JSON-LD context (`gen-jsonld-context`), so rdf-persistence can get OldMan's "names come from the context" behaviour from LinkML without hand-written contexts.
2. **Per-attribute former/current snapshot + ack**, giving minimal `DELETE DATA ; INSERT DATA` in one SPARQL 1.1 request. This should be the default update strategy inside a session-scoped Unit of Work (which OldMan lacks).
3. **Skolem IRIs for bnodes**, with cascade deletion of owned skolem nodes. This gives a clean aggregate boundary for embedded objects.
4. **Pluggable IRI minting strategies** (UUID, prefix + counter, hash-fragment). Avoid the counter-in-the-graph approach under concurrency, or put it inside the transaction.
5. **readonly/writeonly/required field semantics** and the **`allow_new_type` guard** for HTTP payloads.
6. **Client/store vocabulary split** as an anti-corruption layer for the middleware.
7. **Hydra or JSON-LD content negotiation** for the HTTP tier.

Avoid:

- models as runtime objects with `__getattr__` (no typing; LinkML-generated pydantic classes are better);
- Active Record `save()`;
- no identity map (lazy refs re-fetched on every access);
- process-local locks for IRI counters;
- unescaped string-built SPARQL;
- dependency on abandoned packages (`rdflib-jsonld` is merged into rdflib 6+; use rdflib's built-in JSON-LD).

## Risks / anti-patterns observed

- **Lost updates:** `DELETE DATA` with stale former values silently leaves the other writer's triples behind (merge-by-accident). There is no version or ETag check, even though the HTTP layer could support ETags.
- **N+1 on object refs:** each access to a reference attribute calls `store.get` unless the dogpile cache is configured.
- **Concurrency:** the `IncrementalIriGenerator` counter is protected by a `threading.Lock` only (`store/sparql.py:16`), so it is unsafe across processes.
- Cascade delete of skolem bnodes does not check other references (TODO at `resource.py:915`).
- `hashless_iri` is interpolated into `REGEX(...)` (`store/sparql.py:229-231`), an injection or escaping bug.
- 142 TODOs, outdated docs, PATCH unimplemented, and multi-store selection stubbed.

## Round 2 cross-check (taxonomy v1)

Checked against `docs/modules/ROOT/pages/architecture/soa/feature-taxonomy.adoc` (v1). Every "absent" verdict was confirmed by a grep of `oldman/` (tests excluded) and by looking where the feature would live. The key greps returned **0 hits** for: hooks (`pre_save|post_save|hook`), `retry|backoff|timeout`, `async|await`, `jsonapi`, full-text, `shacl|sh:`, reification, `xone|exclusive`, `upsert|get_or_create`, `COUNT(`, `register_function`, `label`.

| Id | Status | Evidence |
|---|---|---|
| M6 Runtime model materialisation | present | `Model` objects built at runtime from the schema graph + context (`store/datastore.py:241`, `model/manager.py:98`); no codegen |
| M7 Convention-based predicate derivation | partial | Reverse direction only: unmapped properties get a `prefix_local` name from the QName (`parsing/schema/context.py:44-47`); names normally come from the context |
| M8 JSON-LD context as mapping | present | `JsonLdContextAttributeMdExtractor` (`parsing/schema/context.py:22-66`); `@type`/`@language`/`@container` drive typing and cardinality (`model/attribute.py:49-63`) |
| M9 Attribute ≠ property | present | `OMProperty` has several `OMAttribute`s (`model/property.py`); e.g. `short_bio_en`/`short_bio_fr` → `bio:olb` (`examples/quickstart_context.jsonld`) |
| M10 Behaviour bound to schema classes | present | `declare_method(fn, name, class_iri)` (`resource/manager.py:31-50`), resolved by ancestry priority (`model/ancestry.py`) |
| M11 Strict / warn-on-unmapped import | partial | Setting an unknown attribute raises `AttributeError` (`resource/resource.py:296-315`); unmapped triples on load are silently ignored (`attribute.update_from_graph`, `model/attribute.py:259`) |
| M12 Alternative type discriminator | absent | Types are read from `RDF.type` only (`resource/resource.py:639, 821`) |
| M13 Constraint emission | absent | Hydra schema is consumed, never emitted; 0 `shacl` hits |
| M14 Reverse engineering | absent | — |
| M15 External model-file compat | absent | Only Hydra + JSON-LD context (both standards; no semantic.works format) |
| I4 Skolemisation policy | present | `BlankNodeIriGenerator`, `/.well-known/genid/` (`iri.py:42-50, 106`); `is_blank_node` re-hides them on export (`resource/resource.py:898-907`); `parse_graph_safely` skolemises input (`utils/sparql.py`) |
| R5 Cardinality constraints on relations | partial | `hydra:required` (min 1) and the container type (single vs `@set`/`@list`) are checked on set and save (`model/attribute.py:138-160, 333-400`); no max-N / OneOrMore vocabulary |
| R6 Mutually exclusive relations | absent | 0 hits |
| R7 Relations with own properties | absent | 0 hits |
| R8 Inverse navigation without declaration | partial | Incoming triples are loaded (`store/sparql.py:154-190`) but reachable only through a declared `hydra:reversed` / `@reverse` term (`parsing/schema/property.py:27-60`, `context.py:50-56`) |
| L3 Pluggable literal-type registry | present | `ValueFormatRegistry` with per-property and per-datatype formats (`parsing/schema/attribute.py:85-97`, `validation/value_format.py`) |
| P8 Owned-predicate semantics | present | Only changed mapped attributes are diffed; `delete()` also goes through `_save_resource_attributes` (`store/datastore.py:190-199`), so foreign triples are preserved |
| P9 Change detection / minimal diff | present | `Entry` former/current + `receive_storage_ack` (`model/attribute.py:459-497`) → `DELETE DATA ; INSERT DATA` (`store/sparql.py:337-371`) |
| P10 Collection patch operators | absent | Attributes are set wholesale (`model/attribute.py:313-330`); the diff is computed on the full set |
| P11 Orphan cleanup | partial | Dropped or replaced skolem-bnode objects are deleted (`resource/resource.py:720-748, 910-916`); no shared-reference protection (TODO `:915`) |
| P12 Policy-driven graph placement | absent | Single `data_graph` (`store/sparql.py:35-40`); `DataStoreSelector.select_store` stub (`store/selector.py`) is where it would live |
| P13 Transaction options | absent | TODO `rest/crud.py:127` |
| P14 Bulk upsert / get-or-create | absent | 0 hits |
| P15 Concurrency mode | absent | Only a process-local `Lock` for the IRI counter (`store/sparql.py:32`) |
| Q6 Injection-safe parameter binding | partial | `initBindings` used for `exists` ASK and schema queries (`store/sparql.py:83`, `parsing/schema/property.py:91-114`); `filter`/`get_by_id`/`hashless_iri` still interpolate strings (`store/sparql.py:175, 229-231`) |
| Q7 Typed SPARQL AST builder | absent | String templates (`utils/sparql.py` `build_query_part`) |
| Q8 Derived query methods | absent | — |
| Q9 Eager loading / N+1 avoidance | present | `_filter_eagerly` with `pre_cache_properties` → one VALUES+UNION query (`store/sparql.py:255-290`); `eager_with_reversed_attributes` (`:154-175`) |
| Q10 Grouped result mapping | partial | Eager rows are grouped per subject into resource graphs; `LIMIT` applies to the inner subject query; no offset |
| Q11 Query safety checks on user SPARQL | partial | `sparql_filter` checks only that `"SELECT"` occurs in the query (`store/sparql.py:67-79`) |
| Q12 Full-text search | absent | — |
| Q13 User-defined SPARQL functions | absent | — |
| Q14 Standard external filter language | absent | — |
| Q15 Totals / facets / counts | absent | 0 `COUNT(` hits |
| Q16 Configurable open-world negation | absent | — |
| Q17 Polymorphic query over subclasses | partial | Results hydrate into the most specific leaf models (`model/registry.py:107-170`), but `filter(types=…)` uses exact `?s a <T>` with no `subClassOf*` expansion (`store/sparql.py:219-221`) |
| Q18 CBD extraction | partial | `_get_by_id` = outgoing + incoming triples + `rdf:List` items (`store/sparql.py:154-200`); bnodes are skolemised rather than closed over |
| S5 Read / write split | partial | Writes go to `data_graph`, reads to `union_graph` (`store/sparql.py:35-40`); no endpoint routing (selector single-store) |
| S6 Client-side cache with invalidation | present | dogpile `ResourceCache`; invalidated on save/delete and for related resources of changed object properties (`store/cache.py`, `resource/resource.py:730-740`) |
| S7 HTTP resilience | absent | 0 hits |
| S8 Community-standard store port | partial | Own `DataStore` ABC; the backend is any rdflib `Graph`/`Store` (e.g. `SPARQLUpdateStore`) |
| X6 Generated JSON:API contract | absent | — |
| X7 Content negotiation | present | `negotiator`, default `application/ld+json` (`rest/controller.py:38-64`); 406 `OMNotAcceptableException` |
| X8 Hypermedia contract | present | Hydra `supportedProperty`/`supportedOperation`/`Link` (`parsing/schema/property.py:27`, `parsing/operation.py:29`, `schema/hydra.py`) |
| X9 API ↔ storage vocabulary mapping | present | `ModelConversionManager`, `EquivalentModelConverter` (`model/converter.py:4, 164`) |
| X10 Read models / projections | absent | The client/store split maps vocabularies; it does not separate reads from writes |
| X11 Annotated representations | absent | 0 `label` hits |
| X12 Delta / change-set format | absent | The diff is internal only (`attr.diff`) |
| X13 Request-context propagation | absent | Only an `is_end_user` boolean is passed through `save()` |
| X14 Graph / model diff API | partial | `OMAttribute.diff(resource)` / `Entry.diff()` give a per-attribute former/new diff (`model/attribute.py:179, 488`); no graph-level diff |
| D6 Lifecycle hooks | absent | 0 hits; would live in `StoreResource.save/delete` (`resource/resource.py:705-790`) |
| D7 Sync + async | absent | — |
| D8 Multi-store test matrix | absent | Fuseki/Sesame are commented-out toggles (`tests/default_model.py:18-21`); not a matrix |
| D9 Service template | absent | — |
| RAD1 Zero-code CRUD service | partial | Generic `HTTPController` GET/HEAD/PUT/DELETE for any model; POST needs a Hydra operation; PATCH TODO (`rest/controller.py:55-154`) |
| RAD2 Declarative routing / gateway | n.a. | Out of library scope |
| O3 OWL class-expression API | absent | RDFS + Hydra only |
| O4 Inferred vs asserted views | absent | — |
| O5 Local closed-world closure | absent | — |
| O6 Rule support | absent | — |
| O7 Ontology import resolution | absent | The schema graph is loaded by the caller; no `owl:imports` handling |
| A2 Auth-proxy compatibility (no GRAPH reliance) | present | Writes `DELETE DATA`/`INSERT DATA` against the default graph; no `GRAPH` clauses emitted (graph choice is the rdflib store's) |
| A3 Field-level access modes | present | `hydra:readonly`/`writeonly` with `is_end_user` (`model/attribute.py:67-80, 149-153`); `allow_new_type`/`allow_type_removal` guard (`resource/resource.py:479, 574-602`) |
| *v0 re-marked:* O2 Reasoner (mode dimension) | absent | Only a SPARQL `rdfs:subClassOf*` ancestry query (`model/ancestry.py:54-65`), not a reasoner |
| *v0 re-marked:* X4 Schema export incl. Pydantic / JSON Schema | partial | Hydra schema graph + JSON-LD context are publishable; no Pydantic, JSON Schema or TS |
| *v0 re-marked:* X5 Change notifications (refined by X12) | absent | — |
| *v0 re-marked:* D2 Async (refined by D7) | absent | — |

**Counts (63 v1 features):** 15 present, 14 partial, 33 absent, 1 n.a.

### Proposed new features (round 2)

- **M16 Multi-typed instances:** one resource is bound to several models or classes at once, with a deterministic attribute and method resolution order (`ModelRegistry.find_models_and_types`, `model/registry.py:107-170`). This is distinct from M4 single inheritance.
- **X15 Document-centric grouping:** hash IRIs are grouped under a hash-less document IRI, which is the unit of HTTP retrieval and update (`hashless_iri`, `in_same_document`, `UUIDFragmentIriGenerator`; `resource/resource.py:148, 237`, `iri.py:91-103`).
- **S9 Linked Data dereferencing store:** a read-only store that fetches a resource by HTTP GET on its IRI, with content negotiation and a JSON-LD context taken from the Link header (`HttpDataStore`, `store/http.py:10-56`).

## Round 3

### (a) v2 cross-check

The greps in `oldman/` (tests excluded) for `rename|soft|undo|vector|similar|replicat|backup|stream|timing|elapsed|diagram|graphviz|mtime|Last-Modified|ETag` returned no matches beyond the ones cited below.

| Id | Status | Evidence |
|---|---|---|
| M16 Multi-typed instances, deterministic resolution | present | `ModelRegistry.find_models_and_types` orders the leaf models (`model/registry.py:107-170`). `Resource.__getattr__` resolves attributes, then methods, then operations, across the ordered models (`resource/resource.py:265-294`). |
| M17 Mapping validation at class-definition time | partial | It rejects: readonly plus writeonly on one property (`model/property.py:59`); reserved attribute names (`model/model.py:49`); class names that are not valid HTTP IRIs (`model/manager.py:234`); duplicate datatypes (`OMAlreadyDeclaredDatatypeError`, `model/property.py`); and duplicate model names (`AlreadyAllocatedModelError`). It does not check predicate uniqueness or inverse-pair consistency. |
| I5 IRI / namespace renaming | absent | No hits. `_id` is fixed after creation, except for the temporary IRI swap after a client save (`resource/resource.py:857`). |
| I6 Equality / hash by persistent identity | absent | No `__eq__` or `__hash__` is defined (grep finds only a comment, `resource/resource.py:112`), so Python object identity is used. As a result, `set(lp_model.all())` in the quickstart compares objects, not IRIs. |
| P16 Undoable / soft deletes | absent | `delete()` writes the removal immediately (`store/datastore.py:190-199`) |
| P17 Large-literal offloading | absent | No hits |
| P18 Write-path quad-transformation hooks | partial | `ModelConverter` (direct or equivalent mapping) transforms a client resource into a store resource before every write (`model/converter.py:124-173`, `resource/resource.py:846`). This happens at object level, not as quad hooks. |
| P19 Change-aware reload | absent | No hits for `mtime`, `ETag` or `Last-Modified`. `HttpDataStore` re-fetches every time (`store/http.py:25`). |
| Q19 Regex / substring filters | absent | `REGEX` is used only internally for hash-less IRI matching (`store/sparql.py:232`). `filter(**kw)` supports equality only. |
| Q20 Vector / similarity search | absent | No hits |
| S9 Multi-backend replication | absent | `DataStoreSelector` raises `NotImplementedError` for more than one store (`store/selector.py:12-13`) |
| S10 Linked Data dereferencing store | present | `HttpDataStore`: GET on the IRI with Accept negotiation; the JSON-LD context comes from the `Link` header (`store/http.py:10-56`) |
| S11 Embedded-store administration | absent | Only `reset_instance_counter` ("for test purposes only", `store/sparql.py:118-140`) |
| S12 Batched queries in one call | absent | The per-resource `DELETE DATA ; INSERT DATA` is one request (`store/sparql.py:362-369`). That is a single update, not batching of queries. |
| S13 Streaming large result sets | absent | `_filter_lazily` returns a generator, but it is built over `rdflib` results already fetched in full (`store/sparql.py` `_filter_lazily`) |
| S14 Query observability | partial | `logger.debug("Query: %s")` (`store/sparql.py:366`, filter at `_filter_lazily`). No timing. |
| X15 Document-centric grouping | present | `hashless_iri`, `in_same_document`, `UUIDFragmentIriGenerator`, and controller and CRUD keyed by the hash-less IRI (`resource/resource.py:148, 237`, `iri.py:91-103`, `rest/crud.py:34-104`) |
| X16 Standard API profile conformance | absent | No conformance endpoint. Hydra is used for its vocabulary, not as a profile. |
| D10 Model diagram generation | absent | No hits |

v2 counts: 3 present, 3 partial, 13 absent.

### (b) Developer experience deep-dive

**Shortest complete CRUD example** (from `examples/quickstart.py`, which has 47 non-comment lines). It also needs two external artefacts: `quickstart_context.jsonld` (37 lines) and `quickstart_schema.ttl` (20 lines). The minimal path is about **14 lines of Python plus 57 lines of JSON-LD and Turtle**:

```python
schema_graph = Graph(); parse_graph_safely(schema_graph, schema_url, format="turtle")
data_store = SPARQLDataStore(Graph(), schema_graph=schema_graph)
data_store.create_model("LocalPerson", ctx_iri, iri_prefix="http://localhost/persons/",
                        iri_fragment="me", incremental_iri=True)
client_manager = ClientResourceManager(data_store); client_manager.import_store_models()
lp_model = client_manager.get_model("LocalPerson")
alice = lp_model.create(name="Alice", emails={"alice@example.org"})   # create (validated)
alice = lp_model.get(id=alice.id)                                      # read
alice.name = "Alice A."; alice.save()                                  # update (diff)
alice.delete()                                                         # delete
print alice.to_jsonld()                                                # JSON-LD out
```

**Concepts to learn (10):**
- RDF schema graph with the Hydra vocabulary (`supportedProperty`, `required`, `readonly`)
- JSON-LD context terms and containers
- the difference between a Model and a Resource
- the difference between a store model and a client model, plus `import_store_models`
- DataStore (SPARQL or HTTP)
- IRI generators (prefix, fragment, incremental)
- skolem blank nodes
- hash-less IRIs
- `declare_method`
- the `is_end_user` flag

That is a steep curve for a "simple ORM", but every concept is a W3C or Hydra standard.

**Typing and IDE:** none. Models are runtime objects and attributes resolve through `__getattr__`. In exchange, the attribute names are the JSON keys a JS client sees, which is a single vocabulary across back end and front end.

**Real error messages** (good, typed, and documented in `docs/quickstart.rst:215-227`):
- `oldman.exception.OMRequiredPropertyError: emails`
- `oldman.exception.OMAttributeTypeCheckError: you_wont_email_me is not a valid email (bad format)`

The hierarchy is clean: `OMSchemaError`, `OMEditError` and `OMControllerException` (`exception.py`).

**Docs:** a good quickstart and a DBpedia example. The "Core concepts" page is marked OUT-DATED, the HTTP controller is undocumented, and the package has 142 TODOs.

**Footguns:**
1. There is no identity map and no `__eq__`, so two `get()` calls return unequal objects.
2. Each access to an object attribute triggers a store fetch (N+1) unless a dogpile cache is configured.
3. The IRI counter lock is per process.
4. Leaving out `@container: @set` in the context silently makes a property single-valued, and setting a set on it then raises.
5. `import_store_models()` is easy to forget, and then `get_model` returns nothing useful.
6. `ClientResource.save()` changes `id` after save when a temporary IRI was used (`resource/resource.py:857`).

**DX score: 2/5.** It has the best errors and validation of the two and a standards-aligned JSON vocabulary. But the setup is heavy (three artefacts, two managers), there is no typing, the docs are outdated, and it is Python 2.

### (c) Authorization seams

How close OldMan is to a PEP:
- **Field-level enforcement:** `hydra:readonly` / `hydra:writeonly` are enforced in `OMAttribute._check_local_constraints` when `is_end_user=True` (`model/attribute.py:149-153`, raising `OMReadOnlyAttributeError`). This is already a **field-level enforcement point**, but the principal model is binary (end user versus trusted caller). Writeonly attributes are dropped from `to_dict`/JSON output (`resource/resource.py:395`).
- **Type-change guard:** `allow_new_type` / `allow_type_removal` block type escalation from client payloads (`resource/resource.py:479, 574-602`).
- **Unwired controller errors:** `OMForbiddenOperationException` (403) and `OMRequiredAuthenticationException` (401) are **declared but never raised** (`exception.py:62-74`; grep finds no use). They are seams that were planned but not wired.
- **Client/store split:** this is a natural **anti-corruption layer where a PEP fits**. `ClientResource.save()` always passes through `model_manager.convert_client_resource` and then `StoreResource.save` (`resource/resource.py:834-858`). Reads pass through `ClientResourceManager.get/filter/sparql_filter` (`resource/manager.py:83-122`).

So a PEP would go in one of three places:
1. `HTTPController` methods, which already receive `**kwargs` per request, for coarse operation checks (`rest/controller.py:55-154`).
2. `ClientResourceManager` and the converter, for resource-level and field-level checks on the client vocabulary.
3. `DataStore.get/filter/save/delete` (`store/datastore.py:89-199`), for store-level checks.

`sparql_filter` (raw SELECT) bypasses options 1 and 2, so it needs option 3 or a proxy.

**Behind an authorizing SPARQL proxy** (graph rewriting): **good fit.**
- Writes are plain SPARQL 1.1 `DELETE DATA {…} ; INSERT DATA {…}` against the default graph, with no `GRAPH` clauses. Reads are plain `SELECT` / `ASK` on the endpoint's default dataset (`store/sparql.py`). So a proxy can own graph placement.
- **Caveats:**
  - The `exists()` uniqueness check (`resource/resource.py:113-114`) and the IRI counter (`oldman:nextNumber`, `store/sparql.py:16-34`) go through the proxy. An ACL that hides triples can make `exists()` falsely report a free IRI, and the counter needs write access to a shared bookkeeping triple.
  - `DELETE DATA` of former values assumes the client saw all values. That holds under graph-level ACL, but under triple-level ACL hidden values would simply survive, which is acceptable.

**Verdict:** borrow the declarative field access modes (A3) and the client/store split as PEP placement. Keep the persistence layer ACL-agnostic by emitting GRAPH-free SPARQL 1.1, as OldMan does.

### (d) Layer coverage and codegen fit

| Layer | Coverage |
|---|---|
| L0 modelling and codegen | partial: declarative model input (Hydra schema plus JSON-LD context), interpreted at runtime, no codegen |
| L1 domain and persistence | yes |
| L2 stores and transactions | partial: SPARQL and HTTP stores, cache, no transactions |
| L3 identity and authorization | seams only: readonly/writeonly, `is_end_user`, unwired 401/403 |
| L4 data-management API | partial: `HTTPController` with conneg and Hydra operations |
| L5 JS client and UI | indirect: JSON-LD with stable short keys and a Hydra API description consumable by hypermedia JS clients; no TS |
| L6 change events | none |

**Can LinkML's `gen-jsonld-context` produce OldMan's model input directly?** Partly. This was checked against the local clone `/home/lps/work/repos/linkml/packages/linkml/src/linkml/generators/jsonldcontextgen.py`.

What it emits:
- Prefixes and `@id` per slot.
- `@type: @id` for class ranges, `@type: xsd:*` for typed literals, and `@type: @vocab` for enums (`:377-401`).
- `@container: @set` for multivalued slots, **only with `--fix-multivalue-containers`** (default off; `:403-407, 574-578`). Without that flag OldMan treats every slot as single-valued.

Gaps:
- It emits `@container: @index` for inlined dicts, which **OldMan rejects** (`model/attribute.py:449-453`).
- There is no `@language` per term, so OldMan's attribute-per-language pattern (M9) cannot be expressed in LinkML.
- There is no `@reverse` (grep finds no hits for `@reverse` or `inverse` in the generator).
- There is no `@list` for ordered slots.

The second input, the **Hydra schema graph** (`hydra:supportedProperty`, `required`, `readonly`, `writeonly`, `supportedOperation`), has **no LinkML generator** (no hydra generator in `linkml/generators/`). It would need a small custom generator, either from LinkML (`required` → `hydra:required`; readonly via an annotation) or from the SHACL output (`sh:minCount 1` → `hydra:required`).

**Conclusion:** `gen-jsonld-context --fix-multivalue-containers` plus a roughly 100-line custom Hydra generator would feed an OldMan-style runtime. For rdf-persistence, the better use is the reverse: generate Pydantic classes (typing) **and** the JSON-LD context (wire format) from the same LinkML schema, as two projections of one model.

### (e) C9 and C10

| # | Score | Justification | Evidence |
|---|---|---|---|
| C9 Composability / ecosystem fit | 3 | It speaks JSON-LD contexts, Hydra, SPARQL 1.1 Update (via rdflib `SPARQLUpdateStore`), HTTP content negotiation and Linked Data dereferencing, and it emits GRAPH-free SPARQL that works behind a proxy. Against it: no SHACL, LinkML or GSP; no OIDC; JSON-LD 1.0 through the abandoned `rdflib-jsonld`; and its own `DataStore` port. | `store/sparql.py:362-369`, `rest/controller.py:38-64`, `store/http.py`, `setup.py` |
| C10 Maintainability and operability | 1 | Small code base (5.4k LOC). But it is Python 2, alpha (0.2), has a dead upstream with a single author, 142 TODOs and outdated docs, depends on abandoned packages (`rdflib-jsonld`, `negotiator`), and its PyPI name has been taken by an unrelated project. Debug logging only. | `setup.py`, `.travis.yml`, PyPI JSON |

### (f) Proposed new features (round 3)

- **AZ2 Principal or trust level threaded through write calls into field-level checks:** OldMan's `is_end_user` passes from `save()` into `check_validity`. A generalised version passes a principal or context object into a pluggable PEP.
- **AZ3 Declared authz error contract mapped to HTTP:** typed 401/403 exceptions in the persistence/API boundary (`OMRequiredAuthenticationException`, `OMForbiddenOperationException`), so a PEP's decision surfaces uniformly.
- **G1 Hydra API documentation generated from the model:** `hydra:supportedProperty` with required/readonly/writeonly and `supportedOperation`, generated from LinkML or SHACL. This is the missing generator needed to make OldMan-style hypermedia contracts model-driven.
- **G2 Twin projections from one schema:** typed host classes (Pydantic) and the JSON-LD context (wire mapping) are generated together, and the runtime uses the context as the object↔RDF mapping. This combines M3, M8 and X4.

## Round 4

### (a) v3 cross-check (102 features)

I confirmed each absence by grep over `oldman/` (tests excluded). The patterns `policy|permission|acl|principal|tenant|outbox|notify|websocket|mercure|etag|if-match|cursor|openapi|graphql|frame|typescript|savepoint|idempot|history|batch_size` returned 0 hits.

The Id-mapping appendix maps my round-3 proposals as follows: AZ2 → **AZ21** (present), AZ3 → **AZ24** (partial), G1 → **G11** (absent: Hydra is consumed, not generated), G2 → **G8** (partial: runtime half).

**New evidence this round.** `gh api` shows two **unmerged branches** that my rounds 1–3 (master only) missed: `session` (2015-10 to 2015-12) and `proxy` (2016-01-05, the last push). I read their files through the GitHub API as data, saved under `temp/oldman-session/`. Rows that rely on them are marked `@session`.

| Id | Status | Evidence |
|---|---|---|
| AZ1 | absent | There is no decorator. The seams are `DataStore.get/filter/save/delete` (`store/datastore.py:89-199`). Greps for `policy`, `acl`, `principal` and `permission` found nothing. |
| AZ2 | absent | No policy injection into `_filter` / `_get_by_id` queries (`store/sparql.py:154-290`) |
| AZ3 | absent | Queries are string templates (`utils/sparql.py`); no AST |
| AZ4 | absent | — |
| AZ5 | absent | `save()` diffs per resource (`store/sparql.py:337-371`) but nothing authorizes the delta. The `session` branch tracker (2015-12, unreleased) also has no PEP. |
| AZ6 | absent | `HTTPController` has no hook points (`rest/controller.py:55-154`) |
| AZ7 | absent | — |
| AZ8 | absent | — |
| AZ9 | absent | — |
| AZ10 | absent | — |
| AZ11 | absent | — |
| AZ12 | absent | — |
| AZ13 | absent | Single `data_graph` (`store/sparql.py:35-40`) |
| AZ14 | absent | — |
| AZ15 | absent | — |
| AZ16 | partial | `is_end_user=False` lets a trusted caller bypass readonly checks (`model/attribute.py:149-153`). It is a parameter, with no per-service opt-in. |
| AZ17 | absent | — |
| AZ18 | absent | — |
| AZ19 | partial | `HttpDataStore` accepts an injected `requests` session (`store/http.py:16-18`), but that is per store, not per request |
| AZ20 | absent | — |
| AZ21 | present | `is_end_user` is threaded from `save()` / `update()` into `check_validity` and the readonly checks (`resource/resource.py:349, 479, 705-716`; `model/attribute.py:138-153`) |
| AZ22 | absent | The dogpile `ResourceCache` is shared and not partitioned by principal (`store/cache.py`). This is the anti-pattern behind a proxy. |
| AZ23 | absent | — |
| AZ24 | partial | `OMRequiredAuthenticationException` (401) and `OMForbiddenOperationException` (403) are declared but never raised (`exception.py:62-74`) |
| AZ25 | absent | Write-only attributes are omitted from output, which is hiding, not masking (`resource/resource.py:395`) |
| AZ26 | absent | — |
| AZ27 | absent | — |
| AZ28 | absent | — |
| AZ29 | absent | — |
| G1 | absent | Models are runtime `Model` objects built from the schema graph and context (`model/manager.py:98-160`); nothing is generated |
| G2 | absent | — |
| G3 | absent | — |
| G4 | absent | — |
| G5 | absent | IRI values are validated at runtime (`IRIValueFormat`, `validation/value_format.py:57`), not typed in generated code |
| G6 | partial | `@language` terms and `@container: @language` maps round-trip at runtime (`model/attribute.py:49-63`). Not generated from a schema. |
| G7 | absent | The context is hand-written (`examples/quickstart_context.jsonld`); no frames |
| G8 | partial | Runtime half only: the JSON-LD context is the object↔RDF mapping (`parsing/schema/context.py:22-66`). No typed classes are generated. |
| G9 | absent | — |
| G10 | absent | Generic controller, not generated (`rest/controller.py`) |
| G11 | absent | Hydra is consumed (`parsing/schema/property.py:27`, `parsing/operation.py:29`), never generated |
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
| G23 | absent | The `types` term is mapped to `@type` (rdf:type), not to a designator slot |
| G24 | absent | — |
| G25 | absent | — |
| G26 | present | Each model's attributes are extracted over its class ancestry, bottom-up, so a subclass merges its parents' properties (`model/manager.py:134-157`, `model/ancestry.py`) |
| G27 | absent | — |
| T1 | partial | One `DELETE DATA ; INSERT DATA` request per **resource** (`store/sparql.py:362-369`). The `session` branch `flush()` still sends one request per resource ("TODO: implement it more efficient by grouping the queries", `oldman/storage/store/sparql.py:336-349@session`). |
| T2 | absent | Greps for `version` and `etag` found nothing |
| T3 | absent | — |
| T4 | absent | — |
| T5 | partial | `session` branch only (unreleased): `ResourceTracker.find(iri)` returns tracked, modified objects before `flush()` (`oldman/core/session/tracker.py:79-85@session`) |
| T6 | absent | — |
| T7 | partial | Capability flags: `support_sparql_filtering()` (`store/datastore.py:80`). The `session` branch raises `UnsupportedDataStorageFeatureException` for a missing `exists()` (`oldman/storage/store/store.py:217-226@session`). |
| T8 | absent | — |
| T9 | absent | — |
| T10 | absent | — |
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
| U9 | absent | Hydra operations are advertised per class, not per user (`resource/resource.py:244`) |
| U10 | absent | — |
| RAD3 | absent | — |
| RAD4 | partial | POST is available only where a Hydra `supportedOperation` is declared (`rest/controller.py:86-121`). PUT and DELETE need no declaration (`:123-147`). |
| X17 | absent | One profile (JSON-LD/Hydra) plus rdflib RDF formats through conneg |
| X18 | absent | — |
| X19 | absent | No ETag or If-Match |
| X20 | absent | `limit` only (`store/sparql.py:237`) |
| X21 | absent | PATCH is a TODO (`rest/controller.py:149-154`) |
| X22 | absent | Contexts are referenced by IRI, and `HttpDataStore` fetches them remotely from the `Link` header (`store/http.py:36-41`) |
| D11 | partial | `OMSPARQLParseError` carries the query and the parser error (`store/sparql.py:370-371`). Remote endpoint bodies are not surfaced. |
| D12 | absent | Generic `OMObjectNotFoundError`; no per-model types |
| D13 | partial | Errors name the attribute (`OMRequiredPropertyError(self.name)`, "Attribute %s is not editable by end-users", `model/attribute.py:152, 161`) but not the model |
| S15 | absent | — |
| S16 | absent | — |
| S17 | partial | `update_from_graph` / PUT computes the per-attribute diff against the current resource and writes only that, for a single resource (`resource/resource.py:535-565`, `rest/crud.py:74-137`) |
| S18 | absent | — |
| S19 | absent | — |

**v3 counts: 2 present (AZ21, G26), 12 partial, 88 absent, 0 n.a.**

### Purpose and origin

- **Built for:** exposing and consuming RDF resources *on the Web* as JSON-LD objects. Per the README, an "Object Linked Data Mapper", deliberately not "ORM": resources live on the Web, in stores you may not control.
  - Author: Benjamin Cogrel (the only contributor, 246 commits; GitHub org `oldm`), 2014–2016.
  - Status: master frozen at v0.2 (2015-03). An unreleased `session` branch (late 2015) restructured the code into `core` / `client` / `storage` and added a `Session` with a `ResourceTracker`, a `flush()` and cross-store sessions. A `proxy` branch followed (2016-01). The repo is archived, with 15 stars.
- **Design angle:**
  - Declarative models from W3C standards: a JSON-LD context gives names and types, and a Hydra/RDFS schema gives constraints and operations.
  - Hypermedia-API first (an HTTP controller with content negotiation and Hydra operations).
  - Python methods bolted onto RDF classes.
- **Where it could fit:**
  - It is an idea source for **L0** (the JSON-LD context as mapping, which LinkML can generate), **L1** (snapshot diff, skolem aggregates, IRI strategies), **L3** (field access modes and the trust flag) and **L4** (Hydra/JSON-LD controller).
  - It does not fit as a dependency (Python 2, archived, fails DEC-5). It does not fit L6 at all.

### (c) Variant fit

| Candidate | V1 Portable core | V2 semantic.works | V3 Fluree | V4 GraphDB | V5 CQRS reads | A Runtime mapper | B Generated | C Generic service |
|---|---|---|---|---|---|---|---|---|
| OldMan (ideas only) | supports: JSON-LD + Hydra contract, minimal `DELETE DATA ; INSERT DATA` diff, field access modes | supports: GRAPH-free SPARQL 1.1 writes are proxy-friendly, so `sparql-parser` owns graph placement. Its contract (JSON-LD/Hydra) differs from mu's JSON:API. | supports: JSON-LD context as mapping matches Fluree's JSON-LD-native I/O | neutral | supports: `HttpDataStore` (S10) shows read-only dereferencing; the client/store split separates the API vocabulary from the store | **enables:** the runtime mapping read from metadata (context + schema), which is what A does with LinkML `class_uri`/`slot_uri` | ideas: G8 twin projections, G11 Hydra generation (both missing in OldMan) | **closest prior art:** a generic controller interpreting the schema at runtime (`HTTPController` + Models), but no typing and an unfinished PATCH |

### (d) Corrections to the integrated docs

1. **Unmerged `session` branch missed.** `libraries/oldman.adoc` "At a glance" and the "Notable absences" list, and my own rounds 1–3, analysed master only. Correction: an unmerged `session` branch (2015-10 to 2015-12) adds a `Session` with `get/delete/flush/close`, a `ResourceTracker` and a `CrossStoreSession`. In detail:
   - `find(iri)` is a linear scan, so the identity map is partial: "TODO: use an index" (`core/session/tracker.py:79-85@session`).
   - Flush is ordered by reference dependencies (`storage/session.py:57-76@session`).
   - Temporary IRIs are replaced by permanent ones at flush (`storage/store/sparql.py:351-357@session`).

   Each resource is still written in its own request, so there is no atomic unit-of-work commit. "No UoW, identity map" should read "none on master; partial on the unreleased `session` branch".
2. **Author.** `libraries/oldman.adoc` "Origin and angle" says "One author (oldm)". The author is **Benjamin Cogrel**; `oldm` is the GitHub organisation (`setup.py`, `gh api …/contributors` → `bcogrel 246`). `catalogue.adoc` "2014–2016" is right (last push 2016-01-05, on the `proxy` branch).
3. **Identity row.** `index.adoc` Patterns table lists OldMan for "Identity map keyed by (class, IRI) per session … equality by IRI". On master OldMan has **neither**: there is no `__eq__`/`__hash__` (I6 absent) and no identity map. OldMan qualifies only for pluggable IRI minting and skolem IRIs.
4. **Mapping row.** `index.adoc` Patterns table lists OldMan under "Domain classes stay persistence-free (Data Mapper)". OldMan reads the mapping from metadata (correct), but its resources are **Active Record** (`resource.save()`, `delete()`). It is cited for metadata mapping only, not for Data Mapper.
5. **Reads row.** `index.adoc` Reads row: OldMan should be added as a source of "one-query eager loading (VALUES + UNION)" (`store/sparql.py:154-175, 255-290`). SuRF uses a sub-select + UNION without VALUES.
6. **Catalogue layers.** `catalogue.adoc` OldMan row tags "L1, L4". The evidence supports **L0 (partial), L1, L2 (partial), L3 (seams), L4**, as the library page itself says.

### (e) Proposed new features (round 4)

- **I7 Deferred IRI minting:** objects get temporary IRIs on creation, and the store mints permanent IRIs at flush (OldMan `session` branch, `generate_permanent_id`, `storage/store/sparql.py:351-357@session`).
- **P20 Reference-aware flush ordering:** the unit of work sorts its writes by object-reference dependencies (OldMan `session` branch, `_sort_resources_to_update`, `tracker.get_dependencies`).
- **T12 Cross-store unit of work:** one session spans several stores, flushed per store cluster, with no atomicity across stores (OldMan `session` branch, `CrossStoreSession`, `cluster_by_store_and_status`).

## Round 5

### (a) v4 cross-check (77 features)

I confirmed each absence by grep over `oldman/`. The patterns `aggregate|migrat|schema_version|opentelemetry|traceparent|span|redact|did you mean|error_code|testcontainer|on_commit|after_commit|saga|conformsTo|to_sparql|websocket|mcp` hit only two "aggregate them" TODO comments (`resource/manager.py:110, 120`). Rows marked `@session` rely on the unmerged `session` branch (https://github.com/oldm/OldMan/tree/session).

| Id | Status | Evidence |
|---|---|---|
| B1 | absent | No declared aggregates. Ownership is inferred from the IRI shape (local skolem `/.well-known/genid/`, `resource/resource.py:898-916`). |
| B2 | absent | — |
| B3 | absent | `_get_by_id` loads outgoing and incoming triples plus `rdf:List` items (`store/sparql.py:154-200`), not the owned closure; references stay lazy (`model/attribute.py:409-424`) |
| B4 | partial | `save()` diffs per attribute and deletes dropped skolem children (`resource/resource.py:705-755`); ownership is implicit, and each resource is written separately |
| B5 | absent | Object attributes auto-resolve to live resources (`model/attribute.py:409-424`); `get_lightly` returns IRIs (`:426-434`) but not as a typed reference |
| B6 | absent | — |
| B7 | absent | `DELETE DATA ; INSERT DATA` with no WHERE guard (`store/sparql.py:362-369`) |
| B8 | absent | The diff is rendered to SPARQL inside the store (`store/sparql.py:337-371`); there is no change-set value |
| B9 | absent | — |
| B10 | partial | Document-centric grouping under a hash-less IRI (X15, `resource/resource.py:148, 237`), but everything sits in one `data_graph` (`store/sparql.py:35-40`); no graph per aggregate |
| B11 | absent | — |
| B12 | absent | grep `on_commit\ |
| B13 | partial | Cascade delete of skolem children inside the "boundary" (`resource/resource.py:757-790`); inbound references are not checked (TODO `:915`) |
| B14 | absent | — |
| B15 | absent | — |
| B16 | absent | — |
| PG1 | absent | String templates (`utils/sparql.py`) |
| PG2 | absent | — |
| PG3 | absent | — |
| PG4 | absent | — |
| EV1 | absent | grep `migrat` returned 0 |
| EV2 | absent | — |
| EV3 | absent | — |
| EV4 | absent | — |
| EV5 | partial | `EquivalentModelConverter` maps client resources onto an equivalent store vocabulary at runtime (`model/converter.py:164-173`). It is not versioned migration. |
| EV6 | absent | — |
| EV7 | absent | — |
| EV8 | absent | — |
| EV9 | absent | — |
| AZ30 | absent | — |
| AZ31 | absent | — |
| AZ32 | absent | — |
| AZ33 | absent | `OMResourceNotFoundException` (404) is raised only for genuinely missing resources (`rest/controller.py:70-72`); no authz |
| AZ34 | absent | — |
| AZ35 | absent | — |
| AZ36 | absent | — |
| G28 | absent | — |
| G29 | absent | — |
| G30 | absent | — |
| G31 | absent | — |
| G32 | absent | — |
| G33 | absent | No generated metadata. At runtime an unmapped property only warns and falls back to a QName name (`parsing/schema/context.py:44-47`). |
| G34 | absent | — |
| G35 | absent | — |
| G36 | absent | — |
| T12 | absent | — |
| T13 | absent | — |
| T14 | partial | Unmerged `session` branch only: `CrossStoreSession.flush()` clusters by store, with no cross-store atomicity (`oldman/storage/session.py:57-76@session`); master is single-store (`store/selector.py:12-13`) |
| S20 | absent | — |
| S21 | absent | — |
| S22 | absent | — |
| S23 | absent | — |
| X23 | absent | An unmapped property is downgraded to a QName name with a warning (`parsing/schema/context.py:44-47`). Unmapped triples on load are ignored silently (`model/attribute.py:259-271`). |
| X24 | absent | — |
| E10 | absent | — |
| I7 | absent | — |
| I8 | partial | Unmerged `session` branch only: temporary IRIs are replaced at flush (`generate_permanent_id`, `oldman/storage/store/sparql.py:351-357@session`); master mints on creation (`resource/resource.py:94-125`) |
| P20 | partial | Unmerged `session` branch only: `_sort_resources_to_update` and `tracker.get_dependencies` (`oldman/storage/session.py:57-60@session`, `core/session/tracker.py:114@session`) |
| U11 | absent | — |
| U12 | absent | — |
| U13 | absent | — |
| D14 | absent | — |
| D15 | absent | — |
| D16 | absent | — |
| D17 | partial | Queries are debug-logged (`store/sparql.py:366`); no `to_sparql()` API |
| D18 | partial | `get_lightly` returns IRIs without fetching (`model/attribute.py:426-434`), but the default `get` loads lazily (`:409-424`) |
| D19 | absent | Tests use an in-memory rdflib graph (`tests/default_model.py:27`), but there is no shipped plugin or fixture kit |
| D20 | absent | Fuseki and Sesame toggles are commented out (`tests/default_model.py:18-21`) |
| D21 | absent | — |
| D22 | absent | — |
| D23 | absent | — |
| D24 | absent | — |
| D25 | absent | `@set` values are Python sets (unordered); only `@list` keeps order (`model/attribute.py:49-51`) |
| D26 | absent | — |
| D27 | absent | — |
| D28 | absent | — |
| D29 | absent | — |

**v4 counts: 0 present, 9 partial (B4, B10, B13, EV5, T14, I8, P20, D17, D18; three of these only on the `session` branch), 68 absent.**

### (b) Page review: `libraries/oldman.adoc`

1. **Line 2 is out of date.** It says "dead since 2015". The last push was 2016-01-05, on the `proxy` branch (line 12 says so).
   - **Fix:** "dead since early 2016 (master frozen 2015)".
2. **Line 57 conflates two queries.** It says "Eager mode fetches all matched subjects in one query built from `VALUES` + `UNION` (`_filter_eagerly`, `store/sparql.py:154-175, 255-290`)".
   - Lines 154-175 are `_get_by_id`. It uses VALUES + UNION to fetch one resource's **outgoing and incoming** triples.
   - `_filter_eagerly` (255-290) uses VALUES + UNION **only when `pre_cache_properties` is given**. Otherwise it is a plain join of `?s ?p ?o` with the sub-query.
   - **Fix:** "`_get_by_id` uses VALUES + UNION for outgoing and incoming triples (154-175); `_filter_eagerly` loads all matched subjects in one query and adds VALUES + UNION for `pre_cache_properties` (255-290)".
3. **Lines 48 and 97 leave out a caveat.** They say "sends *one* `DELETE DATA {…} ; INSERT DATA {…}` request" and "producing one minimal … request".
   - The single request is **per resource**. Saving several resources, including cascaded skolem children, sends several requests with no atomicity across them (`resource/resource.py:743-748`). The `session` branch flush still sends one request per resource.
   - **Fix:** add "per resource".
4. **Line 98 overstates the boundary.** It says "Skolem IRIs … with cascade deletion of owned skolem nodes: a clean aggregate boundary for embedded objects".
   - Ownership is **inferred from the IRI shape** (`/.well-known/genid/` on `localhost`, `resource.py:898-907`), not declared (B1 absent), and shared references are not protected (line 110 says so).
   - **Fix:** "an implicit boundary; declare ownership in the model instead (B1, B13)".
5. **Line 96 needs a qualifier.** It says "LinkML `gen-jsonld-context` can generate it".
   - **Fix:** "can *partly* generate it (needs `--fix-multivalue-containers`; no `@language`, `@reverse` or `@list`; see Code-generation fit)".
6. **Line 82 (C2) and line 88 (C8) need scoping.** Line 82 says "no session" and line 88 says "last commit 2015".
   - **Fix:** "no session on master (partial on the unreleased `session` branch)" and "master last commit 2015; branches to 2016-01".
7. **Lines 73 and 184 cite a temporary path.** They say "Evidence …: `temp/oldman-session/`".
   - `temp/` is git-ignored and not durable.
   - **Fix:** cite https://github.com/oldm/OldMan/tree/session (and `/tree/proxy`) instead.
8. **Line 180 is out of date.** It says "Round-4 proposals from the `session` branch (no id yet)". They now have v4 ids.
   - **Fix:** "I8 deferred IRI minting, P20 reference-aware flush ordering, T14 cross-store unit of work".

I agree with the editor keeping L2 as partial and scoping "no identity map" to master (line 45). Both match the evidence.

### (c) Final verdict

**ideas.** It is the strongest idea source for the JSON-LD/Hydra middleware. There is no code to reuse: Python 2, archived, fails DEC-5.

Three things a system architect must remember:
1. **The JSON-LD context can serve as the object↔RDF mapping**, but LinkML's `gen-jsonld-context` covers it only partly. Plan to generate Pydantic classes and the context as twin projections (G8), plus a Hydra generator (G11), rather than hand-writing contexts.
2. **Per-attribute snapshot diffs give minimal SPARQL 1.1 writes**, but only inside a real unit of work that sends **one request for the whole change set with a version guard** (B7, T1, T2). OldMan's per-resource requests and its missing guards lose updates.
3. **Authorization seams belong at three explicit points**: the API controller, the client/store mapping, and the store port. Field access modes (readonly/writeonly) and a type-change guard should be declarative in the model. OldMan's GRAPH-free SPARQL is what keeps it proxy-compatible.

### (d) n.a. (library report)

### (e) No new features proposed
