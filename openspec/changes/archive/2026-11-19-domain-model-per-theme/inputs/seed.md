# Seed: domain-model-per-theme (secondary; never groomed)

Developer, 2026-11-19, after release 0.6.0 (`thematic-structure` archived), in the lead session.

## The seed, in the developer's words

- "why do we have within /domain we have /generated and then a bunch of other classes (e.g.
  exceptions or media) everything is supposed to be generated or not?!"
- "why do you place all the generated model files into the core/domain/generated? isn't it cleaner
  to put the generated domain classes (and other technical files) within each thematic submodule
  (of course respecting the dependency between modules?)" — "where is the access domain model?"
- "why do we even have to separate these 'kinds'? I meant initially to separate technical LinkML
  models (e.g. settings classes, pagination and sorting mixins, access control perhaps, etc.) from
  the domain conceptual data models (project, conceptual mapping, technical mapping, resources,
  etc.), how does this idea differ from what you do today?"
- On RISK-9 of `thematic-structure`: "I would make it mandatory for consumers too."
- "take option (b)" (one combined shapes file and context, Python classes per theme).
- "shape an epic as small as possible".

## Q&A record (lead's answers, accepted by the developer)

- Hand-written domain files (`base.py`, `exceptions.py`, `sparql*.py`, `media.py`) are behaviour,
  not model artefacts; "LinkML is the single source" covers model artefacts. `sparql*.py` stay in
  `core/domain`: services use them (services may not import adapters) and they do no I/O.
  Developer: "I see how it is at the borderline, so better to hand-write these files".
- The domain model is one target today (`rp.yaml` → `core/domain/generated/`), which is why
  `access/` has no `domain/generated/`. Splitting it per theme fits the theme order except
  `rp_files` → `rp_provenance` (same rank): rank `provenance` below `files`.
- Option (b) chosen over (a): Python classes per theme; one combined `shapes.ttl`,
  `context.jsonld` and frames, as consumers load them today.
- `kind` is stated three times today (module annotation, `pyproject.toml` key, folder); one source
  proposed: the module's `module_kind` annotation.
- `model/` stays as it is (domain modules at the top, `technical/<theme>/` below): "good enough for
  now".
- Previous EPIC cannot take this: archived and released in 0.6.0; a small new change instead.

## The attack on the first PLAN, and the developer's answers (2026-11-19)

A fresh reviewer tried to break the first PLAN against the code and found four blockers: the
generator names its output files from the import path and needs a "modules a target generates"
set, not only an import rule (B1); the rule must apply only beside the root, or a consumer's
metamodel import stops going through `rdf_persistence` (B2); the `python_package` hard check fails
on imported modules (B3); `access` ↔ `tenancy` form a cycle (`rp_tenancy` imports `rp_access`;
`access` services use `TenantAccess`, `TenantState`), and `schema` imports `rp_files` and
`rp_tenancy` classes (B4). Also: theme targets with roots fail the migrations check (B5); two
targets in one package delete each other's files (B6); about 40 library modules and 60 test files
deep-import the moved modules, and `rdf_persistence/__init__.py` imports them eagerly (B7); about 25
generator-test configs use layer-less packages.

Answers:
- "okay yes split": the kind rule and the per-theme domain model are two EPICs; the kind rule
  (`target-kind-from-the-model`) first.
- "option (a) put them together": `rp_tenancy` is generated in the `access` theme (a tenant is an
  access boundary); the `tenancy` theme keeps its services.
- "add rp_collaboration.yaml": one root importing `rp_collections`, `rp_discussion`, `rp_workflow`.
- "I agree with 'each per-theme target will also write its own partial shapes.ttl'" (OQ-1 closed).
- "sure do a proper fix" (the `schema` imports); "sure do whatever is needed" (the deep imports).

## Found at intake (lead, reading develop at 2f75a60+)

- `core/domain/generated/rp.py` is the root module: it defines only `LinkMLMeta` and re-exports
  every module's classes (`from .rp_access import ...`). Kept in `core`, it would import every
  theme: it must not be written as Python, or not in `core`.
- `module_kind` has three values (`domain`, `technical`, `access`); `rp_access` and `rp_tenancy`
  are `access`, the rest carry none (domain by default).
- All domain modules sit in `rdf_persistence/model/` beside `rp.yaml`. The 7.2 docs builder noted
  that a module in the same folder as the target's root schema is generated again rather than
  imported: the cross-target import may not hold for these modules as is.
