# triplemodel

- **Repo:** https://github.com/eddiethedean/triplemodel — clone `/home/lps/work/repos/triplemodel` (shallow clone, single squashed commit)
- **Commit analysed:** `bd981af` "Prepare CHANGELOG for 0.12.0 PyPI release" (2026-05-22), version 0.12.0, "Beta"
- **Licence:** MIT (`LICENSE`, `pyproject.toml`)
- **Size:** ~80 source files, 11,216 Python LOC in `src/` (largest: `io/sparql.py` 799, `model.py` 752, `io/import_.py` 743, `io/files.py` 530, `store/graph.py` 421). There are 71 test entries and about 13k test LOC with **785 `test_` functions**. Docs: 15 numbered guides, a cookbook, migration notes for 0.10 and 0.11, API_STABILITY, COMPATIBILITY and ROADMAP (551 lines).
- **GitNexus index:** repo `triplemodel`, 265 files, 4,389 nodes, 8,652 edges, 92 communities, 281 processes. Indexed at HEAD.
- **Author / cadence:** one author ("Odos Matthews"; pyproject says "TripleModel contributors"). Releases ran from 0.1.0 (2026-05-17) to 0.12.0 (2026-05-22), so **12 minor releases in 6 days** (CHANGELOG.md:10–390). That run included a full engine swap from rdflib to pyoxigraph in 0.10 and the removal of SHACL in 0.11. No activity after 2026-05-22 was visible.
- **Docs read:**
  - In the repo: `README.md`, `CHANGELOG.md` (headings), `docs/MIGRATION_0.10.md`, `docs/MIGRATION_0.11.md` (grep), `docs/ROADMAP.md` (grep), `docs/guides/13-sparql-and-endpoints.md`.
  - Published: https://triplemodel.readthedocs.io/. The landing page is stale: it says "SparqlModel … planned but not yet available" and lists no guides beyond the index.

## Summary

triplemodel is a **stateless Pydantic ↔ RDF mapper**. A `TripleModel` subclass declares a nested `class Rdf` (namespace, `type_uri`, `id_field`, prefixes, embed mode, graph mode, `graph_iri`) and maps fields with `rdf_field(predicate)` or `Annotated[..., Predicate(...)]`. On top of that it provides:

- write-mode strategies (add / replace / patch) for syncing an instance into a graph;
- import that ends in Pydantic `model_validate`;
- `rdf:List`, language-tagged literals and a typed-literal registry;
- datasets (named graphs);
- thin SPARQL helpers over a *local* store;
- an experimental OWL/RDFS → stub codegen CLI.

Since 0.10 the graph container is its own `RdfGraph`/`Store` facade over `pyoxigraph.Store`. This facade copies rdflib idioms (`triples()`, `objects()`, `initNs`, `initBindings`) but drops rdflib entirely. Remote SPARQL was removed: `load_sparql` and `open_sparql_graph` raise `NotImplementedError`. The mapping layer is solid and thoroughly tested. It has no session, no identity map and no remote store; those live in sparqlmodel.

## Architecture (GitNexus + code)

- **Clusters (GitNexus):** `Io` (78 symbols, the core import/export cluster), `Sync` (30: write modes and nested cleanup), several `Store` communities (11–12 each), plus test communities. Sub-packages:
  - `config/` — `RdfConfig`, a frozen dataclass derived from the nested `Rdf` class.
  - `fields/` — `rdf_field`, `ref_field`, `BackPopulates`, `ResourceRef`, the resolver.
  - `metadata/` — cardinality and predicate map.
  - `terms/` — `LangString`, `MultiLangString`, `OpaqueLiteral`, `LiteralRegistry`, `python_to_term`/`term_to_python`, `rdf:List` collection.
  - `embed/` — IRI vs bnode strategies.
  - `io/` — export, import, sync, dataset, files, sparql, dispatch, compare, cbd, rdfs, stores.
  - `store/` — `RdfGraph` over pyoxigraph, `Dataset`, formats, `SparqlResult`.
  - `codegen/` — OWL → stubs.
  - `plugins/`, `protocols.py` — `PredicateResolver`, `GraphWriteMode`.
  - `ontology_registry.py` — inverse and subclass hints.
- **Key execution flows (GitNexus processes):**
  - `Sync_to_dataset → sync_to_graph → Bind` (proc_179). `sync_to_graph` dispatches to `Add`/`Replace`/`PatchGraphMode.apply` (`io/sync/__init__.py:37–90`, `io/sync/modes.py:54–216`).
  - `Main/Dump_dataset → model_to_dataset → GraphWriteMode.apply` (proc_27, proc_53; `io/dataset.py:164–191`, `protocols.py:186–197`).
  - `All_from_dataset → … → Term_str / Looks_like_iri` (9 steps) and `Import_value → Term_str`, i.e. the graph → field conversion chain (`io/import_.py:336, 493–623`).
  - `Models_to_dataset → _map_subject / _ref_link_for_field / _direction_to_base`, i.e. export with refs and base direction.
  - `Model_diff → _map_subject/_map_object` (`io/compare.py:73`); `Clear_model_rdf_lists → Iri_ref` (list cleanup on patch).

## Implementation principles (how it actually works)

- **Mapping:** field metadata (predicate, inverse, datatype, lang, transitive, back_populates) lives in Pydantic `FieldInfo` metadata or `json_schema_extra`. `__pydantic_init_subclass__` validates predicates when the class is defined (`model.py:69`). `RdfConfig` is built from the nested `Rdf` class. A subclass's `Rdf` **replaces** the parent's rather than merging (`model.py:47–49`).
- **Identity / IRI minting:** `subject_uri = namespace (+ "/" if needed) + percent-encode(id_field value)`. Values that already start with `http(s)://` or `urn:` pass through unchanged. `IriId` marks a full-IRI id field (`config/rdf_config.py:24–34, 106–130`). The scheme is deterministic and reversible (`id_from_subject_uri`), and there is no UUID default.
- **Export:** `model_to_triples` walks fields and converts values with `python_to_term` and the `LiteralRegistry` (Decimal, UUID, Enum, gYear, …; `terms/registry.py:19–163`). `set[T]` produces repeated objects and `list[T]` produces an `rdf:List` (`io/list_fields.py`). Nested models embed by IRI or bnode via the Strategy objects (`embed/strategies.py:19–134`).
- **Write modes (update strategy):**
  - `add` appends.
  - `replace` clears nested children and inverse links, removes **owned** triples (mapped predicates plus type), then adds.
  - `patch` clears only empty fields, then does per-(subject, predicate) `graph_set_many` (`io/sync/modes.py:54–216`).
  - Foreign predicates are preserved (tests: `test_integration.py:240 test_replace_preserves_unowned_triples_on_subject`).
- **Import:** `graph_to_model` collects owned predicates and converts terms. It can apply `strict_import` / `warn_unmapped_fields`, handle duplicates (`on_duplicate`) and resolve inverse predicates, then ends in `model_cls.model_validate(data)`, so Pydantic validates on load (`io/import_.py:493–623`). `rdf:type` dispatch with optional `rdfs:subClassOf` resolution is in `io/dispatch.py` and `io/rdfs.py`.
- **Named graphs:** `Rdf.graph_iri` or the `graph_iri=` argument places a model's triples into a named-graph context of a `Dataset` (`io/dataset.py:152–245`). There are TriG/N-Quads I/O and `quads_in_context`.
- **"Transactions":** `store_commit` flushes an on-disk store, and `store_rollback` is an explicit **no-op** ("transactions are not exposed on `Store`") (`io/stores.py:121–131`).
- **SPARQL:** local only. `run_sparql`, `ask`, `construct_models`, `select_models` (projection or hydrate) and `apply_update` all run on the local pyoxigraph store with rdflib-style `initNs`/`initBindings` emulated by inlining (`io/sparql.py:110–147, 221–626`). Remote access is gone: `open_sparql_graph` raises (`io/sparql.py:666–679`) and `load_sparql` calls it first, so it always raises (`io/sparql.py:705–731`).
- **Serialisation:** pyoxigraph parsers and serialisers for Turtle, TriG, N-Triples, N-Quads, RDF/XML, N3 and JSON-LD (`store/formats.py:24–68`). **JSON-LD contexts are not supported**: `Rdf.jsonld_context` and `context=` only raise a warning (`store/io_warnings.py:52,77,84–88`), so JSON-LD output is expanded or flat, not compacted.
- **Codegen:** `triplemodel-codegen` parses OWL/RDFS through the local store and emits stub classes from `owl:DatatypeProperty`/`ObjectProperty`, `rdfs:domain` and `rdfs:subClassOf` (`codegen/parse.py`, `codegen/emit.py`). The README labels it "Experimental".

## Patterns catalogue

| Pattern | Where |
|---|---|
| Data Mapper (stateless; mapping metadata on the class, conversion in `io/`) | `io/export.py`, `io/import_.py:493` |
| Active-Record-ish convenience methods on the model (`to_graph`, `from_graph`, `sync_to_graph`, `parse`, `serialize`) | `model.py:94–750` |
| Strategy: graph write modes | `AddGraphMode` / `ReplaceGraphMode` / `PatchGraphMode`, `GRAPH_WRITE_MODES` (`io/sync/modes.py:54–221`) |
| Strategy: embedding | `IriEmbedStrategy` / `BnodeEmbedStrategy` (`embed/strategies.py`) |
| Registry: literal types, vocabularies, ontology hints, predicate resolvers | `terms/registry.py`, `vocab_registry.py`, `ontology_registry.py`, `plugins/__init__.py` |
| Protocols (structural typing) | `PredicateResolver`, `GraphWriteMode` (`protocols.py:121, 186`) |
| Facade / Adapter over pyoxigraph that mimics the rdflib Graph API | `store/graph.py:53` (`RdfGraph`), `store/dataset.py` |
| Unit of Work / Identity Map / Session / Repository | **absent by design** (`docs/ROADMAP.md:42`) |

## Docs vs code

| Claim (source) | Verdict |
|---|---|
| "SPARQL: `ask`, `construct_models`, `select_models`, `load_sparql`, `apply_update`" (README feature table) | Partly true. `load_sparql` **always raises `NotImplementedError`** (`io/sparql.py:666–679, 705`). guides/13 admits this, but the README still advertises it. |
| "Named graphs: `Rdf.graph_iri`, `to_dataset` / `from_dataset`, TriG / N-Quads" (README) | Confirmed (`io/dataset.py`, `config/rdf_config.py:75`). |
| "Store transactions (`commit`/`rollback`) … done" (`ROADMAP.md:115,344`) | Technically present, but `store_rollback` is a no-op (`io/stores.py:128–131`). Not a real transaction capability. |
| JSON-LD file I/O (README) | Confirmed for expanded/flat JSON-LD. **`jsonld_context` is claimed, not functional**: it only warns (`store/io_warnings.py:84`). |
| SHACL (ROADMAP 0.4 exit criteria `ROADMAP.md:220–224`; sparqlmodel ECOSYSTEM) | **Removed in 0.11**, not in the code (`MIGRATION_0.11.md:11–20`). |
| "Codegen: experimental OWL/RDFS → stub models" (README) | Confirmed and minimal (`codegen/emit.py` 124 LOC). There is no LinkML. |
| "Public API frozen from 0.9 until 1.0" (README) | Contradicted by the history: 0.10 swapped the graph type (rdflib → own `Store`) and 0.11 removed SHACL, both breaking and both with migration guides. |
| "We orchestrate pyoxigraph; we do not reimplement parsers, stores, or SPARQL engines" (`ROADMAP.md:20`) | Mostly true for parsers and engine. It does, however, reimplement an rdflib-like Graph facade and the `initBindings` semantics. |
| RTD landing page: "SparqlModel … planned but not yet available" | **Stale**. sparqlmodel 0.13.1 exists and depends on triplemodel. |

## Scores C1–C8

| # | Score | Justification | Evidence |
|---|---|---|---|
| C1 Feature coverage | 2 | A mapper only: mapping, literals, lists, lang tags, named graphs and file I/O are rich. Persistence is absent: no session, identity map, transactions, remote store, query builder or SHACL. Relations exist (nested, `ref_field`, `back_populates`) without loading control. | `docs/ROADMAP.md:42`, `io/stores.py:128` |
| C2 Approach & patterns | 3 | A clean stateless Data Mapper with Strategy write modes and embed strategies, plus resolver and literal registries. Minus points: convenience methods on the model (`to_graph`, `parse`, `serialize`) mix persistence I/O into the domain class, and a subclass `Rdf` replaces rather than inherits. | `io/sync/modes.py`, `model.py:47–49, 94–750` |
| C3 Developer friendliness | 4 | Short happy path (`alice.to_graph()`, `Person.from_graph`), typed (`py.typed`), predicate validation at class definition, 15 numbered guides plus cookbook and examples. The RTD landing page is stale and the API surface is large (about 260 lines of `__init__` exports). | README quick start, `docs/guides/`, `src/triplemodel/__init__.py` |
| C4 Ease of adoption | 4 | Three dependencies (pydantic, pyoxigraph, typing-extensions); in-memory and on-disk pyoxigraph store work out of the box. No remote store at all, and fast breaking churn. | `pyproject.toml` deps, `io/stores.py:68` |
| C5 Reuse of foundations | 3 | Uses pyoxigraph for parsing, serialising, SPARQL and storage, and Pydantic for validation. But it **dropped rdflib** and rebuilt an rdflib-like Graph/Dataset facade (~550 LOC in `store/graph.py` + `store/dataset.py`). That breaks interoperability with the rdflib ecosystem (pySHACL, LinkML runtime, SPARQLWrapper), and no SPARQL client is reused. | `docs/MIGRATION_0.10.md`, `store/graph.py:53` |
| C6 Data-centric & DDD fit | 3 | Stateless mapping keeps persistence separate from sessions, and the owned-predicate write modes fit aggregates. But the domain classes must inherit `TripleModel` and carry `class Rdf` (no plain-object mapping). Codegen is OWL-only and experimental, with no LinkML path. A cosmic-python repository could sit on top. | `model.py:42`, `codegen/` |
| C7 SPARQL 1.1 portability | 1 | Remote SPARQL has been removed; SPARQL works only against the local pyoxigraph store. Nothing is locked to a vendor, but there is also nothing to port. | `io/sparql.py:666–731`, guides/13 |
| C8 Health | 3 | CI on Python 3.10–3.13 with ruff, ty, a min-versions job and a 100% coverage gate; 785 tests; MIT. Against that: a single author, 12 minors in 6 days including an engine swap, no activity since 2026-05-22, and coverage-gap test files (`test_coverage_gaps*.py`). | `.github/workflows/ci.yml`, `pyproject.toml:111,117` |

## Feature inventory

| Id | Status | Evidence |
|---|---|---|
| M1 | present | `TripleModel` + `class Rdf` + `rdf_field` (`model.py:42`) |
| M2 | partial | OWL/RDFS ontology as codegen input only; `OntologyRegistry` hints (`ontology_registry.py:32`). No LinkML, SHACL or JSON-LD context. |
| M3 | partial | `triplemodel-codegen` OWL/RDFS → stubs, experimental (`codegen/emit.py`) |
| M4 | present | `rdf:type` dispatch with `rdfs:subClassOf` resolution (`resolve_subclass`, `io/dispatch.py`, `io/rdfs.py`); `instance_of` for Wikidata-style typing (`rdf_config.py:58–62`) |
| M5 | partial | Pydantic on construct and load (`io/import_.py:623`); `strict_import`; predicate validation at class definition. SHACL removed in 0.11. |
| I1 | present | `namespace` + percent-encoded `id_field`; `IriId` for full IRIs (`rdf_config.py:106–130`) |
| I2 | present | `embed="bnode"` strategy, skolemize/de-skolemize, `blank_node_policy` (`embed/strategies.py:69`, `store/skolem.py`) |
| I3 | absent | Stateless by design |
| R1 | present | `set[T]` multi-valued, `list[T]` → `rdf:List` (`io/list_fields.py`, `terms/collection.py`) |
| R2 | present | Nested models, `ref_field`/`ResourceRef`, `inverse=` on import, `BackPopulates` paired inverses with validation (`fields/back_populates.py:29–388`) |
| R3 | partial | Nested import is eager; `hydrate_refs` / `model_join` helpers resolve references on demand; no depth control |
| R4 | partial | Replace/patch clear stale nested IRI and bnode children (`io/sync/nested_cleanup.py`); no delete cascade (no delete API) |
| L1 | present | XSD mapping, `literal_datatype`, `LiteralRegistry`, `register_literal_type`, `OpaqueLiteral` (`terms/registry.py`) |
| L2 | present | `Lang`, `LangString`, `MultiLangString`, base direction (`terms/lang.py`) |
| P1 | partial | Create/update/read against a local graph (`sync_to_graph`, `from_graph`); no delete-object API |
| P2 | present | add / replace / patch modes (`io/sync/modes.py`) |
| P3 | absent | No session |
| P4 | absent | `store_rollback` is a no-op (`io/stores.py:128`) |
| P5 | absent | None |
| P6 | present | `graph_iri`, `Dataset`, `to_dataset`/`from_dataset`, TriG/N-Quads (`io/dataset.py`) |
| P7 | present | `iter_graph_to_models`, `load_models_streaming`, chunked import, `parse_into_store_graph` (`io/import_.py:655`, `io/files.py`) |
| Q1 | present | `Model.from_graph(graph, uri)` |
| Q2 | absent | No query DSL ("There is no Python query DSL", guides/13) |
| Q3 | present | `construct_models`, `select_models` (projection/hydrate) on a local store (`io/sparql.py:301–600`) |
| Q4 | absent | Only what raw SPARQL provides |
| Q5 | partial | `transitive_objects/subjects`, `Transitive` import (`store/graph.py:330–380`) |
| S1 | present | pyoxigraph `Store`, memory or disk (`io/stores.py:68`) |
| S2 | absent | Removed in 0.10; `load_sparql` raises |
| S3 | absent | None |
| S4 | partial | `open_graph("memory"/"disk")` only; the plugin store registry was removed in 0.10 |
| X1 | partial | JSON-LD parse/serialise via pyoxigraph; contexts not supported (warning) |
| X2 | present | Turtle, TriG, N-Triples, N-Quads, RDF/XML, N3 (`store/formats.py`) |
| X3 | absent | None |
| X4 | partial | Pydantic JSON Schema for free; no TS |
| X5 | partial | `graph_diff` / `model_diff` produce deltas, but there are no events (`io/compare.py`) |
| D1 | present | `py.typed`, `ty` in CI |
| D2 | absent | No async API |
| D3 | absent | No framework integration (left to sparqlmodel) |
| D4 | present | 15 guides, cookbook, examples, migration guides |
| D5 | partial | In-memory store serves as a fake; `graphs_equal` / isomorphism helpers for assertions |
| O1 | partial | `owl:inverseOf` and subclass hints only (`ontology_registry.py`); no restrictions |
| O2 | absent | None |
| A1 | absent | n.a. |

### Proposed new features

| Proposed id | Area | Feature | Seen here |
|---|---|---|---|
| P8 | Persistence | Owned-predicate semantics: replace/patch only the triples the model maps, preserving foreign triples | `remove_owned_triples` (`io/sync/predicate_ops.py`), `test_replace_preserves_unowned_triples_on_subject` |
| M6 | Modelling | Strict / warn-on-unmapped import (closed-world check of incoming data against the model) | `Rdf.strict_import`, `warn_unmapped_fields` (`rdf_config.py:79–82`) |
| M7 | Modelling | Alternative type discrimination (classification property other than `rdf:type`, e.g. `wdt:P31`) | `Rdf.instance_of` (`rdf_config.py:58–62`) |
| I4 | Identity | Skolemisation policy for blank nodes on import/export | `skolemize_export/import`, `store/skolem.py` |
| X6 | Interop | Graph/model diff (isomorphism, triple delta) as a first-class API | `graphs_equal`, `graph_diff`, `model_diff` (`io/compare.py`) |
| Q8 | Query | Concise Bounded Description (CBD) extraction per resource | `cbd_graph` / `cbd_model` (`io/cbd.py`, `store/cbd.py`) |
| L3 | Literals | Pluggable literal-type registry (Python type ↔ datatype converters) | `register_literal_type` (`terms/registry.py:134`) |

## JS-friendliness

Low. It produces Pydantic JSON Schema (`model_json_schema`) for free and can serialise JSON-LD through pyoxigraph, but without `@context` compaction, so the output is not idiomatic JSON for JS clients. It has no HTTP layer and no TS types.

## Reuse verdict for rdf-persistence: **borrow ideas, avoid as a dependency**

Do not adopt or extend it:
- It **abandoned rdflib** (DEC-4 names rdflib as our foundation) in favour of its own pyoxigraph facade, which cuts it off from pySHACL, LinkML runtime and SPARQLWrapper.
- It has no remote SPARQL.
- It is a single-author project with high-velocity breaking churn and is now dormant.
- Its models must inherit `TripleModel`.

**Ideas worth borrowing:**
1. **Write modes as named strategies** (add / replace / patch) with **owned-predicate** semantics: only the mapped predicates and `rdf:type` are cleared, and foreign triples survive. This is the right default for shared graphs.
2. Deterministic IRI minting `namespace + quote(id_field)` with a reversible `id_from_subject_uri`, plus pass-through for full IRIs.
3. `set[T]` = repeated objects vs `list[T]` = `rdf:List`, expressed purely through Python typing.
4. `LangString` / `MultiLangString` value types and a pluggable `LiteralRegistry` for xsd ↔ Python conversion.
5. `BackPopulates` paired inverses validated at class definition, and `OntologyRegistry` hints (`owl:inverseOf`, subclass) applied to models.
6. Named-graph placement per model class (`Rdf.graph_iri`), overridable per call.
7. Strict / warn-on-unmapped import, skolemisation policy, CBD, graph diff.

For our LinkML route, the equivalent mapping metadata should come from LinkML `slot_uri`/`class_uri` annotations rather than a hand-written `class Rdf`.

## Risks / anti-patterns observed

- **Advertised-but-dead API:** `load_sparql` appears in the README feature table and always raises `NotImplementedError` (`io/sparql.py:666–731`).
- **No-op "transactions":** `store_rollback` silently does nothing (`io/stores.py:128–131`), so callers may assume atomicity that does not exist.
- **API stability claim contradicted:** "frozen from 0.9" was followed by breaking changes in 0.10 (graph type) and 0.11 (SHACL removed).
- **Re-implemented rdflib-like facade** (`RdfGraph`, emulated `initBindings` by inlining terms into the query text, `io/sparql.py:110–124`). This duplicates rdflib semantics with subtle differences.
- **Persistence methods on the domain class** (`to_graph`, `parse_url`, `serialize`, `construct_from_sparql` on `TripleModel`): Active-Record leakage into the domain model.
- **Subclass `Rdf` replaces the parent config** (`model.py:47–49`), which is a footgun for inheritance hierarchies.
- **Stale published docs** (RTD landing page) and a mistyped cross-link (`sqarqlmodel` in the README and guides).
- **Burst development** (12 minors in 6 days, 100% coverage gate met partly by "coverage gap" tests): treat both robustness and longevity claims sceptically.

## Round 2 cross-check (taxonomy v1)

Checked against `docs/modules/ROOT/pages/architecture/soa/feature-taxonomy.adoc` (v1). Paths are relative to `src/triplemodel/`. Absences were confirmed by grep over `src/` and by reading the module where the feature would live.

**Counts:** 7 present, 13 partial, 37 absent, 6 n.a. (63 v1 features).

| Id | Status | Evidence |
|---|---|---|
| M6 | absent | Codegen emits Python *source text* (`codegen/emit.py:57 generate_models_from_graph → str`). Grep for `create_model` / dynamic `type(` returns nothing, so no runtime classes are built. |
| M7 | partial | The default `FieldPredicateResolver` needs an explicit predicate (`fields/resolver.py:16–27`), but the pluggable `PredicateResolver` (`protocols.py:121`, `plugins.register_predicate_resolver`) lets a namespace + field-name convention be plugged in. No built-in convention. |
| M8 | absent | `Rdf.jsonld_context` / `context=` are only warned about and never applied (`store/io_warnings.py:52, 77, 84–88`; `config/rdf_config.py:73–74`). |
| M9 | absent | No first-class multi-attribute-per-property mapping. Per-language variants are one `MultiLangString` attribute (`terms/lang.py:69`). Unlike sparqlmodel there is no duplicate-predicate guard, so the behaviour of two fields sharing a predicate is unverified. |
| M10 | absent | No per-RDF-class behaviour binding. |
| M11 | present | `Rdf.strict_import`, `warn_unmapped_fields` (`config/rdf_config.py:79–82`), enforced in `io/import_.py:114 _enforce_subject_predicates`. |
| M12 | present | `Rdf.instance_of` / `instance_type_uri` (`config/rdf_config.py:58–62`), used in the resolver and discovery (`fields/resolver.py:37`, `io/discovery.py`). |
| M13 | absent | SHACL removed in 0.11 (`docs/MIGRATION_0.11.md:11–20`; grep `shacl` over `src/` returns nothing). |
| M14 | partial | Models are generated from an OWL/RDFS ontology (`codegen/parse.py`, `codegen/emit.py`), not from instance data or shapes. |
| M15 | absent | None. |
| I4 | present | `skolemize_export/import`, `blank_node_policy` (`config/rdf_config.py:68–70`), `store/skolem.py`, `io/skolem.py`. |
| R5 | partial | Cardinality is inferred from the annotation (`metadata/cardinality.py`) and checked by Pydantic on load. No relation-level constraint types and no connect-time check. |
| R6 | absent | None. |
| R7 | absent | RDF-star terms are explicitly rejected: "RDF-star triple terms cannot be converted" (`terms/convert.py:151–152`). No reification support. |
| R8 | partial | Graph-level reverse traversal exists (`store/graph.py:191 subjects`, `:356 transitive_subjects`). Model-level inverse navigation needs a declared `inverse=` / `BackPopulates` (`fields/back_populates.py:329–388`). |
| L3 | present | `LiteralRegistry`, `register_literal_type` (`terms/registry.py:19–163`). |
| P8 | present | `remove_owned_triples` in replace mode (`io/sync/modes.py:93–141`, `io/sync/predicate_ops.py`); test `test_integration.py:240`. |
| P9 | partial | `model_diff` / `graph_diff` compute deltas (`io/compare.py:58–127`), but writes do not use them: patch mode clears and resets per (subject, predicate) (`io/sync/modes.py:144–209`). |
| P10 | absent | `graph_set` / `graph_set_many` replace values (`io/ops.py:85–117`). No add/remove-element operators. |
| P11 | partial | `clear_stale_nested_iri_children` / `_bnode_children` drop stale children on replace/patch (`io/sync/nested_cleanup.py`). No shared-reference protection found (grep `referenced\|shared` returns nothing). |
| P12 | partial | Graph placement is set per model class through `Rdf.graph_iri` (`config/rdf_config.py:75`, `io/dataset.py:152–160 resolve_graph_iri`). That is a class-level setting, not a rule engine over types or predicates. |
| P13 | absent | `store_rollback` is a no-op (`io/stores.py:128–131`). |
| P14 | absent | `bulk_load_into_graph` is a raw RDF load (`store/ops.py:49–86`), not a keyed upsert. Already covered by P7. |
| P15 | absent | No concurrency modes. The only lock mention is pyoxigraph's on-disk lock note (`store/graph.py:106`). |
| Q6 | partial | `prepare_model_query` and `initBindings` use pyoxigraph `substitutions` for SELECT/CONSTRUCT (`io/sparql.py:243–270`). The ASK path **inlines terms by regex without escaping quotes** in literal values (`io/sparql.py:96–124`), which is an injection-unsafe path. |
| Q7 | absent | No query builder at all ("There is no Python query DSL", `docs/guides/13-sparql-and-endpoints.md:3`). |
| Q8 | absent | None. |
| Q9 | partial | `construct_models` maps one CONSTRUCT result to many models, so there is no per-object query (`io/sparql.py:301`). There is no include/depth planner. |
| Q10 | absent | `select_models` projection maps each flat row to one flat model (`io/sparql.py:542–600`). No grouping into nested objects. |
| Q11 | partial | `detect_query_form` and form checks only (`io/sparql.py:79–89`, `load_sparql` form guard). |
| Q12 | absent | None. |
| Q13 | absent | pyoxigraph `custom_functions` is not exposed (grep returns nothing). |
| Q14 | absent | None. |
| Q15 | absent | None. |
| Q16 | n.a. | No query builder. |
| Q17 | partial | Subclass-aware dispatch on import (`resolve_subclass`, `io/dispatch.py`, `io/rdfs.py`), but no querying. |
| Q18 | present | `cbd_graph` / `cbd_model` (`io/cbd.py`, `store/cbd.py`, `store/graph.py:393`). |
| S5 | n.a. | No remote store (removed in 0.10). |
| S6 | n.a. | No remote store. |
| S7 | n.a. | No remote store. |
| S8 | absent | Its own `RdfGraph` facade over `pyoxigraph.Store` (`store/graph.py:53`), not the rdflib `Store` or RDF/JS interface. rdflib was removed in 0.10 (`docs/MIGRATION_0.10.md`). |
| X6 | absent | No HTTP layer. |
| X7 | absent | `parse_url` maps a response Content-Type to a parser (`io/files.py:51`). That is client-side format detection, not negotiation. |
| X8 | absent | None. |
| X9 | absent | None. |
| X10 | partial | `select_models` projection hydrates read-only flat models from SELECT rows (`io/sparql.py:438–600`). This is a read-side mapping, but there is no separate read-model concept. |
| X11 | absent | None. |
| X12 | absent | `graph_diff` returns a delta object (`io/compare.py:21–70`), but there is no change-set format or subscriptions. |
| X13 | absent | None. |
| X14 | present | `graphs_equal`, `graph_diff`, `model_diff` (`io/compare.py:46–127`). |
| D6 | absent | `plugins/` registers resolvers and literal types only (`plugins/__init__.py`). No save or delete hooks. |
| D7 | absent | Sync only. |
| D8 | partial | Tests cover in-memory and on-disk pyoxigraph stores (CI job `ci.yml:37` runs `test_stores*.py`, `test_streaming.py`). No triple-store servers. |
| D9 | absent | None. |
| RAD1 | absent | None. |
| RAD2 | n.a. | Out of library scope. |
| O3 | absent | `OntologyRegistry` holds only inverse and subclass hints (`ontology_registry.py:32–202`). |
| O4 | absent | None. |
| O5 | absent | None. |
| O6 | absent | None. |
| O7 | absent | `codegen.ontology_graph` parses a single file (`codegen/parse.py:31–43`); `owl:imports` is not followed (grep `imports` returns nothing). |
| A2 | n.a. | No remote store. |
| A3 | absent | No RDF-level readonly or writeonly field modes. |

**Re-marked v0 features:**

| Id | Status | Evidence |
|---|---|---|
| O2 | absent | No reasoner. |
| X4 | partial | Pydantic JSON Schema only; no `format: uri` for IRI fields was found. No TS types. |
| X5 | partial | Diff deltas exist (`io/compare.py`, i.e. X14), but there are no events or subscriptions (X12 absent). |
| D2 | absent | No async API. |

### Proposed new features (round 2)

| Proposed id | Area | Feature | Seen here |
|---|---|---|---|
| S9 | Stores | Embedded on-disk store lifecycle (open, flush, backup, optimize, destroy, named-graph admin) | `store/ops.py:89–222`, `io/stores.py:68–151` |
| M16 | Modelling | Mapping validation at class-definition time (predicate IRIs, unique predicates, inverse pairs) | `fields/validation.py:39`, `fields/back_populates.py:169–299`; sparqlmodel `model.py:79–96` |

## Round 3

### (a) v2 cross-check

Paths are relative to `src/triplemodel/`. Absences were confirmed by grep over `src/` and by reading the module where the feature would live.

**Counts:** 2 present, 3 partial, 14 absent.

| Id | Status | Evidence |
|---|---|---|
| M16 | absent | One `type_uri` per class (`config/rdf_config.py:58`). Dispatch picks a single class per subject (`io/dispatch.py`). There is no multi-type instance or resolution order. |
| M17 | present | Predicate IRI validation at class definition (`fields/validation.py:39–52`, called from `model.py:69`) and `BackPopulates` pair validation (`fields/back_populates.py:169–299`). There is no unique-predicate check (sparqlmodel adds one). |
| I5 | absent | None. |
| I6 | absent | Pydantic value equality only. Grep finds no identity-based `__eq__`/`__hash__` in `model.py`. |
| P16 | absent | None. |
| P17 | absent | None. |
| P18 | absent | `PredicateResolver` plugins change predicate *resolution* (`protocols.py:121`, `plugins/__init__.py`), and `skolemize_export` rewrites bnodes. There is no general quad-transformation hook on the write path. |
| P19 | absent | `fetch_url` performs an unconditional GET with no ETag or If-Modified-Since (`io/files.py:199–206`). File parsing is unconditional. |
| Q19 | absent | No query DSL; raw SPARQL only. |
| Q20 | absent | None. |
| S9 | absent | None. |
| S10 | partial | `Model.parse_url(url)` does an HTTP GET through urllib and infers the format from extension or Content-Type (`model.py:539`, `io/files.py:51, 199–206`). It is a one-shot load, not a store. It sends no `Accept` header and has no auth hook. |
| S11 | present | `dump_store`, `load_store`, `backup_store`, `optimize_store`, `store_flush`, `list/ensure/clear/remove_named_graph` (`store/ops.py:89–222`); `open_graph`, `destroy_store` (`io/stores.py:68–151`). |
| S12 | absent | None. |
| S13 | partial | `iter_graph_to_models` and `load_models_streaming` stream *models* from graphs and files (`io/import_.py:655`, `io/files.py`). SPARQL result sets are not streamed. |
| S14 | absent | No `logging` in `src/` (grep `getLogger` returns nothing). |
| X15 | partial | Nested children (IRI or bnode embeds) are exported and cleaned together with the parent (`embed/strategies.py`, `io/sync/nested_cleanup.py`). They are not modelled as fragment IRIs of one document. |
| X16 | absent | None. |
| D10 | absent | None. |

### (b) Developer experience deep-dive

**Shortest complete CRUD** (about 15 lines; model from the README quick start, update from `examples/doc/snippets/updating_clear_age.py`):

```python
class Person(TripleModel):
    class Rdf:
        namespace = "http://example.org/people/"
        type_uri = f"{FOAF}Person"
        id_field = "slug"
    slug: str
    name: str = rdf_field(f"{FOAF}name")

alice = Person(slug="alice", name="Alice")
graph = alice.to_graph()                                      # create
loaded = Person.from_graph(graph, alice.subject_uri())        # read
alice.name = "Alice B."; sync_to_graph(alice, graph, mode="replace")  # update
found = Person.construct_from_sparql(graph, "CONSTRUCT {?s ?p ?o} WHERE {?s a foaf:Person; ?p ?o}")  # query (raw SPARQL)
remove_owned_triples(graph, alice.subject_uri(), Person)      # delete (internal helper)
```

- **There is no public delete.** `remove_owned_triples` lives in `io/sync/predicate_ops.py:26` and is not in the top-level `__all__`. Otherwise you write `apply_update` SPARQL or call `graph.remove`.
- **Querying is raw SPARQL only.**

**Concepts to learn (about 10 to start):** `TripleModel`, the nested `class Rdf` (`namespace`, `id_field`, `type_uri`, `prefixes`, `embed`, `graph_mode`, `graph_iri`), `rdf_field`/`Predicate`, `Store`, `to_graph`/`from_graph`, write modes, `set` vs `list`, `LangString`, `ref_field`, `Dataset`. The public surface is large: **128 names in `__all__`** (`__init__.py`).

**Typing / IDE:** `py.typed`, `ty` in CI, and Pydantic instances complete well. The nested `class Rdf` is untyped duck-typed config: typos in its attribute names are not caught by the IDE, because `get_rdf_config` reads them with `getattr` (`config/rdf_config.py:230`).

**Error messages are precise.** Real examples:
- `ValueError: Person.name: rdf_predicate 'rdfs#' resolves to '...rdfs#', which has no local name after '#' or '/'. Use a full property IRI or CURIE (e.g. rdfs:label, not rdfs# alone).` (`fields/validation.py:47–51`).
- `ValueError: Rdf.namespace is required to derive a subject IRI; set it on the model's Rdf class or pass uri= explicitly.` (`config/rdf_config.py:107–111`).
- `UserWarning: Multiple objects (2) for field 'name' (predicate …, subject …); using the first only.` (`io/import_.py:102–112`).

**Docs:** 15 numbered guides, a cookbook, executable doc snippets (tested via `test_doc_examples.py`) and migration guides; good. The RTD landing page is stale, and the README advertises the dead `load_sparql`.

**Surprises / footguns:**
- A subclass `Rdf` *replaces* the parent's config (`model.py:47–49`).
- `list[T]` silently means `rdf:List`.
- Single-valued fields on multi-valued data keep only the first value, with a warning (`on_duplicate="warn"` default).
- `jsonld_context` is accepted but ignored, with a warning.
- `store_rollback` silently does nothing.
- `load_sparql` always raises.
- Breaking churn despite the "API frozen" claim.

**DX score: 3/5.** The mapping part is pleasant. There is no persistence happy path (no delete, no query builder, no remote store), and the API surface is wide.

### (c) Authorization seams (DEC-8)

- **ACL-agnostic by construction, for a trivial reason:** triplemodel never talks to a SPARQL endpoint. It maps models to and from a *local* pyoxigraph graph. Remote access was removed (`io/sparql.py:666–679`), and `fetch_url` is an unauthenticated urllib GET (`io/files.py:199–206`).
- **Where a PEP would go:** in whatever layer moves the local graph to and from the remote store. That is a store adapter in rdf-persistence, or sparqlmodel's `HttpStore`. triplemodel itself offers no hook.
- **GRAPH rewriting:**
  - `Rdf.graph_iri` places triples in named graphs only inside a local `Dataset` (`io/dataset.py:152–245`).
  - If a downstream adapter serialised that dataset as `INSERT DATA { GRAPH <g> {…} }`, a rewriting proxy (sparql-parser) would override the placement. Per DEC-8 / A2, graph placement must therefore stay *advisory*.
  - Nothing in triplemodel breaks, because it never issues remote SPARQL.

### (d) Layer coverage & codegen fit

- **Layers covered:**
  - **L0** modelling and codegen: partial (an experimental OWL/RDFS → stub generator, `codegen/`).
  - **L1** domain and persistence: mapping only (no session or repository).
  - **L2** stores and transactions: partial (embedded pyoxigraph store with admin operations, no transactions, no remote).
  - **L3–L6**: none.
- **Generating models from LinkML: feasible and arguably easier than for sparqlmodel**, because the mapping is static configuration: `class Rdf` from `class_uri`/`id_prefixes`/schema `prefixes`, `rdf_field(slot_uri)`, `ref_field` vs nested model from `inlined`, `set[...]` from multivalued, `LangString` for language slots, and `Rdf.graph_iri` from an annotation.
- **What is missing or awkward:**
  1. Entities must subclass `TripleModel`, so stock `gen-pydantic` output cannot be used directly; a custom template is needed.
  2. Because a subclass `Rdf` replaces the parent's, the generator must emit a full `Rdf` per class, flattening `is_a` config.
  3. `id_field` minting is `namespace + quote(value)`. LinkML `identifier` slots that hold full IRIs or CURIEs fit (pass-through or `IriId`), but `structured_pattern`-based minting would need generator logic.
  4. Enums with `meaning:` IRIs need a custom literal or resource mapping (`LiteralRegistry` can help).
  5. There is no SHACL, so LinkML `gen-shacl` shapes would be validated outside, via pySHACL on an rdflib graph. That requires a format round-trip, because triplemodel graphs are not rdflib graphs.

### (e) C9 and C10

| # | Score | Justification | Evidence |
|---|---|---|---|
| C9 Composability / ecosystem fit | 2 | Strong on RDF syntaxes (Turtle, TriG, N-Quads, RDF/XML, JSON-LD via pyoxigraph), but JSON-LD contexts and framing are unsupported. It dropped rdflib, so there is no direct pySHACL, LinkML-runtime or SPARQLWrapper interop. Its own `RdfGraph` facade is neither rdflib `Store` nor RDF/JS. No SPARQL protocol client. Pydantic gives JSON Schema. | `docs/MIGRATION_0.10.md`, `store/io_warnings.py:84–88`, `store/graph.py:53` |
| C10 Maintainability & operability | 2 | Large surface (128 exports, 11k LOC). The "API frozen" claim was broken by two breaking minors in a week, and the project is dormant with a single maintainer. No logging. On the plus side: a pure library with no services to run, migration guides, a min-versions CI job, and a small dependency set (3). | `__init__.py`, `CHANGELOG.md`, `.github/workflows/ci.yml:45–56`, `pyproject.toml` |

### (f) Proposed new features (round 3)

| Proposed id | Area | Feature | Seen here |
|---|---|---|---|
| G2 | Generation | Inheritance-safe mapping config (per-class RDF config merges with the parent's rather than replacing it, so generated hierarchies stay small) | anti-pattern seen: `Rdf` replaces the parent's (`model.py:47–49`) |
| T1 | Transactions | Honest transaction capability reporting (a store declares whether commit/rollback are real; no silent no-ops) | anti-pattern seen: `store_rollback` no-op (`io/stores.py:128–131`) |

## Round 4

### (a) v3 cross-check

Checked against `feature-taxonomy.adoc` (v3, 102 features). Paths are relative to `src/triplemodel/`. Absences were confirmed by grep over `src/` (`policy`, `permission`, `acl`, `outbox`, `event`, `etag`, `If-Match`, `transaction`, `savepoint`, `logging`, `meaning`, `template` all return no relevant hits) and by reading `io/`, `store/` and `codegen/`.

triplemodel has **no remote store, service or session**, so features that only make sense at a store boundary, in a service or in a UI are marked n.a.

My round-3 proposals map to v3 ids as follows: G2 → **G26**, T1 → **T7**.

| Id | Status | Evidence |
|---|---|---|
| AZ1 | absent | No store port to decorate (`store/graph.py:53` is a concrete facade). |
| AZ2 | absent | No query generation. |
| AZ3 | absent | Raw SPARQL strings only (`io/sparql.py:221`). |
| AZ4 | absent | None. |
| AZ5 | absent | `model_diff` exists (`io/compare.py:73`), but nothing authorizes a changeset. |
| AZ6 | n.a. | No service pipeline. |
| AZ7 | n.a. | No service pipeline. |
| AZ8 | absent | None. |
| AZ9 | absent | None. |
| AZ10 | absent | None. |
| AZ11 | absent | None. |
| AZ12 | absent | None. |
| AZ13 | absent | `graph_iri` is static per class or per call (`config/rdf_config.py:75`, `io/dataset.py:152–160`). No token parameters. |
| AZ14 | absent | None. |
| AZ15 | n.a. | No service. |
| AZ16 | n.a. | No service. |
| AZ17 | absent | None. |
| AZ18 | absent | None. |
| AZ19 | n.a. | No remote store. `fetch_url` is an unauthenticated urllib GET (`io/files.py:199–206`). |
| AZ20 | n.a. | No service or proxy. |
| AZ21 | absent | None. |
| AZ22 | n.a. | No cache or remote store. |
| AZ23 | n.a. | No service. |
| AZ24 | absent | None. |
| AZ25 | absent | None. |
| AZ26 | absent | None. |
| AZ27 | absent | None. |
| AZ28 | absent | None. |
| AZ29 | absent | None. |
| G1 | partial | Static mapping metadata on classes (`class Rdf`, `rdf_field`; `config/rdf_config.py:53–82`, `fields/metadata.py`). Not persistence-free: `TripleModel` adds `to_graph`, `parse_url`, `serialize`, `construct_from_sparql` (`model.py:94–750`). |
| G2 | absent | None. |
| G3 | absent | `codegen/emit.py` builds source with hard-coded f-strings (`emit.py:57–124`). No templates or base-class injection. |
| G4 | absent | `ontology_graph` parses one file (`codegen/parse.py:31–43`). |
| G5 | partial | `IriId`, `ResourceRef` and IRI-like `str` → `NamedNode` (`fields/resource_ref.py`, `terms/iri.py`). No `format: uri` in the schema. |
| G6 | partial | `Lang`, `LangString`, `MultiLangString` round-trip at runtime (`terms/lang.py:42–161`). There is no schema or generation side. |
| G7 | absent | `jsonld_context` is unsupported and only warns (`store/io_warnings.py:84–88`). |
| G8 | absent | None. |
| G9 | absent | None. |
| G10 | absent | None. |
| G11 | absent | None. |
| G12 | absent | None. |
| G13 | absent | None. |
| G14 | absent | `select_models` maps hand-written SELECTs (`io/sparql.py:438`). Nothing is generated. |
| G15 | absent | None. |
| G16 | absent | None. |
| G17 | partial | OWL/RDFS → Python stubs (classes from `rdfs:Class`, fields from `rdfs:domain`, `is_a` from `rdfs:subClassOf`; `codegen/emit.py`). Single file only, no shapes, no schema output. |
| G18 | absent | None. |
| G19 | absent | None. |
| G20 | absent | None. |
| G21 | absent | None. |
| G22 | absent | None. |
| G23 | partial | Typing by `rdf:type` or `Rdf.instance_of` with subclass-aware dispatch (`config/rdf_config.py:58–62`, `io/dispatch.py`). No designator slot. |
| G24 | absent | `Enum` values become *literals* through the registry (`terms/registry.py`), not concept IRIs. |
| G25 | absent | None. |
| G26 | absent | Anti-pattern: a subclass `Rdf` replaces the parent's config (`model.py:47–49`). My round-3 proposal. |
| G27 | absent | None. |
| T1 | n.a. | No remote writes. |
| T2 | absent | None. |
| T3 | n.a. | No remote store. |
| T4 | absent | None. |
| T5 | absent | None. |
| T6 | absent | None. |
| T7 | absent | Anti-pattern: `store_rollback` is a silent no-op and `store_commit` only flushes (`io/stores.py:121–131`). My round-3 proposal. |
| T8 | absent | None. |
| T9 | n.a. | No remote writes. |
| T10 | absent | None. |
| T11 | n.a. | No remote writes. |
| E1 | absent | None. |
| E2 | absent | None. |
| E3 | absent | None. |
| E4 | absent | None. |
| E5 | absent | None. |
| E6 | absent | None. |
| E7 | absent | None. |
| E8 | absent | None. |
| E9 | absent | None. |
| U1 | n.a. | Python mapping library; no JS client. |
| U2 | n.a. | Same. |
| U3 | n.a. | Same. |
| U4 | n.a. | Same. |
| U5 | n.a. | Same. |
| U6 | n.a. | Same. |
| U7 | n.a. | Same. |
| U8 | n.a. | Same. |
| U9 | n.a. | Same. |
| U10 | n.a. | Same. |
| RAD3 | n.a. | No API. |
| RAD4 | n.a. | No API. |
| X17 | n.a. | No API. |
| X18 | n.a. | No API. |
| X19 | n.a. | No API. |
| X20 | n.a. | No API. |
| X21 | n.a. | No API. |
| X22 | absent | No JSON-LD context to bundle (see G7). |
| D11 | n.a. | No store requests. `fetch_url` raises on HTTP ≥ 400 (`io/files.py:204–206`). |
| D12 | absent | `from_graph` raises plain `ValueError` / `TypeError` (`io/import_.py:109, 141, 159, 205`). |
| D13 | present | Errors name the model, field and predicate: `"{Model}.{field}: rdf_predicate … resolves to …"` (`fields/validation.py:47–51`) and `"Multiple objects (n) for field 'x' (predicate …, subject …)"` (`io/import_.py:102–105`). |
| S15 | absent | None. |
| S16 | absent | None. |
| S17 | partial | Replace and patch modes make a subject's owned triples equal to the model (`io/sync/modes.py:93–209`), and `graph_diff` / `model_diff` compute differences (`io/compare.py:58–127`). Writes do not commit *only* the difference. |
| S18 | present | `bulk_load_into_graph` uses `pyoxigraph.Store.bulk_load`, separate from `sync_to_graph` (`store/ops.py:49–86`). |
| S19 | absent | None. |

**Counts (102):** 2 present, 6 partial, 64 absent, 30 n.a.

### (b) Purpose and origin

- **Built for:** a **stateless mapping layer** between Pydantic models and RDF triples. It declares subject IRIs, literals, lists, language tags, nested resources and named graphs once, then moves data between models, local graphs and RDF files (README: "Typed Pydantic models for RDF … no manual quad writes for every property").
- **Who and in what context:**
  - Same single author as sparqlmodel (GitHub `eddiethedean`, "Odos Matthews").
  - Developed 2026-05-17 → 05-22 (12 minor releases) as the foundation sparqlmodel builds on. Roadmap-driven, with `examples/exit_criteria_0N.py` scripts per milestone.
  - It began on rdflib and switched to pyoxigraph-only in 0.10 (for speed: "Rust engine"), then removed SHACL in 0.11.
  - Real-world examples (Nobel, DCAT, Wikidata `instance_of`) show a **data-wrangling / ETL** angle as well as an application one.
  - Desk scan: 0 stars, 1 contributor, about 48 PyPI downloads a month.
- **Design angle:** mapping-first and stateless. "We do not build sessions, query compilers, or cascade `put` semantics" (`docs/ROADMAP.md:20, 42`). Engine-centric (pyoxigraph), file- and local-graph-oriented, model-in-code.
- **Where it fits:** **L1 mapping** (the object ↔ triple layer inside rdf-persistence), partial **L0** (OWL → stubs) and partial **L2** (embedded store administration). As a *dependency* it fits nowhere: it fails DEC-5, conflicts with DEC-4 (it dropped rdflib), and has no remote store. As an *idea source* it fits our mapper internals: owned-predicate write modes, the literal registry, `set` vs `rdf:List`, language strings, per-class graph placement, strict import and skolemisation policy.

### (c) Variant fit

| Variant / approach | Fit | Why |
|---|---|---|
| V1 Portable Python core | ideas only | Its mapping semantics belong inside rdf-persistence's mapper. It cannot be a dependency (rdflib-free, DEC-5 fail, no remote store). |
| V2 semantic.works-compatible | neutral (ideas) | Store-agnostic local mapping. Its `graph_iri` placement must stay advisory behind `sparql-parser`. |
| V3 Fluree | neutral (ideas) | Same as V2; nothing Fluree-specific. |
| V4 GraphDB | neutral (ideas) | Same as V2; nothing GraphDB-specific. |
| V5 Graph-direct reads (CQRS) | partial idea | `construct_models` / `select_models` show how to hydrate models from one CONSTRUCT or SELECT, which is useful for read models. |
| A Runtime mapper | closest fit (ideas) | It is a runtime mapper reading static class config. We would read LinkML `class_uri` / `slot_uri` instead of `class Rdf`. |
| B Generated mapper and routes | enables (template target) | A static `class Rdf` plus `rdf_field` is easy to emit. A generator must flatten inherited config because of G26. |
| C Generic service | blocks | No runtime model materialisation (M6 absent). Codegen emits source text only. |

### (d) Corrections to the integrated docs

1. `catalogue.adoc` lists triplemodel layers as "L1". Its own library page (`libraries/triplemodel.adoc:14`) and this report give "**L0 partial** (OWL/RDFS → stubs) · L1 mapping · **L2 partial** (embedded pyoxigraph store with administration)". The catalogue should match.
2. `index.adoc`, Writes row cites triplemodel for "owned-predicate semantics; per-attribute snapshots; one `DELETE … INSERT … WHERE` …; version guard". triplemodel supports only the **owned-predicate** part. It has no snapshots (P9 is only a separate diff API), no remote writes and no version guard. The citation should be scoped to that first item.
3. `index.adoc` anti-pattern "SPARQL built by string concatenation — … triplemodel (ASK path)": accurate and precise. SELECT and CONSTRUCT use pyoxigraph `substitutions` (`io/sparql.py:243–270`); only the ASK path inlines terms by regex without escaping (`io/sparql.py:96–124`).

### (e) Proposed new features (round 4)

| Proposed id | Area | Feature | Seen here |
|---|---|---|---|
| I7 | Identity | Reversible IRI minting: the id can be recovered from the IRI (`id_from_subject_uri`), and full IRIs pass through unchanged | `config/rdf_config.py:24–34, 120–130` |

## Round 5

### (a) v4 cross-check

Checked against `feature-taxonomy.adoc` (v4, 77 features). Paths are relative to `src/triplemodel/`. Absences were confirmed by grep over `src/` and `tests/` (`version`, `etag`, `outbox`, `event`, `on_commit`, `migration`, `saga`, `cypher`, `assert_type`, `testcontainers`, `opentelemetry`, `logging`, `conformsTo` give no hits) and by reading `io/`, `store/` and `codegen/`.

Features that need a remote store, a session or a service are marked n.a.

| Id | Status | Evidence |
|---|---|---|
| B1 | partial | A nested `TripleModel` (embedded, owned) vs `ref_field` / `ResourceRef` (reference) (`embed/strategies.py`, `fields/resource_ref.py`). There is no root declaration. |
| B2 | absent | No ownership or cycle validation (grep `cycle` returns nothing). |
| B3 | partial | `from_graph` hydrates nested owned models, and `cbd_model` extracts the closure in one call (`io/cbd.py`). This runs on a local graph, not as a store query. |
| B4 | partial | `replace` clears stale nested children and the owned triples, then rewrites (`io/sync/modes.py:93–141`, `io/sync/nested_cleanup.py`). There is no snapshot diff. |
| B5 | partial | `ref_field` / `ResourceRef` hold IRIs, and `hydrate_refs` resolves them explicitly (README "Graph algorithms"). Not a generic `Ref[T]`. |
| B6 | n.a. | No commit. |
| B7 | n.a. | No remote writes. |
| B8 | absent | `graph_diff` returns a `GraphDiff` value (`io/compare.py:21–70`), but it is not a change-set that adapters render. |
| B9 | absent | None. |
| B10 | absent | `graph_iri` is per class or per call (`config/rdf_config.py:75`). There is no graph-per-aggregate strategy. |
| B11 | absent | None. |
| B12 | n.a. | No commit. |
| B13 | absent | No delete API (`remove_owned_triples` is internal, `io/sync/predicate_ops.py:26`). |
| B14 | absent | None. |
| B15 | n.a. | No session. |
| B16 | absent | None. |
| PG1 | absent | No query AST. |
| PG2 | absent | None. |
| PG3 | absent | RDF-star terms are rejected (`terms/convert.py:151–152`). |
| PG4 | absent | None. |
| EV1 | absent | None. |
| EV2 | absent | None. |
| EV3 | absent | None. |
| EV4 | absent | None. |
| EV5 | absent | None. |
| EV6 | absent | None. |
| EV7 | absent | None. |
| EV8 | absent | `bulk_load_into_graph` loads straight into the target graph (`store/ops.py:49–86`). There is no staging graph with ADD/MOVE. |
| EV9 | absent | `backup_store` exists (`store/ops.py:159`), but there is no rehearsal flow. |
| AZ30 | n.a. | A policy-engine feature; triplemodel has no policy engine, store boundary or gateway. |
| AZ31 | n.a. | Same. |
| AZ32 | n.a. | Same. |
| AZ33 | n.a. | Same. |
| AZ34 | n.a. | Same. |
| AZ35 | n.a. | Same. |
| AZ36 | n.a. | Same. |
| G28 | n.a. | It publishes no contracts. |
| G29 | partial | Codegen warns about skipped or degraded constructs, e.g. "Skipping duplicate class name" (`codegen/emit.py:98, 117`). Warnings only, no report. |
| G30 | absent | None. |
| G31 | absent | None. |
| G32 | absent | None. |
| G33 | absent | None. |
| G34 | absent | None. |
| G35 | absent | No query-time field metamodel. |
| G36 | absent | None. |
| T12 | n.a. | No remote store. |
| T13 | partial | `open_graph(..., read_only=True)` opens a pyoxigraph read-only store (`io/stores.py:73–93`). This is store-level, not at a protocol boundary. |
| T14 | n.a. | No session. |
| S20 | absent | None. |
| S21 | absent | None. |
| S22 | absent | SHACL removed in 0.11. |
| S23 | n.a. | No remote adapters. Local admin is covered by S11. |
| X23 | absent | JSON-LD contexts are unsupported (warning only, `store/io_warnings.py:84–88`). `strict_import` is an RDF-level closed-world check (M11), not JSON-LD term strictness. |
| X24 | absent | None. |
| E10 | absent | None. |
| I7 | present | `id_from_subject_uri` and full-IRI pass-through (`config/rdf_config.py:24–34, 120–130`). Seen first here. |
| I8 | absent | None. |
| P20 | n.a. | No unit of work. |
| U11 | n.a. | Python library. |
| U12 | n.a. | Same. |
| U13 | n.a. | Same. |
| D14 | absent | `AddGraphMode` appends without any duplicate warning (`io/sync/modes.py:54–90`). |
| D15 | absent | No query logging. |
| D16 | n.a. | No HTTP contract. |
| D17 | n.a. | No query builder. |
| D18 | absent | None. |
| D19 | partial | `graphs_equal` / `graph_diff` support isomorphism assertions (`io/compare.py:46–70`), and the in-memory `Store` is a fake. There is no pytest plugin or instance builder. |
| D20 | absent | None. |
| D21 | present | `tests/test_doc_examples.py` and `tests/test_readme_examples.py` execute the docs snippets (`examples/doc/snippets/*.py`) and README examples. |
| D22 | partial | CURIE predicates through `Rdf.prefixes` (`namespaces.resolve_predicate`). Subject ids use `namespace + id`, and `repr` and errors show full IRIs. |
| D23 | absent | None. |
| D24 | absent | None. |
| D25 | absent | `set[T]` fields are unordered. |
| D26 | absent | Grep `assert_type` returns nothing. |
| D27 | absent | None. |
| D28 | n.a. | No API. |
| D29 | absent | None. |

**Counts (77):** 2 present, 8 partial, 45 absent, 22 n.a.

### (b) Page review: `docs/modules/ROOT/pages/architecture/soa/libraries/triplemodel.adoc`

1. **Line 53:** "SPARQL runs on the local store only; `initBindings` is emulated (`io/sparql.py:110–147, 221–626`)"
   - **Problem (overstatement):** SELECT and CONSTRUCT pass bindings to pyoxigraph's engine-level `substitutions` (`io/sparql.py:243–270`). Only the ASK path inlines terms into the text (`_inline_init_bindings`, `io/sparql.py:110–124`).
   - **Fix:** "`initBindings` uses pyoxigraph substitutions, except ASK, where terms are inlined into the query text".
2. **Line 98:** "`RdfGraph` and `initBindings` emulated by inlining terms into query text (`io/sparql.py:110–124`)"
   - **Problem:** same overstatement as line 53.
   - **Fix:** keep the injection-risk sentence, but scope "emulated by inlining" to ASK queries.
3. **Line 24:** "switched to pyoxigraph only in 0.10 (*for speed*)"
   - **Problem:** the motive is my inference. `docs/MIGRATION_0.10.md` does not state the reason.
   - **Fix:** drop "(for speed)" or write "(reason not stated)".
4. **Line 102:** "real store transactions (*ROADMAP lists them as done*)"
   - **Problem (overstatement):** `docs/ROADMAP.md:115` says "`store_commit`, `store_rollback` (no-ops on pyoxigraph; documented)". The roadmap is honest. The misleading part is the API naming and the absence of a runtime signal.
   - **Fix:** "`store_rollback` exists as an API but is a documented no-op; callers get no runtime signal".
5. **Line 101:** "*Silent* data loss. Single-valued fields keep the first of several values, *with only a warning*"
   - **Problem:** the sentence contradicts itself. It is not silent; the default `on_duplicate="warn"` emits a `UserWarning` (`io/import_.py:102–112`).
   - **Fix:** "Lossy import by default: single-valued fields keep the first value (warning, configurable to error)".
6. **Line 156:** "I2 blank-node embedding" listed as present
   - **Problem (missing caveat):** the README and the RTD page label nested blank-node embedding *experimental*.
   - **Fix:** add "(experimental)".

### (c) Final verdict

**ideas** — borrow the mapping semantics; never depend on it.

Three things a system architect must remember:
1. It is **only a mapper over a local pyoxigraph graph**. There is no remote SPARQL (`load_sparql` always raises), no session and no real transactions (`store_rollback` is a no-op).
2. It **left rdflib** for its own facade, so it cannot interoperate directly with pySHACL, the LinkML runtime or SPARQLWrapper. This conflicts with DEC-4.
3. Its reusable value is the **mapping semantics**:
   - owned-predicate write modes (add / replace / patch);
   - reversible IRI minting;
   - `set` vs `rdf:List`;
   - `LangString` and the literal registry;
   - strict import;
   - per-class graph placement.

   These should be re-expressed over LinkML `class_uri` / `slot_uri` metadata and inheritance-safe config.

### (d) Not applicable

I am a library analyst, not an angle analyst; Purpose and origin and the variant-fit table were written in round 4.

### (e) New features

None proposed. I7, which came from this report, is now in the taxonomy.
