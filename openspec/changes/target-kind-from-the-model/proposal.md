# EPIC: A target's kind comes from its model, and binds every target

Parent: `thematic-structure` (archived 2026-11-19; DEC-3 the kinds, RISK-9 the kind/folder rule for
consumers). Seeds: `openspec/changes/domain-model-per-theme/inputs/seed.md` (one shaping session
for both EPICs; this one goes first). Sibling: `domain-model-per-theme`.

## Appetite

SMALL. One capability, the kind of a generation target, touched in the generator's config reader
and boundary step, and in the targets and fixtures that rely on the old rule.

## Why

A target's kind is stated three times: the module annotation `module_kind`, the
`[tool.rp-generate]` key `kind`, and the folder of its package; three checks keep them in step. And
the folder rule binds the toolkit only, so a consumer can generate code outside any layer. The
developer wants one source and the same rule for consumers.

## Solution outline

`rp-generate` reads a target's kind from the modules it generates and no longer accepts a `kind`
key. Every target, the toolkit's or a consumer's, generates into a package whose last segment before
`generated` names the layer its kind allows. A consumer that breaks the rule is told which target,
which package and what to change; the CHANGELOG carries the migration.

## Key decisions

- **DEC-1**: the kind is derived from the modules the target generates (the modules of its import
  closure in its root schema's folder): `technical` when every one is annotated
  `module_kind: technical`, `domain` otherwise (`access` modules are stored, so domain) — one source;
  rejected: keeping the key and checking it against the annotation (two sources kept in step by a
  check); rejected: "every module of the folder" (a consumer with domain and settings roots in one
  folder would derive its settings target as domain).
- **DEC-2**: the `kind` key is removed from the generator's model, so an entry that keeps it is
  refused as an unknown key, naming it — a clear failure rather than a silently ignored key.
- **DEC-3** (developer): the folder rule binds every target: the package's segment before
  `generated` is `domain` for a domain target, and `services`, `adapters` or `entrypoints` for a
  technical one. A package without a `generated` segment fails too. The theme segment stays a
  toolkit rule. `rdf_persistence.testkit` and `rdf_persistence_generation` are exempt from the whole
  rule, as today. **BREAKING** for a consumer with a package such as `app.generated`.
- **DEC-4**: our own consumer-style targets follow the rule in this change: the toy library, the
  getting-started example and every inline config in the generator's tests.
- **DEC-5**: released as 0.7.0 with `domain-model-per-theme`, or alone if that one is later; the
  CHANGELOG migration note names the three things a consumer changes (package, `kind` key, a
  technical module's annotation).

## Rabbit-holes

- A consumer's technical module without `module_kind: technical` now derives `domain`, and its
  `services` package fails. The message must name the annotation as the fix, not only the folder.
- The toy library's package (`tests.fixtures.library.generated`) appears in about 60 files: a
  mechanical rename, done in one commit with the regeneration.

## No-gos

- No change to which modules a target generates or imports (that is `domain-model-per-theme`).
- No theme rule for a consumer's packages.
- No new `module_kind` value; `access` stays as it is.
- No change to the hard-check rules other than the kind and folder ones.

---

## What Changes

- `rp-generate` derives a target's kind; the `kind` key of `[tool.rp-generate]` is refused.
  **BREAKING** for an entry that declares it.
- The kind/folder rule binds every target, consumers included. **BREAKING** for a package without a
  layer segment before `generated`.
- The toy library, the getting-started example and the generator tests' configs move to layer
  packages.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rp-generation`: "A target declares the kind of model it generates".

## Impact

- `rdf_persistence_generation/` (`model/rp_generation.yaml` and its generated module, `steps.py`,
  `checks/boundary.py`), `pyproject.toml` (no `kind`), `tests/fixtures/library/` and its users,
  `docs/modules/ROOT/examples/getting-started/` and its tutorial page, `tests/fixtures/cross_target/`,
  the generator tests' inline configs, `architecture/generation.adoc`, `user-manual/generate.adoc`,
  CHANGELOG.
- Consumers (MWBv2): drop `kind`; move a layer-less package; annotate technical modules.
