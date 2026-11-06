> Derives from: EPIC `toolkit-v1-foundation` ([proposal.md](proposal.md)) · Type: implementation

## Context

The package `rdf_persistence` is the uv scaffold. It has empty `domain/`, `services/`, `adapters/` and
`commons/` packages, a smoke test, an import-linter contract, CI (Ruff, mypy, import-linter, OpenSpec,
pytest with an 80% coverage floor, Xenon) and `testcontainers` in the test group.

The architecture it implements, all under `docs/modules/ROOT/pages/architecture/`:

| Page | What it fixes |
|---|---|
| `index.adoc` | needs N-1..N-11 (`#consumer-needs`), building blocks, public API (`#public-api`) |
| `generation.adoc` | metamodel (`#metamodel`), its revision (`#revision`), the toolchain |
| `api.adoc` | the generic router (`#mapper` for the classes question) |
| `access-control.adoc` | the ODRL check, identity (`#identity`) |
| `open-decisions.adoc` | the decisions of 2026-11-05, D-1..D-12, and D-13 once task 1.11 records it |

Generation steps 1–4 and Fuseki's behaviour were proven in a spike (LinkML 1.12.1, Fuseki 5.1.0),
marked _(spike)_ in `generation.adoc`.

## Goals / Non-Goals

**Goals:**
- the ten capabilities of the EPIC, each landing in its stage with its tests (DEC-3, DEC-4);
- the end-to-end proof on the toy library (DEC-2);
- every spec scenario mapped to a task and a test (tasks.md, Scenario map).

**Non-Goals:**
- the EPIC's no-gos;
- performance work beyond the toy library;
- any command-line tool other than `rp-generate`;
- documentation changes beyond those that tasks 1.11, 6.1 and 6.2 name.

## Decisions

New choices made while planning, grouped by topic; the numbers are stable ids, not an order. Settled
decisions are cited, not restated: EPIC DEC-1..DEC-6 and architecture D-1..D-13, O-1 and O-2.

### Layers and dependencies

- **PD-1 The layer contract.**
  - The scaffold orders the layers `entrypoints > services > adapters > domain`. The architecture puts
    ports in `services` and their implementations in `adapters`.
  - The contract becomes `entrypoints | adapters > services > domain`. `entrypoints` and `adapters`
    are independent siblings: neither imports the other.
  - The service kit needs token verification. It depends on the `TokenVerifier` port, which lives in
    `services`. The JWKS-based implementation, `JwksTokenVerifier`, is an adapter, and the consumer's
    composition root wires it in. The public API table in `index.adoc` already lists both.
  - `generation` and `testkit` sit outside the contract. The scaffold's empty `commons/` package is
    deleted (task 0.1): nothing needs a shared tier. The top-level `__init__.py` re-exports the
    public names.
  - A second contract forbids `domain` from importing `httpx`, `boto3`, `fastapi`, `jwt`,
    `pyshacl` and `anyio`. It sets `include_external_packages = True`.
  - A third contract forbids the four layers from importing `rdf_persistence.testkit`,
    `rdf_persistence.generation`, `pytest`, `testcontainers` and `linkml`: those come only with the
    extras, so a consumer's running service does not have them (stage 0 review).
- **PD-2 Dependencies (DEC-5).**
  - Runtime pins (`==`): `linkml-runtime`, `rdflib`, `pyld`, `pyshacl`, `pydantic`, `httpx`,
    `fastapi`, `pyjwt[crypto]`, `boto3`, `anyio`. Each is pinned to its latest release on the day
    task 0.2 runs, recorded in `uv.lock`; `linkml` is the exception (below). Test-group additions
    follow the same rule: `hypothesis` is pinned to its latest release on the day task 1.14 adds it.
  - An optional extra, `rdf-persistence[generate]`, brings `linkml==1.12.1`, so consumers' running
    services do not install the generators. `linkml-runtime` is pinned to the version that `linkml`
    1.12.1 resolves to in `uv.lock`.
  - `linkml==1.10.0` leaves the dev group. `make install` becomes `uv sync --all-extras`, so
    development and CI always have the generators.
  - The `rp-generate` script is always installed (a `[project.scripts]` entry cannot be limited to
    an extra). Without the extra, it exits with code 2 and the message
    "install rdf-persistence[generate]".
  - `boto3` calls run in a worker thread (`anyio.to_thread.run_sync`). Rejected: `aioboto3`, a second
    S3 stack to track.

### Store and session

- **PD-3 One SPARQL value function.**
  - `domain/sparql.py` holds `term(value) -> str`, covering IRIs, literals with datatype or language,
    and blank-node labels, and `fill(template, **terms)`.
  - Every query template is a module constant with `$name` placeholders, kept in the service that
    sends it (the session, tenancy); adapters forward SPARQL and build none. Only `domain/sparql.py`
    produces SPARQL text from values, including lists of terms (stage 2 review).
- **PD-4 Graph IRI.** `graph_iri(root_iri) = root_iri + "/graph"`, defined only in `domain/iris.py`
  (DEC-29).
- **PD-5 Version tokens.** Each commit writes a fresh random UUID as the version, never a counter.
  - Two sessions that read the same version therefore write different new tokens.
  - The loser's `ASK` for its own token is false: a conflict, never a false success.
- **PD-6 IRIs and paths.**
  - A tenant's IRI is `{base}{tenant_segment}/{uuid4}`. `base` and `tenant_segment` are given by the
    consumer; the toy library uses `libraries`.
  - An aggregate's IRI is `{tenant_iri}/{rp_path}/{uuid4}`.
  - `rp_path` is a required annotation on every aggregate root (the hard check enforces it), for
    example `rp_path: books`. There is no automatic plural.
  - The toolkit mints IRIs; clients never send them on create.
  - An owned part whose class includes `Described` is identified by an IRI too (its `id` stays
    required): the toolkit mints `{root_iri}/parts/{uuid4}` for a part that has none, and keeps it
    across commits. Only classes without an identifier slot (grants, prohibitions: PD-23) are
    blank nodes, skolemised on write (PD-8a). (Task 2.5.)
- **PD-6a Names.** `prefix` is the consumer's short name (lower case, at most 20 characters; the toy
  library uses `lib`, with `base` = `https://example.org/library/`).

  | Thing | Name |
  |---|---|
  | System database | `{prefix}-system` |
  | Tenant database and bucket | `{prefix}-t-{uuid hex}` (the tenant UUID without hyphens; a valid S3 bucket name) |
  | Tenant's metadata graph | `{tenant_iri}/meta` |
  | Tenant's registry graph | `{tenant_iri}/registry` |
  | Aggregate's graph | `graph_iri(root)` = `{root_iri}/graph` |
  | Loaded graph | `{aggregate_iri}/content/{uuid4}` |
  | Tenant access record (an aggregate of the system database) | IRI `{tenant_iri}/access`; graph `graph_iri` of it, `{tenant_iri}/access/graph` |

  The sweep considers only databases and buckets whose names start with `{prefix}-t-`.

  `TenantAccess` is an aggregate root, so it carries `rp_path: access` to satisfy the hard check.
  Its IRI is the one in this table, never minted from `rp_path` (task 1.3).
- **PD-7 Tracking on update.** `dcterms:created` and `dcterms:creator` are written by the first
  commit and kept. Every later commit replaces `dcterms:modified` and adds the committer to
  `dcterms:contributor`. All of these are statements about the graph IRI (D-7). Because a commit
  replaces the whole graph, the session reads the existing tracking statements with the aggregate and
  writes back `created`, `creator` and every earlier contributor. `Tracked` is a class mixin, so the
  generated classes carry these slots, but the mapper (task 2.5) reads and writes them as statements
  about the graph IRI, never the root, and the shapes ignore them (task 1.8).
- **PD-7a The session's two levels.** Graph level, for the router (task 2.3): `get_graph(iri)` →
  triples and version; `add_graph(iri, triples)`; `replace_graph(iri, triples, if_version)`;
  `remove(iri, if_version)`. Object level, for domain services, on the mapper (task 2.5):
  `get(cls, iri)`, `add(obj)`, then `commit()`, which calls the graph-level methods.
- **PD-8a Blank nodes and loaded graphs in a commit** (tasks 2.3, 2.4). The guarded update inserts its
  template once per matched row, so a blank node would be copied. The session therefore skolemises
  every blank node before a write, to `{graph_iri}/.well-known/genid/{uuid4}` (RDF 1.1 §3.5); readers
  see the skolem IRIs, and the mapper (task 2.5) and the frames nest them back as owned parts. Grants
  and prohibitions (PD-23) are written this way. `add_graph` and `replace_graph` take the aggregate's
  loaded graphs, so their registry entries are written in the same update (task 2.4). `remove`
  drops the loaded graphs with the aggregate, in the same update, so none is left orphaned; loading
  is `Session.load_graph`, which refuses an aggregate outside the session's tenant. A registry
  entry's subject is the graph IRI it describes; its `rp:kind` is the enum's meaning IRI.
- **PD-8 The registry and the tenant root.** The commit's update also deletes and inserts the
  aggregate's registry entries, one per graph it owns: its own graph and its loaded graphs. A
  `RegistryEntry` has `graph` (`rp:graph`), `kind` (`rp:kind`: `aggregate`, `loaded_graph`) and
  `owned_by` (`rp:ownedBy`: the root IRI).

  A tenant's root object (the toy `Library`) lives in `{tenant_iri}/meta`, which is its graph
  instead of `graph_iri(root)`. It is versioned and tracked the same way, with the statements made
  about `{tenant_iri}/meta`. It has no registry entry. Its IRI is the tenant IRI itself, it needs no
  `rp_path`, and the generic aggregate routes skip it: it is read and replaced through
  `GET`/`PUT /{tenant_segment}/{t}`, with action `modify` at tenant scope for the replace.

- **PD-8c Stage 2 review decisions.**
  - Parsing never fetches: a JSON-LD document whose `@context` is not inline is refused as
    `InvalidGraph` before parsing (no remote or `file:` context is followed).
  - A commit may name as loaded graphs only IRIs under `{iri}/content/` (PD-6a); `replace_graph`
    given no list keeps the loaded graphs already registered, so an edit through the unit of work
    never drops them.
  - `add_graph` is one conditional insert (`INSERT … WHERE { FILTER NOT EXISTS … }`) confirmed by an
    ASK, so two concurrent adds of one IRI cannot both succeed.
  - Tenancy validates the root and the access record before creating anything, so a refused request
    leaves nothing; deletion and the sweep use the record's stored `database_name`; `finish_deletion`
    acts only on a record in state `deleting`; tenant IRIs carry a canonical UUID.
  - The sweep never drops a resource when the system database had to be created at start-up or holds
    no access record while tenant resources exist: it logs and stops, since that means the records
    are missing, not that the tenants are orphans. The cost is accepted: a crash during the very first tenant's
    creation leaves its resources for an operator to remove.
  - The vocabulary (predicate IRIs, enum meanings) is read from the schema in `services`, keyed by the
    generated enums; nothing in `domain` restates it. The session returns the graph IRI it read, so the
    mapper never re-derives where tracking lives.
  - The top-level package exports lazily, so importing `rdf_persistence.domain` (as every consumer's
    generated module does) loads no adapter or service.
- **PD-8b Tenancy details** (tasks 2.6, 2.7). `Tenancy(store, files, settings, *, mapper,
  access_class, clock)`: it needs the mapper and the consumer's access class (the toy's
  `LibraryAccess`), which `install_service` derives from the schema. `create(label, root, creator)`
  mints the tenant IRI and replaces the root's `id` with it, so the caller's `id` is a placeholder;
  the access record's required `description` is derived from the label. Deletion and the sweep run as
  the principal `{base}toolkit`. The sweep is safe only before the service serves (the lifespan step
  of PD-13): a tenant another worker is creating at that moment would look orphaned.

### Access

- **PD-9 Where access data lives.**
  - **Grants, per-aggregate Permissions and Prohibitions** are owned parts of the tenant's access
    record, in its graph in the system database. They are therefore read in one query per request
    and changed by one guarded commit.
  - **Role definitions** are the consumer's data, not stored data. They are instances of
    `RoleDefinition` in a YAML file beside the consumer's access module, validated against
    `rp_access` at start-up and held in memory. A `RoleDefinition` has three slots:

    | Slot | IRI | Range |
    |---|---|---|
    | `role` | `rp:role` | string, required: a tenant role name, or a global role name from the token |
    | `level` | `rp:level` | enum `system`, `tenant`, `aggregate`, required: where the role applies (`system` only for global roles) |
    | `actions` | `rp:permits` | `Action`, multivalued, required |

    The toy library's `library_roles.yaml`:

    ```yaml
    - {role: admin, level: system, actions: [read]}
    - {role: librarian, level: tenant, actions: [read, modify, delete, administer]}
    - {role: reader, level: tenant, actions: [read]}
    ```
  - **Global roles** come from a configurable token claim, an object keyed by role name. For
    Zitadel it is `urn:zitadel:iam:org:project:{project_id}:roles` (checked on a live token in task
    3.3), so `ServiceSettings.roles_claim` has no default: each consumer sets its own project's claim.
  - The toy library's roles are `librarian` and `reader` per library, plus the global role `admin`.
  - Actions are `read`, `modify` and `delete` (ODRL), and `administer` (the toolkit's
    `rp:administer`: change the tenant's grants). Creating an aggregate is `modify` at tenant scope.
    Creating a tenant needs only a valid token; the creator gets the role named by the consumer's
    `creator_role` (toy: `librarian`).
  - Listing a tenant's aggregates needs `read` at tenant scope. A permission on one aggregate
    allows that aggregate only.
  - `modify`, `delete` and `administer` each imply `read` at the same scope.
  - A *tenant grant* is a grant whose target is the tenant IRI. A caller with no tenant grant, no
    permission on the requested aggregate and no global role that a role definition allows gets
    404. A caller with one of them, but without the
    action, gets 403. A matching Prohibition gets 403 before anything else.

  The toy library's matrix, which task 4.3 tests (`allow`, or the status returned):

  | Caller | read book | modify/create book | delete book | administer grants | delete tenant | list books |
  |---|---|---|---|---|---|---|
  | `admin` (global, `read` at system level) | allow | 403 | 403 | 403 | 403 | allow |
  | `librarian` | allow | allow | allow | allow | allow | allow |
  | `reader` | allow | 403 | 403 | 403 | 403 | allow |
  | direct `modify` permission on book B only | B: allow; others: 404 | B: allow; others: 404 | B: 403; others: 404 | 404 | 404 | 404 |
  | `reader` + direct `modify` permission on book B | allow | B: allow; others: 403 | 403 | 403 | 403 | allow |
  | `librarian` + Prohibition of `modify` on book B | allow | B: 403; others: allow | allow | allow | allow | allow |
  | no grant (outsider) | 404 | 404 | 404 | 404 | 404 | 404 |
  | anyone, tenant `deleting` | 404 | 404 | 404 | 404 | 404 | 404 |
- **PD-10 One grant model.** A `Grant` is an `odrl:Permission` with:
  - `assignee` (`odrl:assignee`): always a `Principal` in v1 (no party collections);
  - `target` (`odrl:target`): an IRI, either the tenant's or an aggregate's graph IRI. The scope
    level follows from which it is;
  - `role` (`rp:role`) for a role grant, or `action` (`odrl:action`) for a direct permission;
    exactly one of the two. `role` is a string matched against `RoleDefinition.role` (PD-9); no
    subclassing is needed, and an application does not narrow it to an enum: an enum value is stored as its meaning IRI, which a string-valued `role` cannot hold (task 1.8).

  The access record owns two collections: `grants` (`rp:grant`, role or direct-action grants) and
  `prohibitions` (`rp:prohibition`), both owned and multivalued. Grant targets are tenant or
  aggregate-graph IRIs only. The system level exists only through
  global roles in the token claim (PD-9): no system grants are stored. A `Prohibition` has the same
  `assignee` and `target`, and an `action`. Uniqueness: one grant per assignee, target and
  role-or-action, declared as `unique_keys: {grant_key: [assignee, target, role, action]}` (task 1.3);
  `generation.adoc#metamodel` (slot table) and `index.adoc#building-blocks` (Tenancy row) say the same.

### Single source of specification (developer, 2026-11-05)

The developer's rule, from the model-driven method of the
[MWBv2 Developer Runbook](https://meaningfy.atlassian.net/wiki/spaces/MR/pages/2107342856): the
domain is specified once, in LinkML, and every artefact that restates it is generated. Nothing that
restates the model is written or edited by hand. The rule is recorded as D-13 (task 1.11).

- **PD-24 What is generated, and what may be hand-written.**
  - Generated from LinkML: domain classes, SHACL shapes, the JSON-LD context and frames, TypeScript
    types, the OpenAPI component schemas (through `gen-json-schema`, inside the OpenAPI hook of task
    5.5) and the diagrams. A standalone JSON Schema file is not a v1 artefact.
  - The toolkit's own data types are declared in LinkML and generated too. `rp.yaml` imports
    neither of these schemas, so consumers' models do not carry them; each is its own
    `[[tool.rp-generate]]` entry (PD-18) and, like the metamodel, is exempt from the checks of PD-23:
    - `rdf_persistence/model/service/rp_service.yaml` (`module_kind: technical`; in its own folder, so the metamodel modules it imports are not treated as its own and regenerated with it): `ServiceSettings` (the
      `settings` of `install_service`: `base`, `prefix`, `tenant_segment`, `creator_role`,
      `roles_claim`), `VerifiedCaller` (what `TokenVerifier` returns: `principal`,
      `global_roles`), and the toolkit's own request and response bodies (PD-13: `TenantCreate`,
      `TenantSummary`, `LabelUpdate`, `GrantSet`, `Page`, `Problem`), generated into
      `rdf_persistence/domain/generated/service/`. `rp_service.yaml` imports `rp_core`,
      `rp_access` and `rp_tenancy` (for `TenantState`); `linkml:Any` is declared as a class `Any`
      with `class_uri: linkml:Any`, which gen-pydantic renders as `typing.Any`; `Problem`'s slots are
      `problem_type`, `problem_title`, ... with aliases `type`, `title`, ... (task 1.13); `GrantSet.grants` has range `Grant`; its run emits only its own classes and
      imports the others from `rdf_persistence.domain.generated`;
    - `rdf_persistence/generation/model/rp_generation.yaml`: `GenerationManifest`, `ConstraintCase`
      and `ClassShape` (PD-26, PD-27), generated into `rdf_persistence/generation/generated/`.
  - Stage 1 review (2026-11-05): every plain data record of `generation` and `testkit` (a file to
    write, a check problem, a flag, a presence alternative, a template view-model, a guard
    violation) is declared in `rp_generation.yaml` and generated. Hand-written types remain only
    where a field holds a foreign runtime object LinkML cannot express (a `SchemaView`, a callable,
    an rdflib graph) or where the type subclasses a LinkML generator or template class; each is
    named in the model guard's allow-list (PD-28). The annotation vocabulary (`owned`, `internal`,
    `graph`, `database`, `module_kind`, `rp_path`, `rp_unlabelled`, and `bookkeeping` for the
    slots the shapes ignore) and its value sets are generated enums, never free strings.
  - Hand-written, because it restates nothing: generic code that reads the schema through
    `SchemaView` at run time (the mapper, the router), the strict base `RpModel`
    (`domain/base.py`), the generator extensions and templates, exception classes, and
    infrastructure types in `testkit` and `adapters` (such as a container's endpoint), which are
    not domain data.
  - A rule the schema declares is enforced by both the generated classes and the generated shapes.
    Stock `gen-pydantic` enforces neither `exactly_one_of` nor `unique_keys`, and stock `gen-shacl`
    translates neither, so the toolkit extends both:
    - classes (task 1.13): `exactly_one_of` and `any_of` become a model validator on the class that
      declares them; `unique_keys` becomes a model validator on every class with a multivalued slot
      whose range declares them (for example `TenantAccess`, over `grants`), refusing two items with
      equal key values. An absent slot counts as a key value, and two absent values are equal (the
      grant key spans `role` and `action`, one of which is always absent); the SPARQL constraint of
      the shapes treats absent values the same way;
    - shapes (task 1.8): `exactly_one_of` becomes `sh:xone`, `any_of` becomes `sh:or`, and
      `unique_keys` becomes a SPARQL constraint on the owning class.
    - shapes are named by the class's native IRI (two classes may share a `class_uri`, such as
      `odrl:Permission`), and a non-owned slot that refers to another aggregate is checked as an
      IRI only (no `sh:node` or `sh:class`), so an aggregate's graph validates without the
      aggregates it refers to (task 1.8);
    - The context and the shapes agree on what a value is (found by the conformance suite, task
      1.14): a class with an identifier slot gets `sh:nodeKind sh:IRI` on its node shape, so an
      instance without an IRI is refused; `uri` and `uriorcurie` slots get `"@type": "@id"`; an
      enum-ranged slot gets `"@type": "@vocab"` and a property-scoped context mapping each value to
      its `meaning`, so values are stored as their meaning IRIs and compact back to their keys
      (the context declares `"@version": 1.1`); an enum gives every value a `meaning` or none, and a
      mixed enum is a generation error. Slots annotated `internal` are optional in the
      shapes: the public context leaves them out (PD-12), the toolkit writes them, and the mapper's
      tests check they are present.
    - `unique_keys` is enforced on multivalued slots holding objects (inlined, or a range without
      an identifier); a slot of references by IRI carries no key slots to compare (task 1.13).
    - `rules` (LinkML's pre- and postconditions), `all_of` and `none_of` are not supported in v1:
      the generated code would ignore them, so `rp-generate` exits 1,
      naming the class, if a schema uses it.
- **PD-25 Extending the generators.** Every gap in a stock LinkML generator is closed by an
  extension in `rdf_persistence/generation/`: a subclass or a template, never a patch to generated
  output. Each extension has a row in the extension table of `generation.adoc` (what the stock
  generator lacks, what the extension adds) and a golden test on the toy schema. A test fails if an
  extension module has no row or no test.
- **PD-26 Freshness and drift.**
  - `rp-generate` writes one manifest per `[tool.rp-generate]` entry, `rp-manifest.json` in the
    table's `python` folder. Its model is `GenerationManifest` (PD-24): `linkml` (the version
    string), `inputs` and `outputs`, each a list of entries with `path` and `sha256`.
    - Paths are POSIX, relative to the folder of the `pyproject.toml`; hashes are over the raw
      bytes; entries are sorted by path.
    - Inputs also include every `services/schema*.py` module, since they decide how a schema is
      read (stage 1 review).
    - Inputs: every file of `load_schema(schema)`'s import closure (the metamodel resolved through
      PD-22; `linkml:types` is covered by the `linkml` version instead), every file of the template
      directories, and every `.py` module under `rdf_persistence/generation/` except those under
      `rdf_persistence/generation/generated/`.
    - Outputs: every file the run wrote, in every target folder (Python, TypeScript, diagrams),
      except the manifest itself. A run deletes only the files its previous manifest lists; it never
      clears a folder, so nested output folders (`domain/generated/service/`) are safe.
    - An input inside the installed `rdf_persistence` package is recorded as
      `rdf_persistence/<path within the package>`, so a consumer's manifest does not depend on
      where the package is installed.
    - A manifest whose `linkml` differs from the installed version means *stale*.
    - Without the `generate` extra, `--check` and the pytest plugin do only the manifest
      comparison: lint and the checks are skipped and the `linkml` version is not compared (hashing
      needs only `linkml-runtime`); a regeneration needs the extra (PD-2). The plugin always does
      only the manifest comparison; the full `--check` runs in `make check-quality`.
  - `rp-generate --check` recomputes both. A changed input means *stale*; a changed output means
    *edited by hand*. Either exits 1, naming the files and the command that fixes them.
  - The check runs in four places:
    - `make check-quality`, so before every PR and in CI;
    - the start of every pytest session: the plugin `rdf_persistence/testkit/freshness.py` checks in
      `pytest_sessionstart` and stops the run with `pytest.exit(..., returncode=1)` when anything is
      stale or edited. A consumer enables it with `pytest_plugins =
      ["rdf_persistence.testkit.freshness"]` in its root conftest. It reads the `pyproject.toml`
      files listed in the ini option `rp_generate_projects` (default: the rootdir's); this repo lists
      its own `pyproject.toml` (whose three `[[tool.rp-generate]]` entries generate the toolkit's schemas)
      and `tests/fixtures/library/pyproject.toml`;
    - a local pre-commit hook, `rp-generate-check`, with `files:
      ^(rdf_persistence/(model|generation)/|tests/fixtures/library/|.*/generated/)`; it replaces the
      "Ruff only" note in `.pre-commit-config.yaml`;
    - `make check-generated` in CI, which regenerates from scratch and diffs, catching what a hash
      cannot (a generator that is not deterministic).
  - Generation is part of the build: `make generate` regenerates everything, and `make build` runs
    it first.
- **PD-27 Correctness of the generated code.**
  1. *Schema gates first*: `linkml-lint` with the raised rules, then the hard and boundary checks;
     nothing is generated from a schema that fails them.
  2. *Golden tests per extension*: RDF output compared by graph isomorphism, other output as exact
     text, and the set of files compared exactly. For the toy library the golden is the committed
     generated tree itself; separate goldens exist only for schemas that are not the toy.
  3. *Cross-artefact conformance*:
     - The cases live in `tests/fixtures/conformance/cases.yaml`, as `ConstraintCase` rows: `kind`,
       `class_name`, `valid` and `invalid` (paths of instance files beside it, in YAML).
     - The constraint kinds of v1: `required`, `cardinality` (`minimum_cardinality`,
       `maximum_cardinality`), `range_type`, `range_enum`, `pattern`, `value_bounds`
       (`minimum_value`, `maximum_value`), `identifier`, `closed` (an unknown field or predicate),
       `exactly_one_of`, `any_of` and `unique_keys`.
     - For every case, the generated class and the generated shape must accept `valid` and refuse
       `invalid`.
     - Coverage: the kinds used by a schema (read from `SchemaView`: the metaslots set on its
       induced slots and its classes) minus the kinds that have at least one row must be empty;
       otherwise the test fails, naming the missing kinds.
     - A consumer runs it on its own schema with `testkit.conformance.run(schema, cases)`.
  4. *Round trips* (strategies in `testkit`, run on the toy library's aggregates and the
     metamodel's `TenantAccess`; equality is on the public projection, since internal slots never
     cross the context): an instance goes to JSON, is expanded with the generated context to RDF, then
     framed and compacted back. Equal means the generated objects compare equal and the two RDF
     graphs are isomorphic. Hypothesis (pinned in the test group, PD-2) draws the instances with
     strategies built from `SchemaView`: required slots always, optional ones by draw; values by
     range (text, integers, dates, enum values, IRIs under a fixed base); owned parts to depth 2.
  5. *Model shape*: for every generated class, the pydantic fields match `SchemaView`'s induced
     slots (name, required and multivalued; the range is held by the snapshot of item 6, since
     LinkML ranges and pydantic types do not map one to one). Both read the schema *after* PD-11's
     defaults, as the generators do. This compares the generated code with the *current* schema, so it catches stale or edited code even without the manifest.
  6. *A model change fails the tests until acknowledged* (runbook): `tests/fixtures/model-shape.yaml`
     holds the reviewed shape of every class of the metamodel and the toy library, as `ClassShape`
     rows (`class_name`, then `slots`, each with `name`, `required`, `multivalued`, `range`). The
     test compares the current schema with this *last reviewed* shape, so any model change, intended
     or not, fails it until `make refresh-snapshot` rewrites the file and the diff is reviewed in the
     PR.
  7. *Generated code compiles*: every generated Python module imports cleanly and passes
     `uv run mypy --config-file mypy-generated.ini` (since PD-19 excludes generated folders from the
     main run). The profile sets `plugins = pydantic.mypy`, `check_untyped_defs = True`,
     `ignore_missing_imports = True`, `warn_unused_ignores = False` and `disallow_untyped_defs =
     False`, and checks only the generated folders; the TypeScript output
     passes `npx -y typescript@5.9.3 tsc --noEmit --strict` in CI.
- **PD-28 Guards against hand-written models.**
  - The model guard parses every module of `domain`, `services` and `entrypoints` with `ast`,
    skipping any path with a `generated` segment. It fails, naming the class, on a class deriving
    from `pydantic.BaseModel`, `rdf_persistence.domain.base.RpModel`, `enum.Enum`, `enum.StrEnum`,
    `enum.IntEnum`, `typing.TypedDict` or `typing.NamedTuple`, or decorated with
    `dataclasses.dataclass`. Names are resolved through each module's imports, aliases included
    (`import pydantic as p`, `from enum import Enum as E`). The only default exception is `RpModel`
    in `rdf_persistence/domain/base.py`; a consumer passes its own with `allow=`.
  - The file guard fails on `*.shacl.ttl`, `*shapes*.ttl`, `*.context.jsonld`, `*.frame.jsonld`,
    `*.schema.json`, `openapi*.json`, `openapi*.yaml` and `*.ts` (except `*.test.ts` and
    `*.spec.ts`) anywhere in the scanned roots outside a folder named `generated`. This repo scans
    `rdf_persistence/` and `tests/`, with `tests/fixtures/` exempt (instance data and request
    bodies).
  - Both are `testkit.assert_models_generated(package, *, roots, allow=())`, so consumers get them
    too. In this repo the model guard also scans `generation` and `testkit`, with the allow-list of
    PD-24's foreign-object types.
  - Patterns are fully anchored on both sides (stage 1 review): the classes use `fullmatch`, and
    the shapes wrap each pattern as `^(?:P)(?![\s\S])`, because `$` in pyshacl's and Java's regex
    accepts a final newline. The look-ahead is outside the XPath regex syntax SHACL names, but both
    validators the toolkit targets (pyshacl, Jena) accept it.
  - `rp-generate` validates its own inputs (stage 1 review): manifest paths are relative POSIX paths
    without `..` and hashes are 64 hex digits; a run removes a listed file only if it lies under the
    project and still has its recorded hash; configured folders are relative, without `..`; the
    package is a dotted identifier; every staged file must stay inside the staging folder.

### Generation

- **PD-18 The `[tool.rp-generate]` table.** Paths are relative to the directory of the
  `pyproject.toml`. Each key has a command-line flag that overrides it. The key holds one table,
  or an array of tables `[[tool.rp-generate]]`; each entry is one run with its own manifest
  (PD-26). This repo's `pyproject.toml` has three entries: `rp.yaml` into `domain/generated/`,
  `rp_service.yaml` into `domain/generated/service/`, and `rp_generation.yaml` into
  `generation/generated/`.
  The `schema` key is the field `schema_file` of `GenerationTarget` (a slot named `schema` would
  shadow a pydantic method); the TOML key and the `--schema` flag stay `schema`. Radon cannot read a
  `pyproject.toml` holding a `[[tool.*]]` array, so the Radon and Xenon targets run from inside the
  package folder (task 1.5).

  | Key | Flag | Default | Meaning |
  |---|---|---|---|
  | `schema` | `--schema` | required | root schema file |
  | `package` | `--package` | required | Python import path of the generated package |
  | `python` | `--python-out` | the folder of `package` | classes, shapes, context, frames, schema copy |
  | `typescript` | `--typescript-out` | not written | TypeScript types |
  | `diagrams` | `--diagrams-out` | not written | one Mermaid file per module |
  | — | `--check` | off | write nothing: run lint, the hard and boundary checks, then the manifest comparison of PD-26; exit 1 on a failed check, a stale input or an edited output |
- **PD-19 Reproducible output.** Generator metadata that changes between runs (generation dates,
  generator versions) is switched off in every generator call. Generated folders (`**/generated/**`)
  are excluded from Ruff and mypy in their config files, and from Xenon by an `--exclude` flag on
  the `clean-code` target in the `Makefile` (Xenon has no config file). `make check-generated` regenerates
  every entry (the toy library and the three toolkit schemas) and fails on any difference; CI runs
  it.
- **PD-20 Boundary checks on code.** `docs/tools/check_docs.py` also scans `rdf_persistence/` and
  `tests/` for consumer terms, and `make check-quality` runs it. The end-to-end test uses
  `testkit.assert_public_imports(path)`, which parses a test file's imports with `ast` and fails on
  any `rdf_persistence.<sub>` import other than `rdf_persistence.testkit`.
- **PD-21 Shared metamodel classes.** `Principal` lives in `rp_core`, so `rp_access`,
  `rp_provenance`, `rp_tenancy` and `rp_files` can all use it; its `class_uri` is `prov:Agent`, with
  `odrl:Party` as an exact mapping. `TenantAccess` includes `Described`, so the tenant's label is
  the one `label` slot (`skos:prefLabel`); there is no `dcterms:title` slot in the metamodel.
- **PD-22 Importing the metamodel.** Application modules import metamodel modules as
  `rdf_persistence/model/<module>`. `rdf_persistence/services/schema.py` has `load_schema(path)`
  (in `services`, so the mapper may use it under PD-1; `generation` imports it from there). The
  rules that read a schema's aggregate structure (roots, the tenant root, owned and internal
  slots, PD-11's defaults, the presence alternatives and keyed slots of a class) live beside it in
  `services`, once, and `generation`, `testkit` and the mapper all use them. It opens a
  schema with `SchemaView` and an import map from that prefix to the installed package's `model/`
  folder. `rp-generate`, the mapper and the tests load schemas only through it; a unit test loads
  every toy library schema with it.
- **PD-23 What the hard and boundary checks cover.** The checks of tasks 1.6 and 1.7 apply to the
  classes the application's modules define. The metamodel's own classes are exempt (the toolkit's
  tests cover them), and so are an application class's slots and rules inherited from them; for
  example, `LibraryGrant` (`is_a: Grant`) needs no `Described`. Grants and prohibitions stay blank
  nodes. A class reached only by IRI (`Principal`, `Activity`) is a reference, not a part.
  The checks recognise the toolkit's own schemas by location: a schema file inside the installed
  `rdf_persistence` package. The reference classes are exactly `Principal` and `Activity` (and their
  subclasses); a non-owned slot ranging over any other metamodel class fails. The module-kind rule
  looks at a module's direct imports only (task 1.7).
- **PD-11 Unlabelled classes.** Before running the generators, `rp-generate` gives every class
  annotated `rp_unlabelled: true` a `slot_usage` of `{label: {required: false}}`. `rp_unlabelled` relaxes only the label: the class still includes `Described`, so it keeps `id` and `description`. The generated
  classes and shapes then agree, with no separate change to the shapes generator. In the same
  step it gives every aggregate root a `slot_usage` of `{description: {required: true}}`, as the
  rp-metamodel requirement asks (tests in tasks 1.6 and 1.8).
- **PD-12 Frames.** One JSON-LD frame per aggregate type nests owned parts under their root. It is
  generated in step 5 and placed beside the context.

### API

- **PD-13 Routes are tenant-scoped.**
  - Tenants: `/{tenant_segment}` (list mine, create) and `/{tenant_segment}/{t}` (read, delete),
    where `{t}` is the tenant IRI's UUID.
  - Aggregates: `/{tenant_segment}/{t}/{rp_path}` (list, create) and
    `/{tenant_segment}/{t}/{rp_path}/{id}` (read, replace, delete).
  - The consumer mounts the router under its own prefix. For the toy library this gives
    `/libraries/{t}/books/{id}`.
  - Tenant routes in detail:
    - `GET /{tenant_segment}`: the tenants where the caller has a grant (all, for a global `read`);
    - `POST /{tenant_segment}`: create a tenant, as in PD-9;
    - `GET` and `PUT /{tenant_segment}/{t}`: the tenant's root object (PD-8), with its `ETag`;
    - `DELETE /{tenant_segment}/{t}`: `If-Match` on the access record, action `delete`;
    - `GET` and `PUT /{tenant_segment}/{t}/grants`: the grant set, `If-Match` on the access record,
      action `administer`; `GET` returns the access record's `ETag`, which `DELETE` and `PUT …/label`
      use;
    - `PUT /{tenant_segment}/{t}/label`: the tenant's label in the access record, `If-Match` on the
      access record, action `modify`.
  - Bodies and construction. The tenant-route bodies, `Page` and `Problem` are classes of
    `rp_service.yaml`, generated (PD-24); the router validates them and builds them through these
    classes, never through bare dicts. Aggregate bodies stay JSON-LD, handled as in PD-14.
    `Page.items` has range `linkml:Any` and holds framed aggregates (or `TenantSummary` objects, for
    `GET /{tenant_segment}`). `TenantCreate.root` has range `linkml:Any`; it and the body of
    `GET`/`PUT /{tenant_segment}/{t}` are the tenant root, handled as in PD-14:

    | Route | Request body | Response |
    |---|---|---|
    | `POST /{tenant_segment}` | `{"label": "…", "root": {…the tenant root's slots…}}` | 201, `Location`, `{"id", "label", "state"}` |
    | `PUT …/{t}/label` | `{"label": "…"}` | 200, new `ETag` |
    | `PUT …/{t}/grants` | `{"grants": [{"assignee", "target", "role" or "action"}], "prohibitions": [{"assignee", "target", "action"}]}` | 200, new `ETag`; 422 `invalid-body` on an unknown role or a duplicate key |
    | aggregate routes | the aggregate (PD-14) | the aggregate |

    The consumer's composition root calls
    `install_service(app, *, schema, store, files, identity, verifier, rules, settings, prefix="")`
    on its FastAPI app. It does three things:
    1. mounts the router;
    2. registers exception handlers that turn every toolkit error into a problem response
       (`application/problem+json`), so routes the consumer writes itself get the same answers
       (for example `InvalidGraph` → 422, `TenantGone` → 404, `IdentityUnavailable` → 503);
    3. adds a lifespan step that runs, before the app serves: create the system database if
       missing, then load and validate the role definitions, then the sweep.

    `settings` is a `ServiceSettings` (generated from `rp_service.yaml`, PD-24) holding `base`,
    `prefix`, `tenant_segment`, `creator_role` and `roles_claim`; the verifier returns a
    `VerifiedCaller`, generated from the same module. The
    JSON-LD context is served at `/context.jsonld` under the mount. Upload, graph loading and account
    administration are library calls for the consumer's own routes, not routes of the toolkit.

    Adapter constructors: `FusekiStore(url, user, password)`,
    `S3FileStore(endpoint, access_key_id, secret_access_key, region)`,
    `ZitadelIdentity(issuer, service_token, organisation_id, project_id)` (global roles are project-role
    grants),
    `JwksTokenVerifier(issuer, audience, roles_claim, *, jwks_uri=None, http_client=None)`: keys come
    from the issuer's OIDC discovery unless `jwks_uri` is given; the testkit passes an `http_client`
    that serves its in-memory JWKS.
- **PD-14 Body handling.**
  1. A JSON body is expanded with the generated context; a JSON-LD body is used as is. Either way it
     becomes triples whose root is the IRI from the path (on create, the minted IRI).
  2. The triples are validated against the type's shape.
  3. The session replaces the graph.
  4. The response is built from the stored graph: framed and compacted with the context for JSON
     and JSON-LD, serialised for Turtle.

  The generated classes are not used on this path (D-2). A replace whose body `id` differs from the
  path is refused (422 `invalid-body`).
- **PD-15 Problems and sorting.**
  - Problem `type` IRIs are `{base}problems/{slug}`, with these slugs: `invalid-token`, `forbidden`,
    `not-found`, `conflict`, `precondition-required`, `invalid-body`, `not-acceptable`,
    `unsupported-media-type`, `bad-query`, `unavailable`.
  - Each slug has a fixed `title`: "Invalid token", "Forbidden", "Not found", "Version
    conflict", "Precondition required", "Invalid body", "Not acceptable", "Unsupported media
    type", "Bad query", "Service unavailable".
  - Listings sort by IRI ascending unless `sort=<slot>` or `sort=-<slot>` is given.
  - Filters are query parameters `?<slot>=<value>`; repeated parameters on different slots combine
    with AND. `limit` defaults to 50 and is at most 200. `GET /{tenant_segment}` is paged the same
    way.
  - Cached JWKS keys are kept for 10 minutes; an unknown `kid` triggers one refresh.

### Tests

- **PD-16 Test containers.** `rdf_persistence/testkit/containers/compose.yaml` defines three
  containers:
  - **Fuseki**: built from Apache Jena's `jena-fuseki-docker` Dockerfile at the latest Jena 5.x
    release, pinned in task 0.4. Apache publishes the Dockerfile, not an image, so it is vendored in
    `rdf_persistence/testkit/containers/fuseki/`. A
    `shiro.ini` admits one test user, on every endpoint.
  - **Garage**, pinned by digest. The fixture bootstraps it with `garage layout assign`,
    `garage layout apply` and `garage key create`, through `docker exec`.
  - **Zitadel with Postgres**, pinned by digest. It starts with `ZITADEL_FIRSTINSTANCE_*`
    variables that create an admin machine user and write its personal access token to a mounted
    file. The fixture uses that token only to provision, through the management API:
    - a project with the role `admin`;
    - one machine user per test principal (librarian, reader, outsider, admin), each with a key for
      the private-key JWT flow and the access-token type *JWT* (a machine-user setting in Zitadel;
      by default it issues opaque tokens, which a JWKS check cannot verify). The `admin` user holds
      the global role `admin`. No API application is needed (task 3.3).

    Tests get tokens with the JWT-profile grant, requesting the scopes `openid`,
    `urn:zitadel:iam:org:project:id:{project}:aud` and
    `urn:zitadel:iam:org:projects:roles`, so the token carries the audience and the roles claim.
    No human user is needed: Zitadel has no password grant. Personal access tokens are opaque, so
    they are not supported in v1 (`access-control.adoc#identity`).

  Markers stay assigned by path in `tests/conftest.py`. Its hook is rewritten to apply every marker
  of a directory's row, not only the first:

  | Directory | Markers |
  |---|---|
  | `tests/unit/`, `tests/feature/` | `unit` / `feature` |
  | `tests/integration/store/`, `tests/integration/api/` | `integration`, `store` |
  | `tests/integration/tenancy/` | `integration`, `store`, `files` |
  | `tests/integration/files/` | `integration`, `files` |
  | `tests/integration/identity/` | `integration`, `identity` |
  | `tests/e2e/` | `e2e`, `store`, `files`, `identity` |

  The fixtures in `rdf_persistence/testkit/containers/` start the containers a marker needs. That
  folder ships as package data with the compose file and the vendored Fuseki Dockerfile, so
  consumers get the same fixtures. It is imported lazily and needs the extra
  `rdf-persistence[testkit]` (`testcontainers`); without it, importing the fixtures raises an
  error that names the extra. The marker names live in `rdf_persistence/testkit/markers.py`, which
  needs no extra; the fixtures plugin registers them, and only `tests/integration/` and `tests/e2e/`
  load the plugin, so the unit lane runs without `testcontainers`.
  - `make test` runs `unit or feature` with the 80% coverage floor. `.coveragerc` omits
    `rdf_persistence/adapters/*` and `rdf_persistence/testkit/containers/*` from that floor.
  - `make test-containers` runs `integration or e2e` with `--cov-fail-under=0`, reporting coverage
    without a floor, in a separate CI job.
  - The tenancy tests take the file store from a parametrised fixture: the fake in stage 2, and
    Garage added as a second parameter in task 3.1.
  - The router's unit tests use the fake session, and the session and tenancy logic also get unit
    tests on the fake store, so they count toward the floor.
  - A new CI workflow runs on changes under `docs/**` (which the main workflow ignores): it runs
    `make check-docs` and the Antora build.
- **PD-17 The toy library.** `tests/fixtures/library/` holds:
  - `library.yaml`, the root schema;
  - three domain modules: `library_tenant` (`Library`, the tenant root), `books` (`Book` with owned
    `Chapter`, which owns `Note` and is marked `rp_unlabelled`) and `scans` (`Scan`, with
    `StoredFile`);
  - `library_access.yaml` (`module_kind: access`), with `library_roles.yaml` holding the role
    definitions of PD-9's matrix;
  - `partial.yaml`, a schema importing only `rp_core` and `rp_annotations`;
  - a `pyproject.toml` fragment with the `[tool.rp-generate]` table.

  Its generated output is committed under `tests/fixtures/library/generated/`, and CI checks it is
  fresh.

## Algorithm / approach

### Stage order and what each stage proves

| Stage | Builds | Proven by |
|---|---|---|
| 0 Ground | layer contract, dependencies, toy library, containers | `make check-quality`; container smoke tests |
| 1 Metamodel and generation | six modules; `rp-generate` with checks, seven steps and placement | the toy library generates; planted faults fail, naming the element |
| 2 Store, session, tenancy | store port and Fuseki adapter, session, registry, loading, mapper, tenancy, sweep | integration tests against Fuseki |
| 3 Files and identity | file store and S3 adapter, token verification, identity port and Zitadel adapter | integration tests against Garage and Zitadel |
| 4 Access | permission loading and the check | the role-matrix test |
| 5 Service kit and router | router, negotiation, ETags, problems, listing, OpenAPI | the end-to-end test |

### Worked example: a guarded commit

The session holds `<g>` = `graph_iri(<b>)`, the version `"7f3a…"` it read, and the tracking
statements read with it (`created`, `creator <p0>`, contributors). The new token is
`"c91e…"`, a fresh UUID. It sends one update:

```sparql
DELETE { GRAPH <g> { ?s ?p ?o } . GRAPH <registry> { ?e ?ep ?eo } }
INSERT { GRAPH <g> { …new triples…
                     <g> rp:version "c91e…" ; dcterms:modified "…"^^xsd:dateTime ;
                         dcterms:created "…" ; dcterms:creator <p0> ; dcterms:contributor <p1>, <p> }
         GRAPH <registry> { …entries for <g> and its loaded graphs… } }
WHERE  { GRAPH <g> { <g> rp:version "7f3a…" . ?s ?p ?o }
         OPTIONAL { GRAPH <registry> { ?e rp:ownedBy <b> ; ?ep ?eo } } }
```

Since the stage 2 review the update is one request of several operations separated by `;` (one
transaction in Fuseki), each carrying the version guard in its `WHERE`: first the loaded graphs, then
the registry entries, and last the aggregate's triples with the new version. One combined `WHERE`
would multiply the aggregate's triples by its registry entries and loaded-graph triples. A loaded
graph is exactly `{root}/content/{uuid}`, and only an aggregate IRI of the minted form, the tenant
root, or the tenant's access record `{tenant}/access` (its IRI is fixed by PD-6a) may be written.

It then asks `ASK { GRAPH <g> { <g> rp:version "c91e…" } }`. True means the commit happened.
False means a conflict: Fuseki answers 204 even when `WHERE` matched nothing. A new aggregate uses
`INSERT DATA`, after an `ASK` that `<g>` does not exist. Random IRIs make a race on the same new IRI
practically impossible.

### Worked example: `PUT /libraries/{t}/books/{id}` with `If-Match: "7f3a…"`

1. The `TokenVerifier` gives principal `<p>` and global roles `[]`. The route declares `modify`.
2. The access check loads, in one query, the grants and prohibitions of `<p>` in tenant `<t>`'s
   access record, then applies PD-9's rules in order:
   - a tenant that is not `active` means 404;
   - a Prohibition on `modify` for the tenant or for `graph_iri(<book>)` means 403;
   - no tenant grant, no permission on the book and no global role a role definition allows means
     404;
   - a role definition of one of `<p>`'s tenant roles, or a direct permission on the book, that
     permits `modify` (or an action implying it) means allow;
   - otherwise 403.
3. The body is expanded and validated (PD-14), then the session commits under `"7f3a…"`.
4. The response is 200 with `ETag: "c91e…"`.

### Idempotency and retries

- **Commits** are not blindly retryable. A replay after a lost response gets 409, because the
  version has moved; the client re-reads.
- **Tenant creation** writes the access record last. A retry after a failure creates a new tenant,
  and the sweep removes the orphan.
- **Tenant deletion** is idempotent: a `deleting` record is finished by any later attempt, or by the
  sweep.
- **Blob puts** use a fresh key each time, so a retry leaves at most an orphan, erased with its
  tenant.
- **`rp-generate`** writes to temporary files and moves them into place on success, so it is safe to
  re-run.

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Format SPARQL with f-strings | `fill()` with `term()` (PD-3) | Injection; one place to audit |
| Use the root IRI as a graph name | `graph_iri()` (PD-4) | DEC-29 |
| Use a counter as the version | A fresh UUID per commit (PD-5) | A counter gives false successes |
| Accept client-sent IRIs on create | Mint them (PD-6) | IRIs stay in the toolkit's namespace |
| Generate routes or repositories | The generic router reads `SchemaView` at run time | O-1, D-1 |
| Use generated *domain* classes for aggregate bodies in the router | Context, frame and shapes (PD-14) | D-2 |
| Import an adapter in `services`, `domain` or `entrypoints` | Depend on the port; the consumer wires the adapter | PD-1 |
| Mock Fuseki, Garage or Zitadel in integration tests | Containers (PD-16) | DEC-4 |
| Edit generated files | Change the schema or template; regenerate | Freshness check (PD-26) |
| Hand-write a model, shape, context or API schema | Declare it in LinkML; extend a generator if needed | PD-24, PD-28 guards |
| Put a consumer term in code, tests or architecture pages | Toy library terms | `rp-package-boundaries` |
| Add a login endpoint | The provider's flows | D-10 |

## Error matrix

| Failure mode | How it is detected | Expected handling |
|---|---|---|
| Stale `If-Match`, or the guard matched nothing | `ASK` for the new token is false | `Conflict` → 409 `conflict`; nothing changed |
| `If-Match` missing on update or delete | Service kit | 428 `precondition-required` |
| Unknown tenant, type or id | Router, session | 404 `not-found` |
| Body fails the shape, or a client sent an IRI on create | pySHACL report; router | 422 `invalid-body` with the report's messages |
| `Accept` not JSON, JSON-LD or Turtle | Router | 406 `not-acceptable` |
| `Content-Type` not JSON or JSON-LD | Router | 415 `unsupported-media-type` |
| Unknown filter slot, bad `limit`/`offset`, or unknown sort slot | Router | 400 `bad-query` |
| RDF file does not parse | rdflib | 422 `invalid-body` with the parser's message; no graph |
| Token missing, expired, wrong issuer or audience, or bad signature | `TokenVerifier` | 401 `invalid-token`; the JWKS is refreshed once on an unknown `kid` |
| The provider's JWKS is unreachable | httpx error | 503 `unavailable` once cached keys expire; until then, cached keys |
| Caller not permitted | Access check | 403 `forbidden`, or 404 `not-found` with no grant or an inactive tenant |
| The store is unreachable or answers 5xx | httpx error | 503 `unavailable`; no retry inside the request |
| The tenant database is gone mid-request (Fuseki 405) | Store adapter | `DatabaseGone` → 404 `not-found` |
| The object store is unreachable | botocore error | 503 `unavailable`; metadata not committed (blob before metadata) |
| Put into a missing bucket | `NoSuchBucket` | `TenantGone` → 404; no bucket created |
| Crash between tenant steps | Start-up sweep | Finish `deleting`; drop unnamed databases and buckets |
| Role definitions file invalid | Validation at start-up | The service refuses to start, naming the entry |
| `PUT …/grants` with an unknown role or a duplicate key | Validation against `rp_access` | 422 `invalid-body`; the access record is unchanged |
| The identity provider's management API is unreachable or answers 5xx | httpx error in the Zitadel adapter | `IdentityUnavailable` → 503 `unavailable` |
| No account for an email | Zitadel adapter | `NotFound` → 404 `not-found` |
| Schema fails the hard or boundary check | `rp-generate` | Exit 1, naming each element; outputs untouched |
| Generated output stale | `rp-generate --check` (manifest), at session start, in `check-quality`, pre-commit; CI regenerates and diffs | Exit 1 naming the stale files and `make generate` |
| Generated output edited by hand | Output hash differs from the manifest | Exit 1 naming the edited files |
| Generated classes and shapes disagree on a constraint | Conformance suite (PD-27) | Test fails naming the constraint case |
| A LinkML bump breaks an extension | Extension tests on the toy schema | Fix the extension, or hold the pin |

## Risks / Trade-offs

- [pySHACL on every write is slow] → Toy-sized aggregates; the parsed shapes graph is cached. If one
  write in the end-to-end test exceeds 200 ms, record it in `api.adoc` as a finding.
- [Framing nested owned parts grows complex] → One generated frame per type (PD-12), tested on
  `Book → Chapter → Note`.
- [Zitadel is heavy in CI] → Only the identity suite and the end-to-end suite need it (PD-16), in
  the container job.
- [Generator extensions break on LinkML releases] → Exact pins (PD-2) and extension tests.
- [The filter grammar grows] → Equality, `limit`, `offset` and one sort key (EPIC rabbit-hole).

## Open Questions

None. One choice is left to a task, and its outcome is recorded in the architecture: whether
linkml-openapi can replace the OpenAPI hook (spike 5.6).
