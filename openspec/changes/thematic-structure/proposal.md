<!-- Parents: openspec/specs/rp-package-boundaries (layers import downward only; consumers use the
     public API only); openspec/specs/rp-generation (LinkML is the single source; each artefact goes
     to its declared place); toolkit-v1-foundation PD-1, PD-18, PD-26; changes technical-models
     (Q-2, the kinds of schema) and generator-package (F-4, DEC-7 python_package). Seeds:
     inputs/seed.md, which points at ../manual-revision-notes/inputs/{seed,answers-2026-11-17,
     improvements,analysis,keep}.md (E-1 to E-6, Q-2, analysis §2.1, §2.3, §5.3). -->

# EPIC: Thematic modules

> Shaped 2026-11-17 from the developer's notes and answers (Q-2). **Position: 5th** of the five
> changes of the `manual-revision-notes` initiative, plus `ldes-view` later. Depends on
> `technical-models` (technical schemas kept apart from domain schemas, each generated into the
> `generated/` folder of the lowest layer that uses it, and `iris.py` already split) and
> `generator-package` (F-4: the package a schema module is generated into is declared, not
> hard-coded). All were shaped in parallel and reconciled on 2026-11-17; what this EPIC assumes of
> them is stated in Rabbit-holes (ASM-1 to ASM-3). Every DEC marked "leader's choice" may be
> overruled by the developer.

**Golden-thread parent:** capability `rp-package-boundaries` and the developer's seed: "the
thematic modules are lvl1 distinctions, and then each thematic module then has its own
adapters/models/services/entrypoints ... in linkml folder we shall have likely a flat list of files
... that will be mirrored then in the generated code".

## Appetite

**VERY LARGE**, delivered in eight stages, one PR each. Every hand-written module of the library
(61) and every generated package moves; the import contracts are rewritten; one adapter is split.
No behaviour changes, so it is not HUGE: the import graph between themes is already acyclic, and
each stage is a move that is green on its own.

## Why

`rdf_persistence/` has four long lists: 39 service modules, 9 entrypoints, 6 adapters, 8 domain
modules, and the generated models sit by the lowest layer that imports them, not by what they are
about. A reader looking for "how tenancy works" opens six folders. `rp_service.yaml` is a
catch-all used by 8 of the 13 themes, and the contract that keeps the message bus on top names 39
modules by hand. The sibling projects (ted-sws, mapping-suite-sdk) solve this with two levels:
themes first, layers inside each theme. The other four changes of the initiative have settled what
the models are; this one settles where everything lives.

## Solution outline

The package becomes `rdf_persistence/<theme>/{domain,services,adapters,entrypoints}`, with only
the layers a theme needs. The themes, in dependency order:

```text
core          the kernel: RpModel, errors, media types, SPARQL terms, the HTTP base, the metamodel
iris  schema  files                  (each imports core only, schema and iris also core's metamodel)
provenance                           (core, schema)
persistence                          the Store port, session, mapper, listing, the Fuseki adapter
access  migrations
tenancy
collaboration  events
messaging
api                                  the service kit: aggregates, documents, all entrypoints
```

Inside a theme the layers keep today's direction, and a theme imports only themes below it. The
LinkML schemas stay where consumers import them (`model/rp_*.yaml`, flat); the technical schemas of
`technical-models` are split by theme, and each generates into the same kind of layer as today,
now inside its theme: `technical-models` already applies the rule (the lowest layer every user may
import), so this change only adds the theme prefix. A domain model (persisted as RDF) is only ever
in a `domain/generated/` folder; a technical model (a setting, a wire record, a request body, a
SPARQL term bundle) is never there.

```python
from rdf_persistence import FusekiStore, ServiceKit, Tenancy        # unchanged: the 141 names
from rdf_persistence.persistence.adapters.fuseki import FusekiStore  # the new home
from rdf_persistence.adapters.fuseki import FusekiStore               # works for one release, warns
```

The move goes theme by theme, kernel first, each stage a `git mv` plus import rewrites, so history
follows the files and every stage merges green. `FusekiStore` splits into a SPARQL 1.1 Protocol
base and a Fuseki part, which `second-store` can build on. The `iris.py` wrappers that only call
`DEFAULT_IRIS` go (the split of `iris.py` itself is `technical-models`').

## Key decisions

- **DEC-1** (E-2; leader's choice of the names): **13 themes** in the order above, `core` as the
  kernel's name (ted-sws and mapping-suite-sdk both call theirs `core`, and `rp_core.yaml` is its
  schema). Placement follows analysis §5.3, checked with grimp on 2026-11-17: the theme graph is
  acyclic. Rejected: `kernel` (a third word for one idea); merging small themes (`iris`, `messaging`)
  into others (they are reused separately).
- **DEC-2** (E-1; leader's choice): the **metamodel stays one generation target**, in
  `core/domain/generated/` (one `.py` per module as today, one shapes graph, one context, the
  frames). Reason: its modules import one another across themes, and lower themes use classes of
  higher ones' schemas (`TenantState` in `schema`, `TenantAccess` in `access`, `StoredFile` in
  `schema`); placed per theme they make three cycles (inputs/seed.md). The metamodel is the
  vocabulary every theme speaks, which is what a kernel is. Only the **technical** schemas are
  split by theme. Rejected: one generated folder per metamodel module in its theme (cycles; one
  shapes graph and one context cannot be split).
- **DEC-3** (Q-2 at package level; leader's choice of the form): **domain models sit in
  `<theme>/domain/generated/`; a technical model sits in `<theme>/<layer>/generated/`, where
  `<layer>` is `services`, `adapters` or `entrypoints`: the lowest layer every user of the model
  may import, in the lowest theme that uses it.** A wire record used only by an adapter lands in
  `adapters`, a request body only the entrypoints use in `entrypoints`, a setting that an adapter
  and the kit both use in `services` (PD-2). Hand-written code in a `domain` layer that needs a
  technical model is not domain code: `technical-models` (its DEC-3) already moved `Iris` to
  `services/iris.py` and `tenant_move` to `services/`, and here they go to `iris/services/` and
  `tenancy/services/`. Checked three ways: the generator refuses a target whose kind disagrees with
  its folder; import-linter forbids every `*.domain` from importing any other layer; the model
  guard finds no technical class under `domain/`. (re-shaped 2026-11-17 by the lead in the
  cross-change reconciliation: the rule is "the lowest layer every user of the model may import,
  in the lowest theme that uses it", as PD-2 applies it; `technical-models` applies the same rule
  to today's layers, so this change only adds the theme prefix.) Rejected: a `<theme>/generated/`
  folder beside the layers (outside every contract, so nothing checks it); technical models in an
  innermost layer beside `domain` (the reader would again find DTOs next to the domain;
  `technical-models` first shaped that form and dropped it in the reconciliation).
- **DEC-4** (E-2): **staged moves, no big bang.** One PR per stage, in theme order; each stage moves
  its modules and their unit tests with `git mv`, rewrites every import in the repository in the
  same PR (library, generator, testkit, tests, docs), and leaves no internal shim. Rejected: one PR
  for everything (unreviewable, blocks every other branch for its whole life); internal shims at
  every old path (a second import path per module, kept alive by forgetting).
- **DEC-5** (E-4): **consumers stay stable.** The 141 top-level names stay, each the same object.
  The YAML paths stay. Two deep paths get a shim that warns (`DeprecationWarning`) for **one minor
  release**: `rdf_persistence.domain.base` and `rdf_persistence.adapters.fuseki`. From stage 1 the
  generator writes `from rdf_persistence import RpModel` into a consumer's generated code, so a
  consumer that regenerates has no deep import left. The shims and the deprecated names go in the
  last stage, after a release that carries them. Rejected: no shims (a consumer's committed
  generated code breaks on upgrade); shims for every moved module (none is public).
- **DEC-6** (E-3): **import-linter: one layers contract with every theme as a container, one
  contract ordering the themes**, and forbidden contracts with wildcards (`rdf_persistence.*.domain`)
  that keep the layer direction across themes. The 39-module bus contract and
  `migrations-below-the-runner` are implied by the order and go. The other fine-grained contracts
  keep their meaning on the new paths. Rejected: thirteen separate layers contracts (one form,
  thirteen copies to keep in step).
- **DEC-7** (E-5): **`FusekiStore` splits** into `SparqlProtocolStore`, a base that owns the SPARQL
  1.1 Protocol (query and update POST, Graph Store PUT, status mapping, result parsing) and leaves
  the endpoint layout and the dataset administration abstract, and `FusekiStore`, which adds
  Fuseki's `/{ds}/query|update|data` layout, `/$/datasets` and dataset-level N-Quads. Behaviour,
  constructor and public name are unchanged. If `second-store` is planned before this change
  reaches `persistence`, the split is delivered first, alone, in the old layout (task 4.1).
  Rejected: renaming only (analysis §2.1: it would mislead).
- **DEC-8** (E-6): **the 11 wrappers that only call `DEFAULT_IRIS` are retired**; tests call
  `Iris` instances. The 12 policy-free layout functions (`graph_iri`, `skolem_iri`,
  `system_database_name`, ...) stay, in `iris/domain/layout.py`. `mint_aggregate_iri`, one of the
  141 names, warns for one release and goes with the shims (leader's choice). Rejected: retiring
  all 23 (the layout functions do not depend on the policy and 7 runtime modules use them).
- **DEC-9** (leader's choice): **unit tests mirror the themes** (`tests/unit/<theme>/`), moved in
  the stage that moves their theme; `tests/changed.py` maps a theme's folder to its tests. Feature,
  integration and e2e folders do not move: their markers are by folder and they cross themes.
- **DEC-10** (E-1, with `generator-package` DEC-7): a technical schema module declares its
  `python_package` like a metamodel module (`generator-package` PD-6 already annotates and checks
  each technical group), and **a module imported from another target is imported, never generated
  twice**. This is what lets `tenancy`'s technical schema use `access`'s, and it gives consumers
  the cross-target imports `technical-models` DEC-4 deferred.

## Rabbit-holes

- **ASM-1 (assumed of `technical-models`).** Technical schemas live under
  `model/technical/<group>/rp_<group>.yaml` and carry `module_kind: technical`; `service`,
  `settings` and `templates` generate into `rdf_persistence/services/generated/<group>/`, `wire`
  into `rdf_persistence/adapters/generated/`, `testkit` into `rdf_persistence/testkit/generated/`;
  a target declares `kind`; `domain/iris.py` is already split into `domain/layout.py` and
  `services/iris.py`, and `tenant_move.py` is in `services/`. This change splits the groups by
  theme (`testkit` stays). If it landed otherwise, stage 1's first task re-maps the table of
  design.md; the rule (DEC-3) does not change.
- **ASM-2 (assumed of `generator-package`).** The generator is `rdf_persistence_generation`, a
  sibling top-level package; metamodel and technical modules declare `python_package`;
  `rp_generation.yaml` and the generator's tests have left the library. The generator imports
  library modules by deep path (`schema_structure`, `schema`), so each stage rewrites its imports too.
- **ASM-3 (assumed of `otel-observability`).** Loggers are named by `__name__`; the move changes
  every logger name below `rdf_persistence`. A consumer filtering on `rdf_persistence.services.x`
  must filter on the new name; `rdf_persistence` as a whole still works. Its `telemetry` group
  generates into `rdf_persistence/services/generated/telemetry/` and its helpers are
  `services/telemetry.py`. (`manual-revision-notes` adds `services/jsonld.py`; design.md PD-1
  places it, and task 1.1 re-reads the tree for any other new module.)
- **The served OpenAPI and the consumer's TypeScript.** Today they come from one target
  (`rp_service`). After the split, the request and response bodies come from several theme
  targets; the components and the TypeScript copy are collected over them. The served
  `/openapi.json` and a consumer's generated TypeScript must stay byte-identical.
- **Branches open during the move** (`second-store`, `fine-grained-access`, `graphql-read-api`,
  `typescript-client`, `ldes-view`). Each stage publishes its old→new path table, so a branch
  rebases with one ast-grep rule per row.
- **String paths.** `mock.patch("rdf_persistence.services...")`, `caplog` logger names, ruff
  per-file ignores, `.coveragerc` omits and doc references name modules by path; each stage
  rewrites them, and a test finds any left.

## No-gos

- Changing behaviour, a signature or a public name, except the deprecations of DEC-5 and DEC-8.
- Moving or renaming `rdf_persistence/model/rp_*.yaml`, or splitting the metamodel's generation
  target.
- Moving `testkit` into a theme, or touching the generator beyond E-1 and the template line of DEC-5.
- Re-exports in theme `__init__.py` files: each stays a docstring only.
- Merging, renaming or redesigning modules while moving them (only the removal of the `iris.py`
  wrappers, DEC-8, and the `FusekiStore` split of DEC-7; `technical-models` split `iris.py`).
- A second store adapter (`second-store`), new settings or log fields (`technical-models`,
  `otel-observability`).
- Splitting the distribution.

---

## What Changes

- `rdf_persistence/{domain,services,adapters,entrypoints}/` → `rdf_persistence/<theme>/<layer>/`
  for 13 themes (table in design.md, PD-1). The four old packages are gone at the end, apart from
  the two shims until the last stage.
- `rdf_persistence/domain/generated/` → `rdf_persistence/core/domain/generated/`.
- `model/technical/<group>/rp_<group>.yaml` (from `technical-models`) →
  `model/technical/<theme>/rp_<theme>_<layer>.yaml`, each generated into
  `rdf_persistence/<theme>/<layer>/generated/`; `pyproject.toml` gains one `[[tool.rp-generate]]`
  entry per pair.
- `rdf_persistence/domain/layout.py` → `iris/domain/layout.py` and `rdf_persistence/services/iris.py`
  → `iris/services/iris.py` (the halves `technical-models` split); 11 wrappers removed.
- `adapters/fuseki.py` → `persistence/adapters/sparql_protocol.py` (`SparqlProtocolStore`) and
  `persistence/adapters/fuseki.py` (`FusekiStore`).
- Generator: cross-target imports (DEC-10), the kind/folder check (DEC-3), the public `RpModel`
  import in a consumer's code (DEC-5), components and TypeScript collected over served targets.
- `.importlinter` rewritten (DEC-6); `tests/changed.py`, `ruff.toml`, `.coveragerc` on new paths.
- `tests/unit/<layer>/` → `tests/unit/<theme>/`.
- Docs: `architecture/index.adoc` (the theme map), `architecture/generation.adoc`, every page that
  names a module path; `questions.adoc` gains "Where does a module live?".
- **BREAKING (after one deprecation release):** `rdf_persistence.domain.base`,
  `rdf_persistence.adapters.fuseki` and `mint_aggregate_iri` are removed; logger names change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rp-package-boundaries`: themes with layers inside (the layers requirement as
  `generator-package` leaves it, with themes); the order of themes; deprecated deep paths.
- `rp-generation`: cross-target imports; where domain and technical models sit, per theme, and a
  target's kind fixing its folder (both requirements `technical-models` adds, modified here); a
  consumer's generated code imports the toolkit only from its public package.

## Impact

- A consumer importing only `rdf_persistence` and `rdf_persistence.testkit` sees no change.
- A consumer's committed generated code keeps working for one release (shim), and its freshness
  check asks it to run `rp-generate` once, which removes the deep import.
- Every open branch of this repository must rebase across each stage (the path tables help).
- GitNexus and Serena indexes are stale after each stage; the lead re-indexes (`develop/agents.adoc`).
