# Angle: L0 modelling & code generation (round 3)

Change: `soa-python-rdf-orm` · Angle slug: `angle-codegen` · Analyst date: 2026-11-03
Chain under study: UML (Enterprise Architect, SEMIC conventions) → model2owl (XSLT) → OWL / SHACL /
JSON-LD context → LinkML → generated Python domain + persistence + JSON-LD context + SHACL + TS types
+ JSON Schema / OpenAPI.

Deep dives (clone + `gitnexus analyze` + code): **linkml/linkml** (monorepo, now includes
`linkml_runtime`), **OP-TED/model2owl** (+ the `feature/linkml` branch of the meaningfy-ws fork),
**linkml/schema-automator**, **JPEWdev/shacl2code**. Everything else is desk-scanned (GitHub API,
PyPI/npm stats, README / directory listing).

| Clone | Commit | Files | GitNexus index |
|---|---|---|---|
| /home/lps/work/repos/linkml | d48b197 (2026-10-30) | 2 077 | 21 237 nodes, 41 906 edges, 539 clusters, 300 flows |
| /home/lps/work/repos/model2owl | 351ee02 (2026-03-11) | 1 410 | 1 568 nodes, 17 clusters |
| /home/lps/work/repos/schema-automator | 0cf0e88 (2026-10-27) | 438 | 2 951 nodes, 199 flows |
| /home/lps/work/repos/shacl2code | ba438c3 (2026-10-06) | 147 | 867 nodes, 22 flows |

## 1. Landscape (desk scan)

Stats fetched 2026-11-03 (`gh api`, pypistats.org last month, npm last month). DEC-5 = >200 stars AND
a commit in the last 12 months; packages of a qualifying org / monorepo inherit.

| Candidate | Stars | Last push | Licence | Lang | Downloads/mo | DEC-5 | Layers | Role in chain |
|---|---|---|---|---|---|---|---|---|
| linkml/linkml (gen-pydantic, gen-python, gen-sqla, gen-jsonld-context, gen-shacl, gen-owl, gen-typescript, gen-json-schema, gen-openapi, gen-graphql, gen-shex, gen-sparql, gen-yarrrml, gen-erdiagram/doc …) | 680 | 2026-11-02 | Apache-2.0 | Python | 477 k (linkml) | **pass** | L0 (L1 via runtime) | schema SSoT + generators |
| linkml-runtime (rdflib loader/dumper, SchemaView) — **repo archived, code moved into linkml monorepo `packages/linkml_runtime`** | 44 (archived) | 2025-12 | CC0 | Python | 550 k | **pass (inherits monorepo)** | L0/L1 | RDF ↔ object round-trip |
| linkml/schema-automator (OWL/RDFS/**SHACL**/JSON Schema/SQL → LinkML) | 68 | 2026-10-27 | BSD-3 | Python | 1.8 k | pass (inherits linkml org) | L0 | reverse import |
| linkml/linkml-store (DuckDB/Mongo/Neo4j/Solr/… + generic FastAPI) | 27 | 2026-10-09 | MIT | Python | 10 k | pass (inherits org); README says API unstable | L1/L4 | generic schema-driven store + API |
| linkml/linkml-map (schema↔schema transforms) | 50 | 2026-11-02 | NOASSERTION | Python | – | pass (inherits org) | L0 | model-to-model mapping |
| linkml/linkml-dataops | 6 | 2024-02 | none | Python | – | fail (stale) | L1 | change/patch ops — ideas |
| linkml/linkml-project-cookiecutter | 26 (archived) | 2025-10 | CC0 | – | – | fail (archived) | L0 | project scaffold |
| OP-TED/model2owl (upstream; meaningfy-ws/model2owl is a fork, 1 star) | 49 | 2026-03-27 | EUPL-1.2 | XSLT | – | **fail** (<200) — but Meaningfy/OP-TED own it, so DEC-5 is moot: in-house asset | L0 | UML → OWL, SHACL, JSON-LD ctx, glossary, conventions report |
| JPEWdev/shacl2code (SPDX 3 bindings) | 8 | 2026-10-23 | MIT | Python (gen) → Py/C++/Go/Rust/JSON Schema | 1.7 k | fail | L0/L1 | SHACL → standalone bindings — ideas |
| o-development/ldo (`@ldo/cli`: ShEx → TS types + JSON-LD context; `jsonld-dataset-proxy`) | 73 | 2026-10-31 | MIT | TS | 0.6 k (@ldo/ldo) | fail | L0/L5 | shape → TS objects over RDF/JS — ideas |
| karelklima/ldkit (TS schema → SPARQL; see ldkit.md) | 83 | 2026-10-13 | MIT | TS | 44 k | fail | L5 | TS-side mapper — ideas |
| minorg/shaclmate (SHACL → TS/Python code) | 9 | 2026-11-03 | Apache-2.0 | TS | – | fail | L0 | ideas |
| jeswr/on2ts (OWL → TS) | 11 (archived) | 2025-03 | MIT | JS | – | fail | L0 | dead |
| faust0o/shex-codegen | 18 (archived) | 2024-03 | MIT | TS | – | fail | L0 | dead |
| Health-RI/SeMPyRO (hand-written Pydantic DCAT-AP v3 + RDF serialisation) | 19 | 2026-10-26 | Apache-2.0 | Python | 0.5 k | fail | L1 | precedent: Pydantic + IRI metadata for a SEMIC AP |
| Omegaice/pydantic-rdf (see pydantic-rdf.md) | 23 | 2025-05 | MIT | Python | 25 | fail | L1 | ideas |
| LA3D/pydantic_jsonld, Moritz72/pydantic-jsonld | 3 / 0 | 2025-07 / 2026-05 | MIT | Python | – | fail | L1 | toy Pydantic ↔ JSON-LD bridges |
| edwardanderson/rdfs_pydantic, jupyter-naas/onto2py | 1 / 0 | 2026 | MIT | Python | – | fail | L0 | toy ontology → Pydantic |
| datamodel-code-generator (OpenAPI/JSON Schema → Pydantic v2) | 4 047 | 2026-11-03 | MIT | Python | 13.6 M | **pass** | L0 | JSON Schema/OpenAPI → Pydantic |
| koxudaxi/fastapi-code-generator (OpenAPI → FastAPI app skeleton) | 1 408 | 2026-11-02 | MIT | Python | 58 k | **pass** | L0/L4 | OpenAPI → routes |
| ULB-Darmstadt/shacl-form (SHACL → HTML form web component) | 93 | 2026-10-22 | MIT | TS | 15 k | fail | L5 | shape-driven UI — ideas |
| sparna-git/Sparnatural (SHACL-configured SPARQL query builder UI) | 315 | 2026-11-02 | LGPL-3.0 | TS | 1.3 k | **pass** | L5 | shape-driven query UI |
| emmo-repo/EMMOntoPy (Owlready2-based) | 71 | 2026-10-28 | BSD-3 | Python | – | fail | L0 | ontology tooling |
| RDFLib/rdflib, RDFLib/pySHACL, digitalbazaar/pyld | 2 545 / 367 / 688 | 2026-10/11 | BSD/Apache/BSD | Python | – | pass | L1 foundations | runtime targets of generated code |

Searched and **nothing found** (GitHub search, 2026-11-03): a LinkML/SHACL → FastAPI route or
repository generator ("linkml fastapi", "linkml api": only 0-star personal repos
AvinashBhura/linkml-platform, noelmcloughlin/linkmo); an OWL → Pydantic generator above toy level;
a maintained SHACL → TS generator above 100 stars.

## 2. Deep dive — LinkML (linkml/linkml monorepo, incl. linkml_runtime)

- Repo `linkml/linkml` @ d48b197, Apache-2.0; generators in
  `packages/linkml/src/linkml/generators/` (38 generators; `pydanticgen/`, `sqlalchemy/`, `shacl/`,
  `rustgen/`, `golanggen/`, `javagen/` are packages). `linkml_runtime` now lives in
  `packages/linkml_runtime/` (the old repo is archived) — one release train for schema and runtime.
- Docs read: in-repo `docs/generators/*.rst` (typescript, pydantic, openapi, graphql),
  `docs/schemas/type-designators.md`; generator URLs referenced in code
  (https://linkml.io/linkml/generators/openapi.html).
- GitNexus: `gitnexus context -r linkml RDFLibLoader` → class
  `packages/linkml_runtime/src/linkml_runtime/loaders/rdflib_loader.py:40-388`, `Loader` interface
  with 5 implementations; `gitnexus query "RDF round trip loader dumper"` → loader/dumper test
  cluster `tests/linkml_runtime/test_loaders_dumpers/`.

### Summary
LinkML is the only mature (DEC-5 pass) schema SSoT that fans out to every target the MWBv2 chain
needs. Its Pydantic output is **persistence-free and already carries the RDF mapping metadata**
(`class_uri`, `slot_uri`) as class/field metadata — exactly what a separate rdf-persistence
mapper needs. Its own RDF round-trip (`rdflib_loader`/`rdflib_dumper`) is an in-memory converter,
not a persistence layer, and it still drops language tags. The TS generator is still weak; a new
OpenAPI generator exists but only fills `components/schemas` from a hand-written paths template.
No generator emits repositories, mappers or API routes.

### Architecture & implementation principles (evidence)
- **Generator framework.** Each generator subclasses `Generator` (`linkml/utils/generator.py`),
  reads a `SchemaView`, renders Jinja2. Pydantic templates are Jinja files
  (`pydanticgen/templates/class.py.jinja`, `attribute.py.jinja`, `base_model.py.jinja`, …) and
  can be overridden with `template_dir` (`pydanticgen/pydanticgen.py:233`); extra classes / fields
  can be injected (`injected_classes`, `injected_fields`, `:243-252`); per-module output with
  `split` / `split_mode` (`:327`, `:379`).
- **RDF metadata in generated Pydantic.** `class.py.jinja`:
  `linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({...})` holds `class_uri` etc.;
  `attribute.py.jinja:18`: `json_schema_extra = {"linkml_meta": {...}}` holds `slot_uri`,
  `range`, `multivalued`, `inlined`. Controlled by `metadata_mode` AUTO / EXCEPT_CHILDREN / FULL /
  NONE (`pydanticgen.py:975-1016`). `LinkMLMeta` is a frozen `RootModel[dict]`
  (`pydanticgen/includes.py:6-8`). Generated classes import only pydantic — **no persistence
  code** (cosmic-python compatible).
- **IRI typing.** `uri` and `uriorcurie` have `repr: str` in
  `linkml_runtime/linkml_model/model/schema/types.yaml:125-148`; `pydanticgen.py:52` uses
  `t.repr` → generated field type is `str`. `grep AnyUrl` over the whole monorepo: **0 hits**.
  MWB gap "Pydantic AnyUrl not mapped" is **still true**; a custom template or an injected
  `Annotated[str, AfterValidator]` type is the workaround.
- **TypeScript.** `typescriptgen.py:25-31` `type_map` = str, int, Bool, float, `XSDDate → "date"`.
  `range()` (`:188-231`) never checks `sv.all_enums()`, so an enum-ranged slot falls through to
  `return "string"` (`:231`), although enums themselves are now emitted as `export enum`
  (`:49-62`). `XSDDate` maps to `date` — not a TypeScript type (should be `Date` or `string`);
  `XSDDateTime`, `Decimal`, `URI` are unmapped → `string` with a warning (`:226`). References to
  classes with identifiers become `export type XId = string` (`:44-46`). MWB gaps **still true**:
  enums are declared but not used for typing, `uri → string`, dates broken.
- **JSON-LD context + frame.** `jsonldcontextgen.py:83-86` adds `emit_frame`,
  `embed_context_in_frame`, `frame_body`, `frame_root`; `:204-236` writes `<out>.frame.jsonld`
  with `@type` = tree-root `class_uri`. New since the MWB evaluation; directly useful for an API
  that returns framed JSON-LD.
- **SHACL.** `shaclgen.py` (971 LOC) emits `sh:closed` + `sh:ignoredProperties`, `sh:class` /
  `sh:datatype` / `sh:nodeKind`, min/max count, pattern, `sh:in`, `sh:SPARQLConstraint`.
  `--default-language` tags labels only (`utils/language_tags.py`, used by owlgen/shaclgen) — it is
  about schema metadata, not instance data.
- **OpenAPI (new).** `openapigen.py` (756 LOC): the user supplies an OpenAPI template with
  `paths`; schemas marked `x-linkml-schema`/`x-linkml-source` are filled from the JSON Schema
  generator (`:147-165`, `:537-600`), validated with `openapi_spec_validator` (`:16-18`).
  **It does not generate paths/operations** — routes stay hand-written.
- **GraphQL.** `graphqlgen.py` (121 LOC) emits types, scalars and enums only; no `Query` /
  `Mutation`, no resolvers.
- **SQLAlchemy — the precedent for a separate mapper.** `sqlalchemygen.py:68` defaults to
  `TemplateEnum.IMPERATIVE`; `sqlalchemy_imperative_template.py` generates `Table(...)` objects plus
  `mapper_registry.map_imperatively(DomainClass, tbl_X, ...)` over the *imported* domain classes
  (`from {{model_path}} import *`). This is the cosmic-python "classical mapping" pattern — but
  relationship mappings are commented out (`#'{{mapping.source_slot}}': relationship(...)`), so it
  is immature. There is **no RDF analogue** (no generated SPARQL mapper / repository).
- **RDF round-trip (linkml_runtime).**
  - Dumper `dumpers/rdflib_dumper.py:76-173`: identifier slot → IRI, no identifier → `BNode`
    (`:129`); enum with `meaning` → IRI else literal (`:91-104`); typed literal via
    `utils/rdf_terms.py:177-192` (`Literal(value, datatype=...)`, xsd:string plain); ordered
    multivalued → `rdf:List` (`:150-162`); adds `rdf:type` from the class unless a
    `designates_type` slot wrote it (`:163-172`). **No language tag is ever written.**
  - Loader `loaders/rdflib_loader.py:48-199`: root subjects found by `rdf:type` of the target class
    (`:95`); type designator resolves polymorphism (`:115-122`); unmapped predicates raise
    `MappingError` unless `ignore_unmapped_predicates` (`:134-137`); unprocessed triples
    tolerated by default (`allow_unprocessed_triples=True`, `:55`, `:196-199`); literals return
    `o.value` (`:263-270`) — **language tag lost**; inlined objects resolved through `Pointer`s
    (`:312-316`).
  - So: a graph ↔ object *converter* over an in-memory rdflib Graph, keyed by `SchemaView` at
    runtime. No session, identity map, diff, SPARQL, named graphs or store port.
- **rdf:type for instances.** RDF dump: yes (automatic). JSON dump: only top-level `@type`
  (`dumpers/json_dumper.py:34-66`, `utils/yamlutils.py:385-399`); nested objects carry a type
  only via a `designates_type` slot. YAML/JSON instance data stays type-implicit → the
  "containers trick" of the MWB evaluation is still needed, or a `designates_type` slot of range
  `uriorcurie` on the root class.
- **Language-tagged strings.** No `langString` type in `linkml:types`; loader/dumper ignore
  `Literal.language`. **Gap still true.** Modelling workaround: a `LangString` class
  (`value`, `language`) — but the rdflib loader maps it to a blank node, not to a tagged literal.

### Patterns catalogue (LinkML)
| Pattern | Where |
|---|---|
| Schema-as-SSoT, multi-target generation | `generators/*` |
| Template-method generator + overridable Jinja templates | `pydanticgen/template.py`, `templates/*.jinja`, `template_dir` |
| Metadata-carrying anemic domain classes | `linkml_meta` ClassVar + field `json_schema_extra` |
| Classical / imperative mapping (domain ≠ mapping) | `sqlalchemy_imperative_template.py` |
| Runtime schema-driven converter (no codegen) | `SchemaView` + `RDFLibLoader`/`RDFLibDumper` |
| Type designator for polymorphism | `schemaview.get_type_designator_slot`, loader `:115` |
| Template-filled contract generation | `openapigen.py` (paths template + generated components) |

### Scores (as a code-generation foundation for rdf-persistence)
| # | Score | Justification | Evidence |
|---|---|---|---|
| C1 | 3 | All schema/contract targets present; persistence/repository/API targets absent; lang tags absent | generator list; `rdflib_loader.py:263-270` |
| C2 | 4 | Persistence-free domain + imperative-mapping precedent; RDF converter is not a mapper | `class.py.jinja`; `sqlalchemy_imperative_template.py` |
| C3 | 4 | CLI per generator, typed Pydantic v2 output, good docs; TS weak | `docs/generators/`; `typescriptgen.py:25-31` |
| C4 | 3 | Heavy dependency tree (generator side); runtime side light (pydantic) | `packages/linkml/pyproject.toml` |
| C5 | 5 | rdflib, pydantic, jinja2, openapi-spec-validator | imports in generators |
| C6 | 5 | Model-first by construction; domain classes free of persistence | `pydanticgen` output |
| C7 | n.a. | No store access in generators; runtime converter works on rdflib Graph only | `rdflib_loader.py:48` |
| C9 | 5 | Emits SHACL, OWL, JSON-LD ctx/frame, JSON Schema, OpenAPI, ShEx, GraphQL SDL | generators |
| C10 | 3 | Active, many maintainers; monorepo merge and frequent generator output changes mean pinning + regeneration in CI | archived runtime repo; `ModelChanges.md` |
| C8 | 5 | Large test suite, CI, 477 k dl/mo, many contributors | `tests/`, `codecov.yml` |

JS-friendliness: TS interfaces (weak), JSON Schema, OpenAPI components, GraphQL SDL, JSON-LD ctx/frame.

**Verdict: ADOPT** as the L0 SSoT and generator host. **Extend** with custom Pydantic templates
(IRI type, lang-string type) and a **new rdf-persistence generator** (G2) that reads
`linkml_meta`/SchemaView. **Borrow ideas** from `rdflib_loader/dumper` (type designator, Pointer
resolution, unmapped-predicate policy) but do not use them as the persistence layer.

## 3. Deep dive — model2owl (OP-TED/model2owl + meaningfy-ws fork)

- Upstream `OP-TED/model2owl` @ 351ee02, EUPL-1.2, XSLT 3.0 (Saxon via `pom.xml`), Makefile driven.
  Fork `meaningfy-ws/model2owl` has branch `feature/linkml` (last commit 2025-02-25 "removed uris for
  Enums"; **5 ahead / 365 behind develop**, files `src/linkML.xsl`, `src/linkml/elements-linkml.xsl`,
  `src/linkml/linkML-helpers.xsl`; read via `gh api …/contents?ref=feature/linkml`).
- GitNexus indexes XSLT poorly (1 568 nodes, 3 flows) — evidence comes from file reading.

### Summary
model2owl turns an EA XMI export (SEMIC conventions) into OWL core, OWL restrictions, SHACL shapes,
a JSON-LD context, an HTML glossary, a ReSpec config and a **conventions report (SVRL)**. Upstream
has **no LinkML output**. The LinkML export exists only on a stale fork branch.

### Implementation & the four MWB gaps (status 2026-11)
| MWB gap | Status | Evidence |
|---|---|---|
| no `uri` type | fixed on branch: `xsd:anyURI → uri` | `linkML-helpers.xsl:23` |
| use `linkml:types` | fixed on branch | `linkML.xsl` emits `imports: - linkml:types`, `default_range: string` |
| `String` vs `string` | **still present**: untyped attribute falls back to `String` | `elements-linkml.xsl:187` |
| enum | enum URIs removed (commented out); permissible values carry only a description — **no `meaning` IRI**, so SKOS concept IRIs are lost and the rdflib dumper will write plain literals | `elements-linkml.xsl:343-375`; LinkML `rdflib_dumper.py:101-104` |
| NCName | names derived by `substring-after(@name, ':')`; dots in enum values replaced by `_` | `elements-linkml.xsl:72, 365` |
| lang strings | `rdf:langString`, `rdf:PlainLiteral` → `string` (tag lost) | `linkML-helpers.xsl:56-57` |
| upstream status | not merged; branch 365 commits behind | GitHub compare API |

Upstream SHACL (`src/shacl-shape-lib/`) emits `sh:targetClass`, `sh:property` with
`sh:class`/`sh:datatype` (incl. `rdf:langString`, `elements-shacl-shape.xsl:282`), min/max count,
`sh:sparql` checks, `sh:or` — the *explicit* style that schema-automator's SHACL importer
supports (§4). JSON-LD context lib emits `@id`, `@type`, `@container`.

### Scores
| # | Score | Justification |
|---|---|---|
| C1 | 3 | OWL/SHACL/ctx/docs complete; LinkML export partial and off-trunk |
| C2 | 3 | Clean XSLT module split per target (`*-lib/`); conventions checked before generation |
| C3 | 2 | XSLT + Saxon + Make; hard to extend for Python developers |
| C4 | 3 | Java/Saxon toolchain; deterministic batch |
| C5 | 3 | Saxon, standard XSLT; reinvents nothing at runtime |
| C6 | 5 | UML-first, SEMIC conventions, stable IRIs |
| C7 | n.a. | |
| C9 | 4 | Standard outputs (OWL, SHACL, JSON-LD ctx) |
| C10 | 3 | Maintained by OP-TED/Meaningfy, release branches 3.1/3.2; fork divergence is a cost |
| C8 | 3 | functional tests dir (`test/`), 49 stars |

**Verdict: INTEGRATE (in-house).** Keep model2owl as the UML → OWL/SHACL step. Do **not** invest in
the XSLT LinkML exporter; instead go **SHACL → LinkML via schema-automator `import-shacl`** (or a
thin XSLT fix-up) — one fewer bespoke transform to maintain. If the XSLT exporter stays, it must
emit `meaning:` for enum values and a lang-string type.

## 4. Deep dive — schema-automator (linkml/schema-automator)

- @ 0cf0e88, BSD-3; importers in `schema_automator/importers/` (OWL, RDFS, **SHACL**, JSON Schema,
  SQL, XSD, DBML, Frictionless, caDSR, …); generalizers infer schemas from data.

### Findings
- **SHACL → LinkML importer (new, 986 LOC)** `importers/shacl_import_engine.py`: supports explicit
  (`sh:targetClass`), implicit (class = shape) and *split* shapes across files (merged:
  conjunctive within a file, laxest bound across files, `merge_classes` `:571`); maps `sh:class` /
  `sh:node` / `sh:datatype` / `sh:in` (inline enums `:515`) / `sh:or` / `sh:xone` / qualified
  shapes / cardinality (`:554`); drops `sh:sparql` (documented, `:40-60`). CLI `import-shacl`
  (`cli.py:553-580`); tests `tests/test_importers/test_shacl_importer.py`.
- `TYPE_MAP` (`:133-146`) maps `anyURI → uri`, dates, decimals; **`rdf:langString` falls to
  `string`** (`TYPE_MAP.get(..., "string")`, `:501`) — lossy.
- **OWL importer requires OWL functional syntax** (funowl; `owl_import_engine.py:37-40`
  "ontologies must be in functional syntax"); maps some/all-values-from and cardinality restrictions
  into `slot_usage` (`:75-137`). RDFS importer maps `langString → string` (`rdfs_import_engine.py:362`).
- MWB gap "no RDFS/OWL→LinkML path (schema-automator only)": **partly closed** — the path is still
  schema-automator only, but the SHACL route is now substantive and matches model2owl's output.

Scores: C1 3 · C2 3 (importer/engine per format) · C3 3 · C4 3 (funowl, linkml-map deps) · C5 5 ·
C6 4 · C9 4 · C10 3 (68 stars, active) · C8 3 (tests present). **Verdict: INTEGRATE** at build
time (model2owl SHACL → `schemauto import-shacl` → curated LinkML overlay), with a check that the
round-trip SHACL (LinkML `gen-shacl`) stays equivalent to the model2owl SHACL.

## 5. Deep dive — shacl2code (JPEWdev/shacl2code)

- @ ba438c3, MIT; generator `src/shacl2code/model.py` reads a SHACL+OWL model (JSON-LD) and a
  context; targets Python, C++, Go, Rust, JSON Schema (`lang/templates/`). Used for SPDX 3.

### Findings
- Generated Python is a **standalone runtime** (no rdflib; `templates/python/model.py.j2` imports
  only stdlib): `SHACLObject` base with typed property descriptors (`StringProp`, `AnyURIProp`,
  `DateTimeProp`, `EnumProp`, `ObjectProp`, `ListProp`, `model.pyi.j2:68-330`), validation on
  assignment, `SHACLObjectSet` (object graph with link resolution / identity by IRI,
  `:512`), pluggable `Encoder`/`Decoder` and `JSONLDSerializer`/`JSONLDDeserializer`
  (`:394-590`) bound to a fixed JSON-LD context.
- SHACL features read: path, datatype, class, nodeKind, min/max count, pattern, hasValue
  (`model.py:337-409`). No `rdf:langString` support (grep: 0 hits).
- Domain objects are coupled to serialisation (not to storage); no store, no SPARQL.

Scores: C1 2 · C2 3 · C3 3 · C4 4 · C5 1 (re-implements RDF terms/serialisation) · C6 3 · C9 3 ·
C10 3 · C8 3 (tests per language). **Verdict: BORROW IDEAS** (DEC-5 fail): IRI-typed property
descriptors, object-set identity + link resolution, encoder/decoder port, multi-language
generation from one SHACL model.

## 6. Desk-checked notes (not deep-dived)
- **linkml-store**: backends DuckDB, Mongo, Neo4j, Solr, ChromaDB, filesystem, HDF5, Ibis, Dremio
  (`src/linkml_store/api/stores/`) — **no RDF / SPARQL backend**. `webapi/main.py` is a *generic*
  (non-generated) FastAPI over databases/collections/objects/facets/search (routes at
  `:143-728`). Pattern: schema-driven generic CRUD service (cf. mu-cl-resources). README: "APIs …
  subject to change". Borrow ideas (L4).
- **datamodel-code-generator + fastapi-code-generator** (DEC-5 pass): OpenAPI → Pydantic + FastAPI
  routers. Chained after LinkML `gen-openapi` they would regenerate Pydantic from JSON Schema and
  **lose `linkml_meta` (class_uri/slot_uri)** — so for MWBv2 use them only for route skeletons
  that import LinkML-generated models, or not at all (claim from docs, not code-checked).
- **LDO** (`@ldo/cli`): ShEx → TS typings + JSON-LD context + "ShapeType"; `jsonld-dataset-proxy`
  presents an RDF/JS dataset as plain JSON-like TS objects. Best TS-side idea in the space; DEC-5
  fail; ShEx not SHACL.
- **shacl-form / Sparnatural**: shape-driven UI (forms; query builder) — L5 consumers of the
  generated SHACL; Sparnatural passes DEC-5.
- **SeMPyRO**: hand-written Pydantic for DCAT-AP v3 with RDF serialisation — shows the demand for
  SEMIC-AP Pydantic classes; generation from model2owl SHACL would replace the hand-writing.

## 7. Feature inventory (taxonomy v2 ids, for the deep-dived set)
| Id | LinkML | model2owl | schema-automator | shacl2code |
|---|---|---|---|---|
| M2 schema language | present (LinkML) | present (UML/XMI) | n.a. (importer) | present (SHACL) |
| M3 codegen | present | present (OWL/SHACL/ctx, not code) | n.a. | present |
| M4 inheritance → rdf:type/subClassOf | present (`is_a`, type designator) | present | present | present |
| M5 validation on construct | present (Pydantic) | n.a. | n.a. | present (on assignment) |
| M13 constraint emission (SHACL) | present (`gen-shacl`) | present | n.a. | absent |
| M14 reverse engineering | n.a. | n.a. | present (OWL-ofn, RDFS, SHACL, data) | absent |
| I2 blank nodes | partial (no identifier → BNode, `rdflib_dumper.py:129`) | n.a. | n.a. | present (NodeKind) |
| R1 single/multi, rdf:List | present (`list_elements_ordered`, `:150-162`) | partial (cardinality) | present | present (`ListProp`) |
| R2 references / inverse | partial (`inverse` slot metadata; no runtime inverse) | present (UML connectors both ends) | partial | partial |
| L1 typed literals | present (`rdf_terms.py:177`) | present | present | present |
| L2 language tags | **absent** (instance data) | partial (SHACL `rdf:langString`; LinkML export loses it) | absent (→ string) | absent |
| X1 JSON-LD | present (ctx + frame + json dumper) | present (ctx) | n.a. | present |
| X4 schema export for clients | present (JSON Schema, OpenAPI components, TS, GraphQL SDL) | absent | n.a. | present (JSON Schema) |
| X6 generated JSON:API contract | absent | absent | absent | absent |
| D1 static typing | present (Py), weak (TS) | n.a. | n.a. | present |
| D10 diagrams | present (erdiagram, mermaid, plantuml) | present (glossary/HTML) | n.a. | absent |
| O1 OWL restrictions | present (`gen-owl`) | present (`owl-restrictions.xsl`) | partial (import) | absent |
| RAD1 zero-code CRUD service | absent (linkml-store generic API, non-RDF) | absent | absent | absent |

### Proposed new features (area **G\*** — generation)
| Id | Feature | First seen in |
|---|---|---|
| G1 | Persistence-free generated domain classes that carry RDF mapping metadata (class_uri, slot_uri, range, multivalued, inlined) as class/field metadata | LinkML pydanticgen `linkml_meta` |
| G2 | Generated mapper / repository layer separate from the domain classes (imperative / classical mapping) | LinkML gen-sqla imperative (SQL only; RDF analogue absent everywhere) |
| G3 | Overridable generator templates + injected base classes/fields | LinkML `template_dir`, `injected_*` |
| G4 | Per-module (split) generation following schema imports | LinkML `split`, `SplitMode` |
| G5 | IRI-typed fields in generated code (Pydantic `AnyUrl`/constrained str, branded TS type) | shacl2code `AnyURIProp` (LinkML absent) |
| G6 | Language-tagged string type in schema + generated code + round-trip | absent in all four |
| G7 | JSON-LD context **and frame** generated from the schema | LinkML gen-jsonld-context `--emit-frame` |
| G8 | API contract generation (OpenAPI) from schema + operations template | LinkML gen-openapi |
| G9 | API route / handler generation per aggregate (FastAPI) wired to repositories | absent (fastapi-code-generator from OpenAPI only) |
| G10 | Shapes/ontology → schema import with multi-file merge (refines M14) | schema-automator `import-shacl` |
| G11 | UML → OWL/SHACL/ctx with a modelling-conventions report gate | model2owl SVRL report |
| G12 | Generated data-quality SPARQL check queries | LinkML gen-sparql |
| G13 | Generated mapping rules (YARRRML/RML) from schema | LinkML gen-yarrrml |
| G14 | Polymorphic instance typing via a type-designator slot (rdf:type on instances in JSON/YAML) | LinkML `designates_type` |
| G15 | Enum values bound to concept IRIs (`meaning`) so enums serialise as IRIs | LinkML PV `meaning`; lost in model2owl LinkML export |
| G16 | Standalone generated bindings with object-set identity + pluggable encoder/decoder | shacl2code |
| G17 | Shape-driven UI generation (forms / query builder) from SHACL | shacl-form, Sparnatural (→ L5 angle) |
| G18 | Build-time regeneration, never-edited generated code, generator version pin + golden-file diff | MWBv2 runbook; LinkML `ModelChanges.md` churn |

## 8. Patterns catalogue for the angle
| Pattern | Exemplar | Use in MWBv2 |
|---|---|---|
| Single schema, many generators | LinkML | SSoT for Python/TS/SHACL/ctx |
| Metadata-carrying anemic domain | LinkML Pydantic `linkml_meta` | domain layer stays pure; mapper reads metadata |
| Classical (imperative) mapping | LinkML gen-sqla imperative; SQLAlchemy | template for a generated RDF mapper registry |
| Runtime-schema mapper (no generated mapper) | linkml_runtime rdflib loader/dumper; mu-cl-resources | mapper driven by SchemaView at runtime |
| Contract template + generated components | LinkML gen-openapi | API contract with hand-written paths |
| Shape → schema import | schema-automator import-shacl | model2owl SHACL → LinkML |
| Standalone binding + codec | shacl2code | idea for TS/JSON-LD codec |
| Shape → proxy objects over a dataset | LDO jsonld-dataset-proxy | TS client over JSON-LD responses |
| Conventions gate before generation | model2owl SVRL report | quality gate in CI |

## 9. How the options plug into MWBv2 and into an ACL-agnostic rdf-persistence
- **Recommended chain:** UML (EA) → model2owl → OWL + SHACL + ctx → `schemauto import-shacl` (or
  curated hand-maintained LinkML) → LinkML → `gen-pydantic` (custom templates: IRI type,
  lang-string type) = **domain layer**; rdf-persistence mapper reads `linkml_meta` / SchemaView =
  **adapters layer**; `gen-shacl` for write-time validation; `gen-jsonld-context --emit-frame` for
  the API; `gen-typescript` with a custom template (or LDO-style codegen) for the UI.
- **ACL-agnostic:** nothing in L0 touches authorization. Generated artefacts never contain
  `GRAPH`-scoped access assumptions; graph placement and policy belong to rdf-persistence config /
  the proxy (A2, P12). One L0 contribution: generate *policy inputs* (class/predicate lists per
  aggregate) for an external PEP — not policies themselves (DEC-8).
- **Golden thread:** generated code at build/test time, never edited (G18); pin linkml version;
  diff generated output in CI because generator output changes between minor releases.

## 10. Architecture variants enabled
| Variant | L0 chain | Mapper | API | Trade-off |
|---|---|---|---|---|
| A. LinkML-generated domain + metadata-driven runtime mapper | model2owl → LinkML → gen-pydantic | rdf-persistence reads `linkml_meta` at runtime (no generated mapper) | FastAPI hand-written or G9 generator, JSON-LD via ctx/frame | least codegen to own; mapper generic |
| B. LinkML-generated domain + **generated** mapper/repositories (new G2/G9 generator, Jinja, like gen-sqla imperative) | same | generated per aggregate | generated FastAPI routes | most MWBv2-like; we own a generator |
| C. Shapes-first | model2owl SHACL as SSoT → shacl2code-style generator | generated bindings | — | skips LinkML; loses LinkML ecosystem |
| D. OpenAPI-first | LinkML → gen-openapi → fastapi-code-generator | separate | generated skeleton | loses `linkml_meta` unless models are imported, not regenerated |
| E. Generic service (no per-model code) | LinkML SchemaView at runtime | generic | generic CRUD (linkml-store webapi / mu-cl-resources style) | RAD1; weak typing for domain logic |

## 11. Open questions
1. Is LinkML (curated) or model2owl SHACL the master after UML? (decides whether import-shacl runs
   once or on every build).
2. Language-tagged strings: which representation do we standardise — `dict[lang, str]`,
   `list[LangString]`, or rdflib `Literal` in the domain? Needs a LinkML type + template + mapper
   support (G6); upstream LinkML has none.
3. Do we contribute fixes upstream (TS enum-range typing, `date`→`Date`, uri → `AnyUrl` option) or
   keep custom templates? Upstream contribution lowers C10 cost.
4. Generated mapper (variant B) vs runtime mapper (variant A): MWBv2 runbook says "generated,
   never-edited data classes" — does that extend to repositories and routes?
5. Retire the meaningfy-ws `feature/linkml` XSLT exporter in favour of import-shacl?

Not checked: generator outputs were not executed (rule: no install/run); fastapi-code-generator,
datamodel-code-generator, LDO, shacl-form, linkml-store claims are from README/listings only.

## Round 4

Scope: (a)–(e) for the four deep-dived candidates (LinkML incl. linkml_runtime, model2owl incl. the
meaningfy-ws `feature/linkml` branch, schema-automator, shacl2code); purpose/origin and variant fit
only for desk-scan candidates. Clones and GitNexus indexes as in round 3. Absences were confirmed by
grepping `packages/linkml/src/linkml/generators`, `packages/linkml_runtime/src`,
`schema_automator/`, `model2owl/src`, `shacl2code/src` for: `hydra`, `graphql:`, `type Query`,
`authoriz|polic`, `outbox|RDFPatch`, `transaction|rollback`, `etag|If-Match`, `cursor`. All hits
were false positives (naming policy in `common/naming.py`, jQuery in model2owl `static/js`, a
contextmanager in shacl2code) except those cited below.

### (a) v3 cross-check

Columns: **LML** = LinkML · **M2O** = model2owl · **SA** = schema-automator · **S2C** = shacl2code.

| Id | LML | M2O | SA | S2C | Evidence |
|---|---|---|---|---|---|
| G1 | present | n.a. | n.a. | partial | LML `pydanticgen/templates/class.py.jinja` (`linkml_meta` ClassVar), `attribute.py.jinja:18`; S2C classes carry IRIs but embed the codec (`templates/python/model.pyi.j2:447-590`) |
| G2 | partial | absent | n.a. | absent | LML `sqlalchemy/sqlalchemy_imperative_template.py` (SQL only, relationships commented out); no RDF mapper in any clone |
| G3 | present | partial | n.a. | present | LML `pydanticgen.py:233,243-252`; S2C `lang/jinja.py:18-25` (`--template`); M2O: XSLT imports can be overridden (`config-proxy.xsl`) |
| G4 | present | partial | present | absent | LML `split`/`SplitMode` `pydanticgen.py:125,327,379`; SA loads a directory of shape files (`shacl_import_engine.py:183`); M2O one output per target module |
| G5 | absent | partial | partial | present | LML `types.yaml:145-148` `repr: str`, 0 `AnyUrl` hits; M2O branch `xsd:anyURI → uri` (`linkML-helpers.xsl:23`); SA `anyURI → uri` (`:134`) but then LML types it `str`; S2C `AnyURIProp` (`model.pyi.j2:119`) |
| G6 | absent | partial | absent | absent | LML `rdflib_loader.py:263-270` (`o.value`); M2O SHACL emits `sh:datatype rdf:langString` (`elements-shacl-shape.xsl:282`) but LinkML export maps it to `string` (`linkML-helpers.xsl:56`); SA `:501` fallback `string`; S2C 0 hits |
| G7 | present | partial | n.a. | absent | LML `jsonldcontextgen.py:83-86,204-236` (one frame per run, `@type` from `tree_root`/`frame_root` `:275-276`); M2O context only (`jsonld-context.xsl`) |
| G8 | partial | partial | n.a. | partial | LML generates classes and context, but the runtime maps via `SchemaView`, not the context (`rdflib_dumper.py:76-173`); M2O context only; S2C serialiser bound to one context (`encode_context`, `model.pyi.j2:589`) |
| G9 | present | absent | n.a. | absent | LML `openapigen.py` (paths from a user template, `:147-165`) |
| G10 | absent | absent | absent | absent | grep `@app\.\|APIRouter\|paths:` generation: none (gen-openapi only reads template paths `:184`) |
| G11 | absent | absent | absent | absent | grep `hydra`: 0 hits in all four |
| G12 | partial | absent | absent | absent | LML `graphqlgen.py` (121 LOC) types/enums only, 0 `type Query` |
| G13 | absent | absent | absent | absent | no filter/sort grammar generator (grep `filter`/`sort` in generators: SQL validation only) |
| G14 | absent | absent | absent | absent | LML `sparqlgen.py` emits check queries, not projections |
| G15 | absent | absent | absent | absent | – |
| G16 | partial | absent | n.a. | absent | LML `typescriptgen.py` (weak: `:25-31`, `:231`); S2C has no TS target (`lang/`: cpp, golang, python, rust, jsonschema) |
| G17 | n.a. | n.a. | present | absent | SA `shacl_import_engine.py` (986 LOC), `owl_import_engine.py`, `rdfs_import_engine.py` |
| G18 | absent | present | n.a. | absent | M2O `svrl-conventions-report.xsl`, `html-conventions-report.xsl` |
| G19 | absent | absent | absent | absent | M2O `reasoning-layer-lib/` writes OWL axioms; it does not run a reasoner |
| G20 | absent | absent | absent | absent | same |
| G21 | present | partial | absent | absent | LML `sparqlgen.py`; M2O SHACL with `sh:sparql` checks (`shacl-shape-lib`, 8 occurrences) |
| G22 | present | absent | absent | absent | LML `yarrrmlgen.py` (386 LOC) |
| G23 | present | n.a. | n.a. | partial | LML `rdflib_loader.py:115-122`, `common/type_designators.py`; S2C writes `@type` per object (typed `SHACLObject` subclasses) |
| G24 | present | absent | present | present | LML `rdflib_dumper.py:91-104`; M2O branch enum URIs commented out (`elements-linkml.xsl:343-358`); SA `pv.meaning` from `sh:in` (`:534-540`); S2C `EnumProp(IRIProp)` (`model.pyi.j2:318`) |
| G25 | absent | n.a. | n.a. | present | S2C `SHACLObjectSet`, `Encoder`/`Decoder` (`model.pyi.j2:394-560`) |
| G26 | present | n.a. | present | present | LML `SchemaView.induced_slot` merges `slot_usage` along `is_a`; SA `inherit_constraints` (`:790`); S2C `get_inherited_value` (`model.py:147-154`) |
| G27 | n.a. | n.a. | n.a. | n.a. | process feature; LML ships no golden-file harness of its own |
| AZ29 | absent | absent | absent | absent | grep `authoriz\|polic`: false positives only |
| X22 | partial | partial | n.a. | partial | the generated context is a static file that can be bundled; no bundling support itself |
| U1 | partial | n.a. | n.a. | absent | LML TS interfaces + JSON Schema, no client/fetch code |
| U4, U10 | n.a. | n.a. | n.a. | n.a. | consumers of the SHACL / JSON Schema these tools emit (LML `gen-shacl`, `gen-json-schema`; M2O SHACL) |
| AZ1–AZ28 | n.a. | n.a. | n.a. | n.a. | build-time generators, no request path; grep confirms no policy code |
| T1–T11 | n.a. | n.a. | n.a. | n.a. | no store access; grep `transaction\|rollback`: 0 hits |
| E1–E9 | n.a. | n.a. | n.a. | n.a. | grep `outbox\|RDFPatch`: 0 hits |
| U2, U3, U5–U9, RAD3, RAD4, X17–X21 | n.a. | n.a. | n.a. | n.a. | service / client runtime features |
| D11–D13 | n.a. | n.a. | n.a. | n.a. | runtime error features |
| S15–S19 | n.a. | n.a. | n.a. | n.a. | store features |

Counts over the 27 G-features (G1–G27): LinkML 10 present / 4 partial / 11 absent / 2 n.a. ·
model2owl 1 / 7 / 13 / 6 · schema-automator 4 / 1 / 11 / 11 (mostly n.a. for an importer) ·
shacl2code 5 / 3 / 18 / 1. Every non-G v3 feature is n.a. for these build-time tools, except
X22 and U1 (partial, LinkML).

Id mapping check (round-3 proposals → v3): my G1–G4 → G1–G4; G5 → G5; G6 → G6; G7 → G7;
G8 → G9; G9 → G10; G10 → G17; G11 → G18; G12 → G21; G13 → G22; G14 → G23; G15 → G24; G16 → G25;
G17 → U4/U10; G18 → G27. Consistent with the appendix.

### (b) Purpose and origin

| Tool | Built for | Origin and design angle | Where it fits (L0–L6, V1–V5) |
|---|---|---|---|
| LinkML | A modelling language for data standards that generates schemas and code for many targets | Started at Lawrence Berkeley National Laboratory (Mungall group; first CITATION author Sierra Moxon, LBNL) for biomedical standards (Biolink / NCATS Translator, Monarch, NMDC). Data-exchange-first: designed to validate and convert *documents*, not to persist object graphs, which is why the RDF round-trip is a converter and language tags in instance data were never needed | L0 in every variant; its Pydantic output is L1's domain layer; the runtime converter is not an L1 persistence layer |
| model2owl | Turning EA UML models that follow the SEMIC conventions into OWL, SHACL, a JSON-LD context, a glossary and a conventions report, for the eProcurement Ontology (ePO) | OP-TED (Publications Office of the EU), built by Meaningfy (`CONTRIBUTORS.md`: E. Costetchi, D. Paun). Publication-first: produces standards documentation, not application code; the LinkML exporter was a later Meaningfy experiment | L0 front end, upstream of LinkML; variant-independent |
| schema-automator | Bootstrapping a LinkML schema from existing artefacts (OWL, RDFS, SHACL, JSON Schema, SQL, data) | LinkML organisation. Reverse-engineering-first: an import is documented as lossy by construction (`shacl_import_engine.py:35-60`); dropped constructs are logged | L0 build step between model2owl SHACL and LinkML; variant-independent |
| shacl2code | Typed bindings for the SPDX 3 SBOM model in several languages | Joshua Watt (JPEWdev; SPDX / Yocto community). Exchange-format-first: the binding *is* the serialiser for one fixed JSON-LD context; no store, no rdflib | Ideas for L0/L1 (IRI-typed descriptors, object set, codec port); no direct fit |

Desk-scan candidates (purpose and origin only): **linkml-store** — LinkML org; generic,
schema-driven collections API over non-RDF stores (DuckDB, Mongo, Solr, Neo4j), AI/search angle.
**linkml-map** — LinkML org; schema-to-schema transforms. **datamodel-code-generator** —
contract-first Pydantic generation from OpenAPI / JSON Schema; repo now under the
`datamodel-code-generator` GitHub organisation (koxudaxi founded it). **fastapi-code-generator** —
koxudaxi; OpenAPI → FastAPI skeleton. **LDO** — o-development (Jackson Morgan), Solid community;
ShEx → TS typings + proxy objects over RDF/JS, and the CLI also accepts SHACL by converting it with
`@jeswr/shacl2shex` (`packages/cli/src/util/forAllShapes.ts:3`). **shacl-form** — ULB Darmstadt;
runtime SHACL forms. **Sparnatural** — Sparna; SHACL-configured SPARQL query builder.
**SeMPyRO** — Health-RI; hand-written Pydantic for DCAT-AP 3.

### (c) Variant fit

S = supports, E = enables (makes it possible), B = blocks / conflicts, – = neutral.

| Tool | V1 | V2 | V3 | V4 | V5 | A runtime mapper | B generated mapper & routes | C generic service |
|---|---|---|---|---|---|---|---|---|
| LinkML | S | S (needs a JSON:API generator) | S | S | S (context/frame for read side) | **E** (`linkml_meta` / SchemaView) | S (templates; mapper/route generator to build) | E (SchemaView at runtime) |
| model2owl | S | S | S | S | S | S | S | S |
| schema-automator | S | S | S | S | S | S | S | S |
| shacl2code | – | – | – | – | – | – | ideas (codec, IRI props) | – |
| linkml-store | – | – | – | – | – | – | – | ideas (generic API shape; no RDF backend) |
| datamodel-code-generator | S (client side only) | – | – | – | – | – | **B** if used to regenerate server models (drops `linkml_meta`) | – |
| fastapi-code-generator | S (skeleton) | – | – | – | – | – | S only if it imports LinkML models | – |
| LDO | – | – | S (UI on JSON-LD) | – | **E** (TS objects over RDF/JS) | – | S (TS from SHACL) | – |
| shacl-form | S | S | S | S | S | S | S | **E** (forms from shapes) |
| Sparnatural | – | – | S | S | **E** | – | – | S |
| SeMPyRO | – | – | – | – | – | ideas | ideas | – |

Headline: L0 is variant-neutral (V1–V5 all start from the same LinkML model); the generation
choice is the A/B/C axis. LinkML enables A and C today; B needs a generator we build.

### (d) Corrections to the integrated docs

1. `catalogue.adoc` LinkML origin cell ("Biomedical data-standards community (Monarch, NCATS)"):
   add the originating institution — Lawrence Berkeley National Laboratory (CITATION.cff first
   author Sierra Moxon, LBNL); NCATS is a funder via Biolink/Translator, not the builder. Minor.
2. `catalogue.adoc` datamodel-code-generator ("One maintainer (koxudaxi)"): the repo now resolves
   to `datamodel-code-generator/datamodel-code-generator` (organisation; `gh api` 2026-11-03).
3. `catalogue.adoc` LDO ("ShEx / SHACL → TypeScript"): **correct** — this corrects my round-3
   note "ShEx not SHACL"; the CLI converts SHACL via `@jeswr/shacl2shex`.
4. `variants.adoc` V1 / approach B ("typed REST client generated from OpenAPI"): caveat to add.
   If FastAPI routes use LinkML Pydantic models, FastAPI's runtime OpenAPI carries a non-standard
   `linkml_meta` object in every schema (from `json_schema_extra`, `attribute.py.jinja:18`) and
   types IRIs as plain `string`. LinkML's own `gen-openapi` strips it (`openapigen.py:336-347`),
   so either publish `gen-openapi` output or strip it in a FastAPI `openapi()` hook.
5. `building-blocks.adoc` L0 gaps ("TypeScript generator mistypes enums and dates"): more
   precisely, enums are declared as `export enum` but enum-ranged fields are typed `string`
   (`typescriptgen.py:231`); `xsd:date` maps to the invalid TS type `date` (`:30`).
6. Origin cells for model2owl, schema-automator, shacl2code, fastapi-code-generator, shacl-form,
   Sparnatural, SeMPyRO: confirmed.

### (e) Proposed new features (round 4)

| Proposed id | Feature | First seen in |
|---|---|---|
| G28 | Contract hygiene: generator bookkeeping (`linkml_meta`, `x-linkml-*`) stripped from published contracts | LinkML `openapigen.py:92,336-347` |
| G29 | Importer lossiness report: constructs dropped or degraded on import (e.g. `sh:sparql`, dangling ranges → `uriorcurie`) are listed | schema-automator `shacl_import_engine.py:35-60,756-790` |
| G30 | Cross-path equivalence gate: shapes produced by two generation paths (model2owl SHACL vs LinkML `gen-shacl`) are checked as equivalent in CI | absent everywhere (proposed) |

Not checked in round 4: generator outputs were still not executed; the FastAPI `linkml_meta`
leak (correction 4) is inferred from Pydantic's documented `json_schema_extra` merge plus LinkML's
own stripping code, not observed at runtime.

## Round 5

Final pass over the four deep-dived candidates (LinkML incl. linkml_runtime @ d48b197 = v1.12.1,
model2owl @ 351ee02, schema-automator @ 0cf0e88, shacl2code @ ba438c3). Same clones and indexes.

### (a) v4 cross-check

Columns as in round 4: **LML** · **M2O** · **SA** · **S2C**. Absences confirmed by grep over the
four clones for `conformsTo`, `cypher|neo4j`, `TypedDict`, `aggregation|composite`,
`versionIRI|versionInfo`, `migrat`, `mcp` (hits cited where real).

| Id | LML | M2O | SA | S2C | Evidence |
|---|---|---|---|---|---|
| B1 | partial | absent | n.a. | absent | LML has no composition construct; `inlined`, `tree_root` and free annotations are the only hooks (`meta.yaml`); M2O ignores UML aggregation kind — grep `aggregation\|composite` over `src/**/*.xsl`: 0 hits (only a comment "aggregate definitions", `owl-core-lib/elements-owl-core.xsl:211`, about OWL class aggregation) |
| B2 | absent | absent | absent | absent | no boundary checks in generators or linter (`linter/rules.py:37-505` rule list) |
| B14 | partial | partial | n.a. | absent | LML schema `imports` + split generation (`pydanticgen.py:327,379`); M2O module-per-namespace config |
| PG2 | absent | absent | absent | absent | no Cypher/Neo4j generator (`typedbgen.py` only); linkml-store's Neo4j backend not deep-dived |
| PG3 | partial | absent | absent | absent | LML metaslots `represents_relationship`, `relational_role` (`meta.yaml:2542-2566`, status testing); no generator maps them to RDF 1.2 / edges |
| EV3 | absent | absent | absent | absent | no schema-diff utility in `linkml/utils` or `linkml_runtime/utils`; LML has `deprecated_element_has_exact_replacement` (`linkml_model/meta.py:204`) as a rename hint only |
| EV4, EV5 | n.a. | n.a. | n.a. | n.a. | linkml-map (desk only) |
| EV6 | partial | partial | n.a. | absent | both generate the SHACL a post-migration gate would run (`shaclgen.py`; `shacl-shapes.xsl`); no gate itself |
| EV7 | partial | partial | n.a. | absent | LML schema `version` → `pav:version` (`meta.yaml:841-844`) but `owlgen.py` emits no `owl:versionIRI`; M2O emits `owl:versionInfo` / `owl:versionIRI` on shapes (`shacl-shapes.xsl:90-92`); nothing stamps data |
| G28 | present | absent | n.a. | absent | LML `openapigen.py:92,336-347` |
| G29 | n.a. | absent | present | n.a. | SA `shacl_import_engine.py:35-60` (documented drops), `prune_dangling_ranges` `:756`; M2O SVRL report is about conventions, not loss |
| G30 | absent | absent | absent | absent | no graph-isomorphism / shape-equivalence check in any CI config |
| G31 | absent | partial | absent | absent | M2O Makefile downloads Saxon (`Makefile:9,72-77`) but does not check Java |
| G32 | absent | absent | absent | absent | no reasoner invocation |
| G33 | partial | n.a. | n.a. | n.a. | LML linter has `NoUndeclaredSlotsRule`, `NoUndeclaredRangesRule` (`rules.py:220,258`) but no rule requiring `class_uri`/`slot_uri`; in AUTO mode `range`, `multivalued`, `inlined`, `required`, `identifier` are excluded from `linkml_meta` (`pydanticgen/template.py:191` `meta_exclude` + `common/template.py:66-73` model fields) |
| G34 | absent | absent | absent | absent | grep `conformsTo`: 0 hits |
| G35 | absent | absent | absent | absent | no field-metamodel output in `pydanticgen` |
| G36 | absent | absent | absent | absent | grep `TypedDict` in pydanticgen: 0 hits |
| I7 | present | n.a. | n.a. | partial | LML id ↔ IRI both ways: dumper `_as_uri` (`rdflib_dumper.py:214`), loader `_uri_to_id` (`rdflib_loader.py:340`); S2C keeps full IRIs, compacts via context |
| D21 | present (for LinkML's own docs) | absent | absent | absent | LML `utils/execute_tutorial.py` executes tutorial pages; says nothing about our library |
| D25 | partial | n.a. | n.a. | n.a. | LML `rdf_canonicalize.py:287` (`canonicalize_rdf_graph`, sort is "load-bearing", `:377`) — deterministic RDF output, not load order |
| U12 | absent | absent | absent | absent | – |
| B3–B13, B15, B16, PG1, PG4, EV1, EV2, EV8, EV9, AZ30–AZ36, T12–T14, S20–S23, X23, X24, E10, I8, P20, U11, U13, D14–D20, D22–D24, D26–D29 | n.a. | n.a. | n.a. | n.a. | runtime, store, service or client features; the four tools are build-time generators with no request path (round-4 greps for policy, transaction, outbox: 0 real hits) |

Counts over the L0-relevant v4 ids (B1, B2, B14, PG2, PG3, EV3, EV6, EV7, G28–G36, I7, D21,
D25, U12 = 21): LinkML 3 present / 7 partial / 10 absent / 1 n.a. · model2owl 0 / 4 / 14 / 3 ·
schema-automator 1 / 0 / 12 / 8 · shacl2code 0 / 1 / 17 / 3. Everything else in v4 is n.a.

### (b) Page review — angles/codegen.adoc, building-blocks.adoc L0, design-implications.adoc

| # | Page line (quoted) | Problem | Fix |
|---|---|---|---|
| 1 | codegen.adoc:16 "No generator anywhere emits repositories, mappers or API routes from a LinkML or SHACL model." | Overstatement: LinkML `gen-sqla` emits SQLAlchemy mappings (imperative `map_imperatively`, declarative-2x with `relationship(...)`) from a LinkML model | "No generator emits an **RDF** mapper or repositories, or API routes; the only mapper generator (`gen-sqla`) targets SQL." Same fix for building-blocks.adoc:40 "nothing generates repositories, mappers or API routes from a model" |
| 2 | codegen.adoc:60 "LinkML 1.10.0 emits `class_uri` and `slot_uri` by default; `range`, `inlined` and `multivalued` appear only with `metadata_mode=full`" | Version and mode list incomplete. Verified on the current trunk (1.12.1): AUTO also drops `required` and `identifier` (`pydanticgen/template.py:191`, `common/template.py:66-73`); `except_children` also keeps them | "LinkML (1.10–1.12) …; `range`, `inlined`, `multivalued`, `required` and `identifier` appear only with `metadata_mode=full` or `except_children`." Same in design-implications.adoc:103-105 |
| 3 | codegen.adoc:17 "Language-tagged strings are lost along the whole chain: model2owl's LinkML export, …" | Missing caveat: upstream model2owl SHACL keeps `rdf:langString` (`elements-shacl-shape.xsl:282`); the tag is lost only from the LinkML step onward | add "model2owl's SHACL still declares `rdf:langString`; the loss starts at the LinkML step" |
| 4 | design-implications.adoc:92-94 "Boundaries need annotations or an `inlined` + shared convention, checked at generation time." and taxonomy B1 "… or UML composition" | Missing caveat: model2owl does not read UML aggregation/composition (0 hits), so the UML-composition route needs a model2owl change before LinkML sees it | add "model2owl drops UML composition today; carrying it to LinkML needs a model2owl change or an annotation" |
| 5 | codegen.adoc:232 "Round-4 proposals (no taxonomy id yet):" | Stale: they are now G28, G29, G30 in taxonomy v4 | relabel with the ids |
| 6 | codegen.adoc:152 "That is why its RDF round-trip is a converter and drops language tags" | Causal claim is my interpretation, not evidence | soften to "This fits with its RDF round-trip being a converter that drops language tags" |
| 7 | design-implications.adoc:149-150 "Nothing turns a LinkML schema change into SPARQL Update migrations. LinkML's `deprecated_element_has_exact_replacement` gives rename hints" | Confirmed (slot exists, `linkml_model/meta.py:204`; no schema-diff utility in the monorepo) | none |
| 8 | building-blocks.adoc:40-43 remaining L0 gaps (gen-openapi components only, gen-graphql types only, URIs `str`, TS enums/dates, lang tags, model2owl branch) | Confirmed | none |

Six corrections (rows 1–6) at eight page locations (rows 1, 2 and 4 each touch two pages).

### (c) Final verdict and what an architect must remember

| Candidate | Verdict |
|---|---|
| LinkML (+ linkml_runtime) | **adopt** (dependency at L0; its generated Pydantic is the L1 domain layer; its runtime converter is ideas only) |
| model2owl | **build-time** (in-house UML → OWL/SHACL front end; drop the fork's LinkML exporter) |
| schema-automator | **build-time** (SHACL → LinkML import) |
| shacl2code | **ideas** |

Three things to remember:
1. **LinkML gives you the model and the metadata, not the persistence.** Generated Pydantic is
   clean and carries `class_uri`/`slot_uri`, but `range`/`multivalued`/`inlined`/`required`/
   `identifier` reach `linkml_meta` only with `metadata_mode=full` (or the mapper infers them from
   annotations); the RDF mapper, repositories and routes are ours to build (approach A or B).
2. **Three gaps must be closed by us, in templates and the mapper, before the chain is lossless:**
   language-tagged strings (lost from the LinkML step on), IRI typing (`str`, not `AnyUrl`), and
   enum concept IRIs (`meaning`) — plus the weak TS generator if TS types come from LinkML.
3. **Pin and gate the chain.** Generator output changes between LinkML minors and two paths emit
   SHACL (model2owl, `gen-shacl`): pin versions, regenerate in CI, diff generated code (G27),
   check the two SHACL outputs stay equivalent (G30), and publish `gen-openapi` output or strip
   `linkml_meta` (G28). Decide early whether model2owl SHACL or curated LinkML is the master.

### (d) Purpose and origin, variant fit
Already given in round 4 ((b), (c)); unchanged.

### (e) New features
None. The one gap round 5 surfaced (UML composition not carried by model2owl) is covered by B1 and
reported as a page caveat (row 4), not a new feature.
