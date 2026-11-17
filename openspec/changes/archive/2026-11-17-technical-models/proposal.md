<!-- Parents: openspec/specs/rp-generation (LinkML is the single source; a technical module may hold
     shapes that are never stored); openspec/specs/rp-package-boundaries (layers import downward
     only); toolkit-v1-foundation PD-18, PD-24 to PD-28 (archive/2026-11-06-toolkit-v1-foundation/
     design.md); rules P-0007, P-0008, P-0009 (docs/rules/). Seeds: inputs/seed.md, which points at
     ../manual-revision-notes/inputs/{seed,answers-2026-11-17,improvements,analysis,keep}.md. -->

# EPIC: Technical models apart from domain models

> Shaped 2026-11-17 from the developer's answers Q-1 and Q-2. **Position: 2nd** of the five
> changes of the `manual-revision-notes` initiative, plus `ldes-view` later; it depends on
> `manual-revision-notes` (A-3 and A-4 add the JWT allow-list and the clock leeway as constructor
> parameters, A-2 puts the roots limit on the `Mapper`; this change moves all three into the
> settings). `otel-observability` (D-3, `LogContext`) comes after it and uses its mechanism.
> Every DEC marked "leader's choice" may be overruled by the developer.

## Appetite

**LARGE**, in four stages. Boundaries move: the service models leave `domain/generated/` for the
`services` layer, `domain/iris.py` splits so that no domain module imports a technical model, and
three groups of new generated models arrive (settings, template variables, testkit records).
Existing constructors migrate to settings groups.

## Why

A reader of `rdf_persistence/` cannot tell a domain class (what a consumer persists as RDF) from a
technology-bound record (a setting, a wire answer, a SPARQL parameter). The service module
generates into `domain/generated/service/`, the wire module into `adapters/generated/`, and a
SPARQL template's parameters are a bare dict rebuilt in four places (`unique_keys.py:126`). About
27 deployment values sit as constants and keyword defaults at 15 sites, two of them duplicated.
The developer's answer to Q-2: "we must separate the technical and the domain models ... then we
truly see what are the DTOs that are technology bound, and what are the domain classes".

## Solution outline

Every model stays generated from LinkML (Q-1). What is new is that the kind of a model shows in
its path and is checked:

| Kind | Schemas | Generated into |
|---|---|---|
| domain (the metamodel) | `rdf_persistence/model/rp_*.yaml`, flat, unchanged | `rdf_persistence/domain/generated/`, unchanged |
| technical | `rdf_persistence/model/technical/<group>/rp_<group>.yaml` | the `generated/` folder of the lowest layer every user of the model may import (DEC-1) |

The technical groups are `service` (moved from `model/service/`, generated into
`rdf_persistence/services/generated/service/`), `wire` (moved from `model/adapters/`, still
generated into `rdf_persistence/adapters/generated/`, its only users being adapters and the
testkit), `settings` (new: the central settings, C-1) and `templates` (new: the SPARQL term
bundles of D-1 and the IRI template variables of D-2), both in `rdf_persistence/services/generated/`.
A fifth group, `testkit` (`model/technical/testkit/rp_testkit.yaml`), holds the records the
library's testkit uses (D-4), today declared in the generator's `rp_generation.yaml`; it generates
into `rdf_persistence/testkit/generated/`, beside its only users, so the library never imports the
generator for them (`generator-package` DEC-3 relies on this). As built, a sixth group,
`telemetry`, arrived from `otel-observability` stage 1 (#149) by the same rule.

The domain layer then imports no technical model. Two hand-written domain modules use the service
models today, so `domain/iris.py` splits: its policy-free layout functions stay in `domain`, and
`Iris`, its policy and its templates move to `services/iris.py`, with `tenant_move.py` (DEC-3).

The split is checked three ways: the schema annotation `module_kind: technical` that the
metamodel already has, a `kind` key on each `[[tool.rp-generate]]` target that the generator
checks against its modules, and an import-linter contract that `rdf_persistence.domain` imports no
technical generated package. A consumer gets the `kind` key and its check too.

The settings are generated groups with today's values as defaults, passed from the consumer's
composition root into each constructor:

```python
settings = ToolkitSettings()                         # today's values
# or, opt-in: settings = settings_from_env(ToolkitSettings)   reads RP_HTTP__READ_TIMEOUT_SECONDS …
store = FusekiStore(url, http=settings.http)
verifier = JwksTokenVerifier(issuer, audience, jwks=settings.jwks, http=settings.http)
bus = RedisEventBus(redis_url, deployment="prod", events=settings.events)
install_service(app, ..., settings=service_settings, toolkit=settings)
```

## Key decisions

- **DEC-1** (Q-2; leader's choice of the form): the **kind** of a schema is the existing
  `module_kind` annotation; a technical schema lives under `model/technical/<group>/` and
  generates into the `generated/` folder of the **lowest layer every user of the model may
  import**: `service`, `settings` and `templates` into `rdf_persistence/services/generated/<group>/`,
  `wire` into `rdf_persistence/adapters/generated/` (unchanged), `testkit` into
  `rdf_persistence/testkit/generated/`. The domain schemas and `domain/generated/` do not move.
  (re-shaped 2026-11-17 by the lead in the cross-change reconciliation: no intermediate
  package of technical models beside the layers; this change applies today the end-state rule of
  `thematic-structure` DEC-3 to the present layers, so that change only adds the theme prefix and
  moves no technical model twice.) Reason: the split is visible in both trees, every generated
  package sits inside a layer the existing `layers` contract already orders, and the `generated`
  segment keeps the model and file guards (PD-28) working unchanged. Rejected: the annotation alone
  (invisible in the package tree); moving `domain/generated/` too (over a hundred imports, and the
  thematic change E moves it anyway); an innermost `technical/` package beside `domain` (first
  shaped here: it needed a layer line pairing `domain` with it, which let hand-written domain code import
  technical models, against Q-2, and `thematic-structure` would have moved every model again).
- **DEC-2** (leader's choice): five technical groups, each its own `[[tool.rp-generate]]` target:
  `service`, `wire`, `settings`, `templates` and `testkit`. `ServiceSettings` and `IriPolicy` stay
  in `rp_service.yaml`. The `testkit` group follows DEC-1's rule too: its only users are testkit
  modules, the testkit sits outside the layers, and the existing contract `runtime-without-extras`
  keeps the runtime off it; its schema sits under `model/technical/` (coordinated with
  `generator-package`, whose DEC-4 relies on it). (re-shaped 2026-11-17 by the lead in the
  cross-change reconciliation: package paths follow DEC-1's new rule; `testkit` is no longer an
  exception.) Reason: one target per folder is how the generator works (PD-26); `service`
  is the only one with OpenAPI components and the only one copied into a consumer's TypeScript,
  so settings and template variables must not join it. Rejected: one technical target (wire and
  settings shapes would leak into the served OpenAPI and the consumer's TypeScript). A later
  technical group is one more folder and one more target: `otel-observability` adds `telemetry`
  (`model/technical/telemetry/rp_telemetry.yaml` → `rdf_persistence/services/generated/telemetry/`,
  its PD-1) for D-3's `LogContext`.
- **DEC-3**: technical models MAY import domain models (a request body may carry a domain value);
  **nothing in the domain layer** imports a technical model, neither a generated domain model nor
  a hand-written domain module. Two hand-written modules do today (`domain/iris.py` reads
  `IriPolicy`, `IdSpec`, `ServiceSettings`; `domain/tenant_move.py` reads `IriPolicy`), so this
  change brings forward the `iris.py` split of `thematic-structure` PD-5: the policy-free layout
  functions stay in `domain` (`domain/layout.py`); `Iris`, `DEFAULT_IRIS`, the policy and template
  machinery and the wrappers over `DEFAULT_IRIS` move to `services/iris.py`; `tenant_move.py`
  moves to `services/`. Retiring the wrappers (E-6) stays in `thematic-structure`. Checked by
  import-linter (`layers`, and the contract `domain-never-imports-technical-models`), by the
  generator's `kind` check and by the boundary check that already refuses a domain module
  importing a technical one. (re-shaped 2026-11-17 by the lead in the cross-change reconciliation:
  the developer's Q-2 keeps the domain layer free of technical models now, so the layer line
  pairing `domain` with technical models, and the package cycle it accepted, are gone.)
- **DEC-4** (leader's choice): consumers get the split as a **checked declaration**: a target may
  say `kind = "technical"` or `kind = "domain"`, and `rp-generate` fails when its modules disagree.
  Without `kind`, a target behaves as today. A consumer's technical target importing its *own*
  domain target is not built here: it needs a package per module, which is E-1. Rejected: building
  cross-target imports now (it is E-1's mechanism, and building it twice would diverge).
- **DEC-5** (C-1, Q-1): the settings are generated groups in `rp_settings.yaml`: `HttpSettings`,
  `JwksSettings`, `DirectorySettings`, `EventSettings`, `SseSettings`, `LimitSettings`, and
  `ToolkitSettings` holding one of each. Every slot has today's value as its default. Each
  constructor takes its group (`http=`, `jwks=`, `events=`, ...) in place of the per-value keyword
  arguments it has today. **BREAKING** for a consumer that passes one of those keywords.
  Rejected: keeping both spellings (two ways to say one thing).
- **DEC-6** (B-8): `settings_from_env(model, prefix="RP_")` reads the environment through
  pydantic-settings, behind a new `settings` extra, imported only when called. Nothing reads the
  environment at import. Rejected: generated models deriving from `BaseSettings` (every consumer
  would need pydantic-settings, and validation would read the environment).
- **DEC-7** (D-1): a SPARQL term model holds `SparqlTerm` values, not plain strings. pydantic turns
  a `str` subclass into a `str` (checked on pydantic 2.14.2), which would lose the PD-3 guarantee
  that only `term()` output reaches a query. So `SparqlTerm` declares its own pydantic schema
  (instances only) and the LinkML type `sparql_term` names it through `repr`.
- **DEC-8** (C-3, C-4): the four Zitadel slugs the testkit alone uses move to `testkit/zitadel.py`;
  every other protocol constant stays. The user state becomes the enum `ZitadelUserState` with the
  six states of Zitadel's v2 user API.
- **DEC-9** (leader's choice): no compatibility shims for `domain.generated.service`,
  `domain.iris` and `domain.tenant_move`. They are not public (rp-package-boundaries); every name
  stays exported from `rdf_persistence`.

## Rabbit-holes

- **Splitting `rp_service.yaml` by theme.** That is E-1. Only the new classes go elsewhere here.
- **Cross-target imports for consumers** (DEC-4): stop at the `kind` check.
- **pydantic-settings sources** beyond the environment (dotenv files, secrets directories): not
  configured; a consumer who wants them builds the settings itself.
- **Every dict in the package.** Only the concept-carrying sites of analysis §5.2 items 1, 3, 6
  and 7 change; boundary dicts and the lazy-import maps stay (keep.md). Item 2 is A-6
  (`manual-revision-notes`); items 4 (`migration_runner._failure`) and 5 (the log attributes) are
  `otel-observability`'s, with `LogContext`.

## No-gos

- Moving `rdf_persistence/model/rp_*.yaml` or changing a consumer schema's imports.
- Moving `domain/generated/`, or any hand-written module but the `iris.py` split and
  `tenant_move.py` (DEC-3); retiring the `iris.py` wrappers (E-6); themes (E).
- Moving `rp_generation.yaml` or the generator (F); cutting the testkit's other imports of
  `generation` (`freshness`, and `conformance`'s use of `read_targets`, `ConstraintCase` and
  `ConstraintKind`), which is F-1.
- `LogContext` and the logging style (D-3, `otel-observability`).
- Environment reads, dotenv loading or `os.environ` writes at import.
- New deployment values or changed defaults: every default is today's value.
- Moving protocol constants (slugs, IRIs, header names, SPARQL text) into settings.

---

## What Changes

- `rdf_persistence/model/service/rp_service.yaml` → `model/technical/service/rp_service.yaml`,
  generated into `rdf_persistence/services/generated/service/` (was `domain/generated/service/`).
- `rdf_persistence/model/adapters/rp_wire.yaml` → `model/technical/wire/rp_wire.yaml`, still
  generated into `rdf_persistence/adapters/generated/`; gains `ZitadelUserState`.
- New `model/technical/settings/rp_settings.yaml` and `model/technical/templates/rp_templates.yaml`
  (into `rdf_persistence/services/generated/{settings,templates}/`), and
  `model/technical/testkit/rp_testkit.yaml` (into `rdf_persistence/testkit/generated/`).
- `domain/iris.py` splits: `domain/layout.py` (the policy-free layout functions) and
  `services/iris.py` (`Iris`, `DEFAULT_IRIS`, the policy, the templates, the wrappers);
  `domain/tenant_move.py` → `services/tenant_move.py` (DEC-3).
- `rp_generation.yaml`: the slot `GenerationTarget.target_kind` (TOML key `kind`), a `TargetKind`
  enum, aliases `schema` and `regenerate-command` on their slots (`schema` and `kind` through the
  opt-in annotation `field_name: slot`, D-52), `BoundaryRule.target_kind`; the
  ten records the library's testkit imports leave it for `rp_testkit.yaml` (`ClassShape`,
  `SlotShape`, `ContainerMarker`, `Violation`, `MachineUser`, `ZitadelProject`, `ZitadelServer`,
  `ExecResult`, `FusekiServer`, `GarageServer`) and the new `FieldFlags` joins them;
  `ConstraintCase`, `ConstraintKind` and the slot `kind` stay (only the conformance suite uses
  them, and `generator-package` moves it to the generator).
- `generation/`: the `kind` check; `pydantic_split` imports the Python type a LinkML type's
  `repr` names, defaults a slot annotated `default_instance` to a new instance of its class, gives
  a multivalued `ifabsent: string(a, b)` its list default (design D-31, a LinkML work-around), and
  names a field annotated `field_name: slot` after its slot with the alias apart (D-48, D-52), so `config.py` drops
  `FIELD_OF_TOML_KEY`. The hard check refuses a `default_instance` it cannot honour (D-32) and
  reads the flag as YAML writes it (`true`, `'true'`, `'True'`; any other value refused, D-55). The
  class rules (root, owned, reference) skip the classes of a technical module (D-49); in exchange a
  module that is not technical may not hold a technical class, and a technical module may not
  declare a root (D-55). The JSON-LD context names a `field_name: slot` slot by its slot name.
- `domain/sparql.py`: `SparqlTerm`'s pydantic schema and `fill_terms`. `services/unique_keys.py`,
  `session.py`, `listing.py`, `migrations.py`: term models. `services/iris.py`: `IriTemplateVariables`,
  `IriParts`.
- **BREAKING** constructors: `HttpAdapter`, `FusekiStore`, `JwksTokenVerifier`, `ZitadelIdentity`,
  `S3FileStore`, `RedisEventBus`, `Relay`, `EventHub`, `MessageBus`/`bootstrap`, `Mapper` and
  `UnitOfWork` (the roots limit), `add_events_route`, `ServiceKit`/`install_service` (`toolkit=`).
  New `settings_from_env`, `settings` extra (it overrides pydantic-settings' private
  `_load_env_vars`, D-34). Nineteen public constants and four Zitadel slugs are removed or moved
  (the changelog lists each, D-42).
- `testkit/`: imports its records from `rdf_persistence.testkit.generated.rp_testkit`; three
  `model_copy(update=)` sites use `replaced()`; `TokenSigner` builds its claims from `JwtClaims`.
- `.importlinter`: one contract, `domain-never-imports-technical-models`; `layers` unchanged.
- Docs: `architecture/generation.adoc`, `architecture/index.adoc` (the layer map rewritten),
  `architecture/data-flows.adoc`, the new `howto/settings.adoc` (with every removed keyword and
  its replacement), `howto/adopt.adoc` (the `kind` key, a technical target),
  `howto/event-driven.adoc`, `develop/index.adoc`, `questions.adoc`, the nav.
- Tests: `tests/feature/technical_models.feature`, one scenario per delta scenario.

## Capabilities

### New Capabilities

- `rp-settings`: the toolkit's deployment values as generated groups with defaults, passed from
  the composition root, optionally read from the environment.

### Modified Capabilities

- `rp-generation`: technical models are generated apart from domain models; a target declares its
  kind; a generated field can hold a toolkit type; a slot can default to an instance of its class
  (added at stage 4 with the developer's sign-off, design D-33, D-44).
- `rp-package-boundaries`: a technical model sits in the `generated/` folder of the lowest layer
  every user may import; the domain layer imports none.

## Impact

- A consumer that imports the top package sees no change except the constructors of DEC-5.
- A consumer that imported `rdf_persistence.domain.generated.service`, `rdf_persistence.domain.iris`
  or `rdf_persistence.domain.tenant_move` directly must import from `rdf_persistence`.
- A consumer's `[[tool.rp-generate]]` table is unchanged; `kind` is optional. A consumer's
  technical module may hold nested classes and `default_instance` (D-49). Two new refusals
  (D-55): a module that is not technical, including one with no `module_kind`, may not hold a
  technical class, and a technical module may not declare an aggregate root. A consumer schema that
  did either stops generating, naming the module and the class.
- Every settings duration is at most one year, so `inf`, `nan` and overflowing values are refused
  when the settings are built; the JWKS unknown-key cooldown is at least 1 s and no longer than the
  key-cache TTL, and `JwksTokenVerifier` refuses a longer one (D-55). Every default is unchanged;
  this is **BREAKING** only for a deployment that sets such a value. `settings_from_env`'s errors
  no longer repeat the value read.
- A consumer that imported a testkit record (`ClassShape`, `FusekiServer`, ...) from
  `rdf_persistence.generation.generated.rp_generation` imports it from
  `rdf_persistence.testkit.generated.rp_testkit` (**BREAKING**, no shim).
- External libraries: two work-arounds, each in one place and recorded: LinkML's scalar default
  for a multivalued `ifabsent` (D-31, commented on linkml#4160) and pydantic-settings'
  environment loading (D-34). LinkML's alias handling (D-48) is met by an opt-in annotation in our generator (D-52).
- New optional dependency `pydantic-settings==2.16.2` (already in `uv.lock`) in the `settings` extra.

## As built

Reconciled at the close of the change (P-0004).

| Stage | PR | As shaped | As built |
|---|---|---|---|
| 1 the split | #144 | DEC-1 to DEC-4, DEC-9 | Delivered as shaped: `service` moved into `services/generated/service/`, `wire` under `model/technical/`, `domain/iris.py` split into `domain/layout.py` and `services/iris.py`, `tenant_move.py` into `services/`, the `kind` check and the contract `domain-never-imports-technical-models`. The review re-labelled four findings Critical, fixed before the merge: the release notes for the moved paths (D-10), the scenario map (D-11), docs that disagreed with the code (D-12), an untested scenario (D-13). Delivery decisions D-1 to D-13 |
| 2 templates | #145, #146 | DEC-7, D-1, D-2 | Delivered: `SparqlTerm`'s own pydantic schema, the `templates` group with the term bundles and `IriTemplateVariables`, `IriParts`. One field named `schema_id`, not as planned (D-19). The admin merge of #145 left `develop`'s manifests stale; #146 regenerated them, and every rebase now ends with `make generate` (D-27). Delivery decisions D-14 to D-27 |
| 3 settings | #150 | DEC-5, DEC-6, DEC-8 | Delivered: six settings groups with today's defaults (every `*_seconds` a float, D-32), the constructors migrated, `settings_from_env` behind the `settings` extra, `ZitadelUserState`. Two external work-arounds (D-31 LinkML list defaults, D-34 pydantic-settings). Rebased onto `otel-observability` stage 1, which added the `telemetry` group (D-37). Two pages still described removed keywords; fixed on the developer's decision (D-43). Delivery decisions D-28 to D-43 |
| 4 testkit, BDD, docs | #155 | D-4, PD-10, PD-11 | Delivered: the `testkit` target with PD-11's ten records and `FieldFlags`; the BDD feature; the docs and the new settings how-to. PD-10's aliases were blocked by LinkML (linkml#4256, #4257); the developer chose to extend our generator (D-48), and as built the rule is opt-in, `field_name: slot`, because naming every field after its slot renamed 80 generated fields (D-52). The spec gained "A slot can default to an instance of its class" (D-33, D-44); its test found that a consumer's technical module could not hold a nested class, fixed (D-49). The full review's fix pass (D-55, D-56) bounded every duration and the JWKS cooldown, hid input in `settings_from_env`'s errors, closed D-49's two holes, read `default_instance` as YAML writes it, and brought the docs, the changelog and two BDD steps in line; the lead's rebase doubled the scenario map, repaired (D-54). The checker's one unmet item (two removed constants missing from the changelog) was fixed. Accepted by the developer without a demo (D-53). Delivery decisions D-44 to D-56 |

### Divergences from the shape

- **DEC-2** shaped five technical groups; there are six, as `otel-observability` added `telemetry`
  by DEC-1's rule (D-37).
- **PD-10** shaped the TOML keys as plain LinkML aliases; as built they need the opt-in
  `field_name: slot` annotation (D-48, D-52).
- **DEC-4** shaped only a `kind` check for consumers; as built a consumer's technical module may
  also hold nested classes (D-49), and two refusals came with that (D-55).
- **DEC-5** and the no-go "new deployment values or changed defaults": no default changed, but the
  settings gained upper bounds and a higher cooldown floor that the shape did not name (D-55).
- **D-2** shaped `fill_terms`' bundle field as planned in PD-5; one field is `schema_id` (D-19).
