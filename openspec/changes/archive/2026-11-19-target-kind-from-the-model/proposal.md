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

## Reconciliation (as delivered)

Delivered in one PR, #188, one stage (SMALL). Challenged by one L2+L3 review pass (7 findings;
two re-labelled Critical and fixed, D-4 and D-5; five under the floor) and a fresh checker.
Acceptance demo waived by the developer (`evidence/acceptance.md`).

| Shape item | Final state | Where |
|---|---|---|
| DEC-1 kind derived from the target's own modules | delivered: `derived_kind` over `own_schemas` | 8cdac35e |
| DEC-2 the `kind` key refused | delivered: slot removed from the generator's model, refused as an extra key naming `kind` | 8cdac35e |
| DEC-3 the folder rule binds every target | delivered; "no layer" read as any segment before `generated` that is no layer (D-1) | 8cdac35e |
| DEC-4 our own targets follow the rule | delivered: toy library, getting-started example, cross-target fixture, every inline config that generates; tests that formed a mixed target use a technical-only project (D-3) | 17fd8eb3 |
| DEC-5 release 0.7.0 with the CHANGELOG migration note | migration note delivered; the release is not part of this PR | 09f23048 |
| PD-2 no mixed target | delivered; the problem names the target by its root schema (D-2) | 8cdac35e |
| Docs (task 3.1) | delivered; the user manual's "every schema of the folder" corrected after review (D-4) | 09f23048, ea2ed003 |
| `make refresh-map` exits 0 | delivered; three tests already on `develop` had no row and were mapped | dccfd977 |

**Differences from the shape, with the reason:**

- **What Changes, inline configs:** beyond the generator's tests, the configs in
  `tests/unit/api/test_service_written.py`, `tests/integration/api/test_router.py` and the generator
  e2e tests moved too: each runs generation and would fail the rule.
- **Not delivered here:** the 0.7.0 release and moving the getting-started pin off `v0.6.0`.
  Both follow the release (DEC-5), after `domain-model-per-theme`.
- **Under the floor, open:** review S1–S5 (`design.md`, Delivery decisions). Examples: the theme
  message does not name the derived kind, and the modules in the mixed-target message are joined by
  `,` rather than `, `.
