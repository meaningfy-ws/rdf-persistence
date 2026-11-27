<!-- Parents: issue #402 (split from #189 item v); rp-generation "TypeScript targets get the
     service's types" and "A module another target writes as TypeScript is imported, not copied";
     architecture/generation.adoc "Imports between targets"; consumer-friction no-go (deferred here). -->

# EPIC: the toolkit's TypeScript written once per project

**Golden-thread parents:** issue #402, split from #189 (item v) by the owner's answer to OPEN-5 of
`review-floors`; `rp-generation` requirements "TypeScript targets get the service's types" and "A
module another target writes as TypeScript is imported, not copied"; `architecture/generation.adoc`
*Imports between targets*; `openspec/changes/archive/2026-11-25-consumer-friction/proposal.md`,
whose no-go "de-duplicating the toolkit's own TypeScript types" is the work this change takes up.
Serves the consumer's need (D-12): one copy of each toolkit TypeScript type across its targets;
MWB2 carries three copies of `rp_core.ts`, `rp_access.ts`, `rp_service.ts` and `rp_tenancy.ts` today.

## Appetite

**SMALL.** One generator step (TypeScript) extends the import rule of #371 to the toolkit's own
modules, behind one new configuration key. Existing structure reused; one stage, one PR.
**BREAKING** for generated TypeScript in projects with more than one TypeScript target.

## Why

Since #371 a project's own module is written once, by the target that owns it, and imported by
the others. The toolkit's modules (`rp_core.ts`, `rp_access.ts`, `rp_service.ts`, ...) belong to no
target of the project, so every TypeScript target still writes its own copy. The copies drift when
one target is regenerated after a toolkit upgrade and another is not, and a client can import one
type, `Problem` or `TenantSummary`, from several folders.

## Solution outline

A project with several TypeScript targets names one of them as the owner of the toolkit's
TypeScript (`toolkit-typescript = true` on its `[[tool.rp-generate]]` entry). The owner writes the
toolkit's shared modules, the metamodel's and the served types', once. Every other TypeScript
target writes none of them: its modules import those types from the owner's folder by a relative
path, as #371 does for a project module, and its `index.ts` does not export them. A project with
one TypeScript target is unchanged. A project with several and no owner, or more than one, is
refused before anything is written, with a message that names the entries and the key to set. On
the next run, the copies an importer wrote before are removed as stale outputs.

## Key decisions

- **DEC-1:** with two or more TypeScript targets, the toolkit's shared modules are written by one
  target only and imported by the others by a relative path; the importers' `index.ts` does not
  export them. Reason: the rule #371 already applies to a project's own modules (one file, one
  import path per type). Rejected: emitting only the toolkit modules a target uses (#402 option 2;
  still one copy per target).
- **DEC-2:** the owner is named by a per-entry boolean, TOML key `toolkit-typescript`, set on
  exactly one entry that sets `typescript`. Reason: `[tool.rp-generate]` is an array of rows with no
  project-wide place; the flag sits on the row whose folder receives the files. Rejected: the first
  TypeScript entry by order (an implicit owner, moved by reordering the file); a path key on every
  importer (the same folder repeated on each row).
- **DEC-3:** with one TypeScript target, nothing changes, with or without the key. With several, a
  missing owner, a second owner, or the key on an entry without `typescript` is a configuration
  error raised before any step runs, naming the entries and the fix. Reason: the developer wants a
  clear stop rather than a guess (2026-11-27). Rejected: falling back to copies (the drift
  stays, silently).
- **DEC-4:** the owner writes a fixed shared set: the TypeScript of every module of the metamodel
  (`rp.yaml`'s closure) and of the served types (`rp_service.ts` and the modules it imports), whether
  or not its own schema imports them. Reason: an importer may use a toolkit module the owner's schema
  does not; a fixed set needs no other target's schema. Rejected: the union of every target's closure
  (each run would load every other target's schema).
- **DEC-5:** a toolkit module outside the shared set (a technical module a consumer schema imports
  itself) is still written by each target that imports it. Reason: the owner does not write it, so
  only a copy compiles. Rejected: widening the shared set to every technical module (dozens of files
  no client uses).
- **DEC-6:** **BREAKING** for generated TypeScript, flagged in the commit and `CHANGELOG.md` with a
  migration note; no switch keeps the copies (RISK-1).

## Rabbit-holes

- **The toolkit's TypeScript rendered from two roots.** The owner renders the shared set from the
  metamodel root and the served schemas; a target that rendered `rp_core.ts` from its own schema
  wrote it from the consumer's closure. The text must be the same, or the owner's file differs from
  the copies it replaces; a test pins it on the toy (RISK-2).
- **A parallel change.** `consumer-write-rules` (#415) lets a consumer schema import the toolkit's
  technical modules. A served one (`rp_api_entrypoints`) is in the shared set; any other falls under
  DEC-5. Nothing here waits for it.
- **Freshness.** `pyproject.toml` is not a manifest input, so adding or moving the key is not seen
  by `rp-generate --check`; `make check-generated` (regenerate, then diff) sees it. Accepted, as in
  `consumer-friction`.

## No-gos

- A TypeScript package, a path alias or an import path other than relative paths.
- A switch that keeps the copies.
- A CLI flag for the key (it relates entries to each other; flags override one entry).
- Changing which toolkit module a project's own modules import, or the content of any generated
  type.
- Anything of `consumer-write-rules` or `narrowed-slot-override` (parallel changes).

---

## What Changes

- `[tool.rp-generate]` gains the per-entry key `toolkit-typescript` (boolean, absent = false),
  generated from `rp_generation.yaml` like every other key, and checked across entries.
- `rp-generate`'s TypeScript step: in a project with two or more TypeScript targets, the owner writes
  the toolkit's shared modules; every other TypeScript target imports them from the owner's folder
  and writes none.
- **BREAKING** for generated TypeScript: a client importing a toolkit type (`Problem`, `Page`,
  `TenantSummary`, a metamodel type) from an importer's folder imports it from the owner's folder.
- Docs: `architecture/generation.adoc` *Imports between targets*; `user-manual/generate.adoc` (the key
  and the `typescript` output row); `CHANGELOG.md` *BREAKING*.
- The toy library: its domain entry sets `toolkit-typescript = true`; the value and technical trees
  lose their toolkit copies.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `rp-generation`: "TypeScript targets get the service's types" and "A module another target writes as
  TypeScript is imported, not copied" now carry the owner rule; one requirement added, "The toolkit's
  TypeScript has one owner in a project".

## Impact

- Code: `rdf_persistence_generation/extensions/typescript.py`, `rdf_persistence_generation/steps.py`,
  `rdf_persistence_generation/config.py`, `rdf_persistence_generation/manifest.py` (PD-6),
  `rdf_persistence_generation/model/rp_generation.yaml` and its generated artefacts (`make generate`);
  every `rp-manifest.json` (the generator's source hash).
- Toy: `tests/fixtures/library/pyproject.toml`; the trees `web/src/domain/generated/values/` and
  `web/src/services/generated/` and their `rp-manifest.json` files.
- Tests: generator unit and integration tests beside `test_typescript_imports.py` and
  `test_stale_typescript_copy.py`; config tests; scenario-map rows.
- Consumers: a project with several TypeScript targets sets the key once and moves its imports of
  toolkit types to the owner's folder (RISK-1). MWB2's change names this one (D-12).

## Reconciliation (as delivered, PR #425)

| Shaped | Delivered | State |
|---|---|---|
| DEC-1 one owner writes the shared modules, importers import them | `render(..., toolkit, owns_toolkit)`, `steps._toolkit_folder` | delivered, PR #425 |
| DEC-2 per-entry key `toolkit-typescript` | `GenerationTarget.toolkit_typescript`, toy's domain entry | delivered, PR #425 |
| DEC-3 refusals before any step | `config._refuse_toolkit_owner`, called by `_toml_entries`; four refusals, the fourth (two entries share a folder) added by PD-2 | delivered, PR #425 |
| DEC-4 fixed shared set | `typescript._shared_modules`/`_shared_names` (metamodel first, served by `setdefault`) | delivered, PR #425 |
| DEC-5 a module outside the set is still copied | default path of the importer (a name not in the set is kept) | delivered, PR #425; no test of its own (D-7, W2 under the floor) |
| DEC-6 BREAKING with a migration note | `CHANGELOG.md` `[Unreleased]`, PR body, including a consumer before #371 (P5) | delivered, PR #425 |
| RISK-2 the owner's render equals the copies | TC-2b on every shared module; the toy's domain tree byte-identical | delivered, PR #425 |
| TC-1 on the toy's technical tree | the toy imports no toolkit type, so TC-1 is proved through `render` on a temporary schema (D-7, F1) | delivered differently, PR #425 |
| TC-4 `tsc` over the toy | `make typecheck-ts` green locally; the toy carries no toolkit import, so it checks the removals, not a toolkit specifier | delivered, PR #425 |

Not delivered: nothing the shape promised. Also changed: `manifest.py` (PD-6, missing from the
first Impact list), seven stale rows of `tests/audit/scenario-map.csv` dropped by `make
refresh-map`.
