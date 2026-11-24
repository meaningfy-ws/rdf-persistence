# Seeds: converter-hardening (secondary; never groomed)

The issues below are archived verbatim (body and comments), fetched on 2026-11-22 with
`gh issue view <n> --json ...`. The EPIC (`../proposal.md`) supersedes them but does not replace
them. Codebase notes made while shaping are in `codebase.md`; the open questions in `qa.md`.

## #229 uml-to-linkml hardening: the review's floor

State: OPEN. Labels: .

### Body

Follow-up of `uml-to-linkml` (#196, PRs #212 and #228), accepted by the developer on 2026-11-21 with this follow-up. The full review of the UML converter (`rdf_persistence_generation/uml/`) left these findings below the Critical floor; each is one line in the archived change's `design.md` D-29. Nothing is broken today; they make the next change harder, or are edge cases.

**Structure**
- The reader (`qea.py`) and the converter (`modules.py`, `classes.py`, `links.py`) both own package paths, exclusion, admission and the association-class test (D-22 W-2, again). The reader should emit each package's path and exclusion once.
- `Context` is filled pass by pass in an order nothing enforces; reordering `convert()` silently computes wrong results. Passes could return values the next pass takes as arguments.
- `convert` loads the toolkit itself, and the metamodel is read twice (CLI and toolkit). The CLI could build the `Toolkit` once and inject it.
- `Usage` (slots.py) and `Composed` (mixins.py) are hand-written data classes that D-24 did not keep; generate them or record why not.
- `slots.py` (~570 lines) holds multiplicity, shapes, XSD typing, shared-slot homes and toolkit-slot reuse; the import-graph code sits in `convert.py`; the boundary geometry is in `qea.py`.
- Annotation names and values (`rp_path`, `graph`, `meta`, `owned`, `module_kind`, `domain`, …) are written as strings, not taken from the generated `RpAnnotation`, `GraphKind` and `ModuleKind` enums (A-1 in spirit); `RP_MIXINS`, `CLASS_TYPE` and `ENUMERATION_TYPE` are each defined twice; the left-out reasons are a closed set without an enum.
- Shared helpers (`annotation`, `description_of`) are imported across peer passes; the "no note" rule is written three times; no import contract states that the converter passes are pure.

**Robustness**
- A disk error while moving files into `--out` leaves old and new files mixed; staging beside `--out` fails across filesystems (EXDEV) or when the parent is not writable. Stage inside `--out`, move the report last, and catch `OSError`.
- Every SQLite error reads as "not a .qea file", a mistyped path included; errors after the open escape as a traceback.
- `mode=ro` on a WAL-mode `.qea` leaves `-shm`/`-wal` files beside the model (`immutable=1` would avoid it).
- Harden the reader against a crafted `.qea` (`trusted_schema=OFF`, `query_only`, tables only).
- Two exception classes live outside `rdf_persistence_generation/exceptions.py`.
- An `assert` and a `type: ignore` in production code; repeated scans an index would avoid on a large model.

**Tests**
- No test pins the converter's name patterns to linkml's linter patterns.
- `test_every_uml_rule_has_a_row` counts enum values, not rules R-n; the feature's first scenario lacks a generalisation, a dependency and URI/cardinality Thens; several Then steps bundle asserts; some asserts lack messages; the stage-2 spec sentences have no scenario of their own.


### Comments

None.


## #258 load_role_definitions reads the roles file in the locale's encoding

State: OPEN. Labels: bug.

### Body

## Summary

`load_role_definitions` reads the roles file in the locale's encoding and lets `UnicodeDecodeError` through. `load_workflow`, by contrast, goes through `read_mapping` (`encoding="utf-8"`, decode errors mapped to the loader's own error).

## Where

- `rdf_persistence/access/services/access.py`, `load_role_definitions`: `path.read_text()` with no encoding. It catches only `OSError` and `YAMLError`.
- Compare `rdf_persistence/core/services/yaml_files.py` (`read_mapping`): UTF-8, and `UnicodeDecodeError` becomes the loader's error.

## Failure

The roles file is written as UTF-8. `rp-uml2linkml` writes `<root>.roles.yaml` with `allow_unicode=True`, and a hand-written file may hold non-ASCII text too. On a host whose locale is not UTF-8 (cp1252, for example):

- a role such as `rédacteur` is decoded wrongly and accepted as different text;
- a byte the locale cannot decode raises `UnicodeDecodeError`, a traceback instead of `InvalidRoleDefinition`.

## Fix

Read with `encoding="utf-8"`, ideally through `read_mapping`, and turn a decode error into `InvalidRoleDefinition`. Add a test with a non-ASCII role and one with invalid bytes.

## Found by

The full review of `uml-roles-and-workflows` (L1, D-11). The converter does not work around it; it relies on the library's loader (PD-4).


### Comments

None.


## #259 rp-uml2linkml: run the library's whole-model workflow check before writing

State: OPEN. Labels: enhancement.

### Body

## Summary

`rp-uml2linkml` checks the files it writes only with the per-file loaders (`load_role_definitions`, `load_workflow`), as PD-4 of `uml-roles-and-workflows` decided. The library's whole-model checks at service start (`Workflows._check` and `Workflows._by_class` in `rdf_persistence/collaboration/services/workflows.py`) never run on the converter's output. The converter repeats today's rules itself (PD-5).

## Failure

Suppose the library tightens `Workflows._check`, for example refusing a transition from a state to itself, or requiring a transition role at aggregate level. `rp-uml2linkml` then keeps exiting 0, and the consumer's `install_service(rules=..., workflows=...)` fails at service start. The error names a written file, not the EA diagram or transition.

## Proposal

In `write`'s staged check, when the run draws a workflow, also build `AccessRules(load_role_definitions(staged_roles))` and run `Workflows.from_files(staged_workflows, SchemaView(staged_root_schema), rules)`. A refusal is `StagedFileRefused`, as for the per-file loaders. The converter's own PD-5 checks stay, so they can name the EA element first.

This changes PD-4 of `uml-roles-and-workflows`.

## Source

The full review of `uml-roles-and-workflows` (L3 W1). The developer chose a follow-up issue (D-12a).


### Comments

None.


## #260 rp-uml2linkml: a reference collection's role to its own class fixes member_class

State: OPEN. Labels: enhancement.

### Body

## Summary

Follow-up to #241. `rp-uml2linkml` fixes a reference collection's `member_class` from its `dct:hasPart` role to another converted class. A role to the collection's own class (nesting) leaves `member_class` unfixed. The toolkit's own `ReferenceCollection` description says: "A collection of collections has the collection class as its member class."

## Expected

A reference collection whose only `dct:hasPart` role points at its own class gets `slot_usage: {member_class: {equals_string: <its own class>}}`.

Open points for this issue:
- what a role to its own class together with a role to another class means: today that is nesting plus a member class;
- how `nests` relates: today nesting is stated with `nests`.

## Where

`rdf_persistence_generation/uml/slots.py`, `_member_roles`: today it skips `target == holder`. Docs: `reference/uml-conventions.adoc#member-class`.

## Source

The developer, after #247 (D-14 of `uml-roles-and-workflows`).


### Comments

None.


## #261 docs: starting the service with converted roles and workflows

State: OPEN. Labels: documentation.

### Body

## Summary

A cold reader of `howto/uml-to-linkml.adoc`, after `uml-roles-and-workflows`, could convert a model with roles and workflows but could not start the service from the page with confidence. The open points belong to the service-start docs (`user-manual/serve.adoc`), which the how-to links:

- **Paths:** what the relative paths given to `install_service` (`schema=`, `rules=`, `workflows=`) are relative to at run time.
- **Workflow list:**
  - whether `workflows=` must list every file under `workflows/` by hand (a folder or glob is not accepted);
  - what happens to a file left out;
  - whether a workflow no class names is still loaded.
- **Bad files:** what the service does at start when the roles or workflow files are wrong, stale or missing.
- **Smallest setup:** the smallest working composition root (`store`, `files`, `identity`, `verifier`, `settings`) for a first run.
- **Notes:** whether `no-note` applies to role-definition Objects and to Statechart states and transitions, and whether `rp-generate --check` reads the roles and workflow files at all.

## Proposal

Answer each point in `serve.adoc`, or in the how-to's step 5 where it is conversion-specific. Then have a fresh cold reader follow the how-to again.

## Source

The cold reader's second read in `uml-roles-and-workflows` (D-13, D-15).


### Comments

None.


