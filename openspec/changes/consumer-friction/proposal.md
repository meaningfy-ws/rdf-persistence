<!-- Parents: issues #371 and #372 (MWB2 v2-05 stage 1); rp-generation "A module of another target
     is imported, not generated again"; architecture/generation.adoc "Imports between targets". -->

# EPIC: two frictions MWB2 v2-05 met: TypeScript copies and the fixture guard

**Golden-thread parents:** issues #371 and #372, filed by MWB2 `v2-05` stage 1
(meaningfy-ws/mapping-workbench-v2#122); `rp-generation` requirement "A module of another target
is imported, not generated again"; `architecture/generation.adoc` *Imports between targets*;
`openspec/changes/archive/2026-11-24-domain-values-and-fixes/design.md` D-3 (reversed here, DEC-5).
Serves the consumer's need (D-12): one copy of each generated TypeScript type, and SHACL fixtures
named as the consumer wants.

## Appetite

**SMALL.** One generator step (TypeScript) learns the rule the Python step already follows; one
testkit guard gets its existing escape documented. Existing structure reused; one stage, one PR.

## Why

When a target imports a module that another target generates, the Python imports its classes,
but the TypeScript writes a second, identical copy (#371). The copies drift when only one target
is regenerated, and a client can import one type from two paths. Separately, a consumer that
follows the user manual's guard example and scans `tests/` cannot keep a hand-written SHACL fixture
whose name holds "shapes" (#372): the escape, `exempt=`, exists but is documented for other uses.

## Solution outline

- **#371.** The TypeScript step reads the project's other targets. A module of the import closure
  whose `python_package` is another target's package, where that target writes TypeScript, is not
  written by the importer: the importer's modules import its types from the owner's folder by a
  relative path, and the importer's `index.ts` does not export it. Every other module is written
  as today. On the consumer's next run the old copy is removed as a stale output.
- **#372.** The docstring of `assert_models_generated`, the user manual example and
  `generation.adoc` say that hand-written fixtures (SHACL shapes, contexts) belong under a folder
  passed in `exempt=`, and the example passes one.

## Key decisions

- **DEC-1:** the importer imports from the owner's TypeScript folder when the imported module's
  `python_package` is the package of another target of the same project and that target sets
  `typescript`; it writes no copy. Reason: the rule the Python already follows
  (`generation.adoc` *Imports between targets*). Rejected: documenting that TypeScript always
  copies (keeps the drift the issue reports).
- **DEC-2:** when the owner is not a target of the project or sets no `typescript`, the importer
  writes the copy, as today, and the docs say so. Reason: someone must write the types; failing
  would break every consumer of the toolkit's own types (`rp_core.ts`, `rp_service.ts`, ...).
  Rejected: failing the run.
- **DEC-3:** the importer's `index.ts` does not export a module it imports from another target.
  Reason: one import path per type. Rejected: re-exporting it.
- **DEC-4:** #372 is solved by documentation (issue option 1): `exempt=` is the place for
  hand-written fixtures. Reason: no code and no new API for what one argument already does.
  Rejected: skipping test folders by default (option 2; a stray generated artefact in `tests/`
  would pass unseen) and an `allow_files=` pattern list (option 3; a second escape beside
  `exempt=`).
- **DEC-5:** the toy's value target and technical target each set `typescript`, so the toy
  reproduces #371 and `make typecheck-ts` compiles the cross-folder import. This reverses the
  archived `domain-values-and-fixes` D-3, whose premise ("`typescript.py` writes only a target's
  own schemas") was false.
- **DEC-6:** **BREAKING** for generated TypeScript, flagged in the commit and the CHANGELOG with a
  one-line migration; no switch keeps the copy (RISK-1).

## Rabbit-holes

- The import specifier: a folder nested under the other (`./values/x`), or a sibling
  (`../../domain/generated/values/x`). Computed from the two folders, both relative to the
  project; no other layout is designed for (RISK-2).
- The served types: every TypeScript target still writes `rp_service.ts` and the toolkit modules
  it uses (DEC-2). The owner's and the importer's copies of those stay; only the project's own
  modules are de-duplicated.
- A run with `--schema`/`--package` flags and no `pyproject.toml` entry knows no other target: it
  copies, as today.

## No-gos

- De-duplicating the toolkit's own TypeScript types (`rp_core.ts`, `rp_service.ts`, ...) across a
  consumer's TypeScript targets.
- A switch to keep the copy.
- Any change to `guards.py`'s patterns, defaults or signature (#372 options 2 and 3).
- Anything of `review-floors` (parallel), or any other testkit change.
- A TypeScript package or `import` path other than relative paths.

---

## What Changes

- `rp-generate`'s TypeScript step imports, rather than copies, a module that another target of the
  project writes as TypeScript; the importer's `index.ts` no longer exports it.
- **BREAKING** for generated TypeScript: a client importing such a type from the importer's folder
  imports it from the owner's folder instead.
- Docs: `generation.adoc` *Imports between targets* (TypeScript too, and when it still copies);
  `user-manual/generate.adoc` output table; `assert_models_generated`'s docstring, the user manual
  guard example and `generation.adoc` *Guards against hand-written models* (`exempt=` for
  fixtures); `CHANGELOG.md` *BREAKING*.
- The toy library: two targets gain `typescript`; their generated TypeScript is committed.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `rp-generation`: a requirement added, "A module another target writes as TypeScript is
  imported, not copied".

## Impact

- Code: `rdf_persistence_generation/extensions/typescript.py`, `rdf_persistence_generation/steps.py`,
  `rdf_persistence_generation/templates/typescript/module.ts.jinja`; `rdf_persistence/testkit/guards.py`
  (docstring only). `rp-manifest.json` files where these are generator inputs.
- Toy: `tests/fixtures/library/pyproject.toml`, new `web/src/domain/generated/values/` and
  `web/src/services/generated/` trees; `Makefile` `TOY_TS`.
- Tests: `tests/generator/unit/test_ext_typescript.py` (or a sibling), `tests/unit/testkit/test_guards.py`;
  scenario-map rows.
- Consumers: MWB2 regenerates; its `services/generated/fragment_checks.ts` is removed and imports
  of those types move to `domain/generated/values/` (RISK-1).
