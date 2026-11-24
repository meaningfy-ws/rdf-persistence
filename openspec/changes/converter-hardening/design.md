<!-- PLAN (design half) of converter-hardening. PLAN = this file + tasks.md. -->

> Derives from: the EPIC `converter-hardening` ([proposal.md](proposal.md)), DEC-1 to DEC-5.

## Context

The converter (`rdf_persistence_generation/uml/`) was delivered by `uml-to-linkml` and extended by
`uml-roles-and-workflows`. Both full reviews left findings under the floor; five issues hold them
(`inputs/seed.md`). The facts below are from `inputs/codebase.md` (develop 25e23156). Exit codes
stay as `cli.py` documents them: 0 written, 1 model problems or a refused staged file, 2 unusable
setup.

## Goals / Non-Goals

**Goals:**

- G-1 Every failure of reading the `.qea` and of writing `--out` is one `rp-uml2linkml:` line and
  an exit code, never a traceback (except a converter bug, below).
- G-2 Reading never writes beside the model and never runs code a crafted file holds.
- G-3 An interrupted write is visible: no report in `--out`.
- G-4 A run that draws a workflow writes nothing the service's start would refuse for the
  workflows and roles.
- G-5 A lone `dct:hasPart` role to the own class fixes `member_class` (DEC-2).
- G-6 `load_role_definitions` reads UTF-8 and never lets `UnicodeDecodeError` through.
- G-7 The cheap half of #229 (PD-7) and the test gaps (PD-8).
- G-8 A reader of the how-to can start the service with converted roles and workflows (#261).

**Non-Goals:** the deep restructure (DEC-1); module cycles (no-gos); any new service behaviour.

## Decisions

The EPIC's DEC-1 to DEC-5 hold. Planning decisions:

- **PD-1 Opening the `.qea`** (`qea.py` `_open`). In order:
  1. `path.is_file()` false → `QeaUsageError("<path>: no such file")`.
  2. Read the first 16 bytes (`open(path, "rb")`); `OSError` →
     `"<path> cannot be read: <strerror>"`; not `b"SQLite format 3\x00"` → today's
     `"<path> is not an Enterprise Architect .qea (SQLite) file"`.
  3. Connect read-only: `file:<path>?immutable=1` when no `<path>-wal` file exists beside it,
     else `file:<path>?mode=ro` (a `-wal` file means EA has the model open or did not checkpoint;
     `immutable=1` would ignore the changes in it, and its side files exist already).
  4. `pragma trusted_schema=OFF` and `pragma query_only=ON` before the first query.
  Any `sqlite3.Error` from step 3 to the end of `read_qea` (connect, schema check, every select)
  → `QeaUsageError("<path> cannot be read: <error>")`, the error cut to `SHOWN` characters
  (`rdf_persistence/core/services/yaml_files.py`'s limit, reused).
- **PD-2 Tables only** (`_check_schema`). The table names come from
  `select name from sqlite_master where type = 'table'`; a view (or trigger, index) with a PD-3
  table's name is "has no table <t>", as a missing table is.
- **PD-3 Writing** (`write.py` `write`). In order:
  1. `out.mkdir(parents=True, exist_ok=True)`.
  2. Stage into `tempfile.TemporaryDirectory(dir=out, prefix=STAGING_PREFIX)`: the same
     filesystem as the targets, so `os.replace` never meets `EXDEV`.
  3. Dump, stage, check (PD-4 of `uml-roles-and-workflows`, plus PD-4 below), write the report into
     staging, as today.
  4. Delete `out/<root>.uml-report.txt` if it exists.
  5. Move every staged file but the report, in path order; then move the report last.
  The stale files and leftover staging folders are found before step 2, so the run never reports
  its own staging folder. Any `OSError` raised anywhere in `write` (the stale-file globs included)
  is raised as `OutputError(path, reason)` (new, in `exceptions.py`); `cli.py` prints `rp-uml2linkml: cannot write <path>: <strerror>` and exits 2
  (DEC-4). `<path>` is the file or folder the failing call named (`error.filename`, else `out`).
  The staging folder is removed by the context manager on any exception. A staging folder left by
  a killed run (`out/.uml-write-*`) is reported by the next run as a `stale-file` line "left by an
  interrupted run; delete it", never deleted (it could be another run's, below).
- **PD-4 The whole-model check** (#259, DEC-3; `write.py` `_check_staged`). After the per-file
  loaders pass, and only when `files` holds a `workflows/*.workflow.yaml`:
  `rules = AccessRules(load_role_definitions(staging / "<root>.roles.yaml"))`;
  `Workflows.from_files(sorted(staged workflow paths), load_schema(staging / "<root>.yaml"), rules)`.
  `InvalidWorkflow` → `StagedFileRefused` (exit 1, nothing moved) whose message is
  `the written files would stop the service: <library message>`, with every occurrence of the
  staging folder's path in the library message replaced by `--out`'s path, so a file it names
  (`places`) reads as `<out>/workflows/<f>.workflow.yaml`, never a deleted `.uml-write-*` path.
  A refusal that names no file (`_by_iri`: "class Book shares the class IRI … with a class of
  workflow 'loan' but names workflow 'review'") names one class, the shared class IRI and both workflows (`workflows.py` l. 294-297); the converter
  adds no file to it, because no single file is at fault. The roles file is
  always staged when a workflow is: `workflow_entries` refuses a transition role no drawn role
  defines, so a drawn workflow implies drawn roles; if it is missing anyway, that is a converter bug
  and `load_role_definitions` raises `InvalidRoleDefinition` → `StagedFileRefused`. `write` gets
  the root schema's name from `root_name` (the root is written as `<root_name>.yaml`).
- **PD-5 Member class** (#260, DEC-2; `slots.py` `_member_roles`). Per holder that is a reference
  collection, collect its `dct:hasPart` usages whose range is a converted class: the targets other
  than the holder are the member candidates (as today); when there are none and the holder itself
  is a target, the holder is the member class. A holder with a role to itself and to `Book` keeps
  `member_class: Book` and its self-role stays `has_part` with its `toolkit-slot-kept` line, as
  today. A lone self-role is a member role only when no other collection in the holder's `is_a`
  lineage (an ancestor or a descendant) has a member role; otherwise it stays nesting, as today, so
  #274's `_without_narrowed_parents` never sees it (owner, OPEN-6, 2026-11-24: without this, an
  abstract `Folder` with a self-role and a subclass `Album` with a role to `Photo` fails the run
  "does not narrow", a model that converts today).
- **PD-6 The roles loader** (#258, DEC-5). `yaml_files.py` gains `read_yaml(path, noun,
  error_type) -> object` (today's body of `read_mapping` without the mapping check);
  `read_mapping` calls it and keeps its check and messages. `load_role_definitions` calls
  `read_yaml(path, "role definitions", InvalidRoleDefinition)`, then its own list check. Messages:
  unreadable `cannot read the role definitions <path>: <error>` (unchanged), not UTF-8
  `<path> is not UTF-8 text: …`, bad YAML `<path> is not valid YAML: …` (now cut to `SHOWN`), a
  key given twice the `_UniqueKeyLoader` message, nesting `<path> is nested too deeply to read`.
  How "whatever the locale" is proven without installing a locale: the test runs the loader in a
  subprocess (`sys.executable -X warn_default_encoding`) whose script, after its imports, turns
  `EncodingWarning` into an error around the `load_role_definitions` call only (so a third-party
  import that reads without an encoding cannot fail it), which fails on any read that relies on the
  locale's encoding, and reads back `rédacteur`; the `0xff` and
  duplicate-key cases run in-process.
- **PD-7 The cheap half of #229** (DEC-1 draws the line):
  - `QeaUsageError`, `StagedFileRefused`, `UsageError`, `PrefixesFileError` and the new
    `OutputError` move to `rdf_persistence_generation/exceptions.py`; the old names are not kept
    (only `cli.py`, `write.py`, `qea.py` and tests import them).
  - Annotation names and values come from the generated enums: `RpAnnotation` (`RP_PATH`,
    `OWNED`, `GRAPH`, `MODULE_KIND`, `WORKFLOW`), `ModuleKind.DOMAIN`, `GraphKind.META`
    (`rdf_persistence/core/domain/generated/rp_core.py`). `rp_mixins` and `unique_key` are tags of
    the converter, not annotations, so they stay constants, each defined once (`tags.py`). `CLASS_TYPE` and `ENUMERATION_TYPE` are defined once, in `qea.py`, and imported by
    `classes.py`; `RP_MIXINS` once, in `tags.py`.
  - The left-out reasons (`context.py` `LEFT_NOT_GENERATED`, `LEFT_EXCLUDED`, `LEFT_OUTSIDE`,
    used in `context.py`, `classes.py` and `links.py`) become a LinkML enum `LeftOutReason` in
    `rp_generation.yaml`, regenerated with `make generate` (LinkML is the single source).
  - `slots.py`'s two `assert slot is not None` become a typed lookup (`Toolkit.toolkit_slot(iri) ->
    SlotDefinition`, raising `KeyError` for a caller bug); `mixins.py`'s `# type: ignore` goes the
    same way (`Toolkit.toolkit_class(name)`).
  - The metamodel is read once: `cli.py` builds the `Toolkit` once (`load_toolkit()`, cached) and
    `convert(model, settings, toolkit)` takes it; `Context.__init__` (`context.py` l. 101, which
    calls `load_toolkit()` itself today) takes the toolkit as an argument, and its
    `metamodel_prefixes` comes from `toolkit.prefixes()`, which replaces `cli.metamodel_prefixes()`
    (deleted). Callers that change: `cli.main`; the one test caller of `convert`,
    `tests/generator/uml_model.py` `run` (l. 316, passing `METAMODEL_PREFIXES` from l. 47, which
    goes: it passes `load_toolkit()`); `tests/generator/unit/test_uml_cli.py`
    `test_the_metamodel_prefixes_name_the_toolkit_namespaces` (l. 326), rewritten in place on
    `load_toolkit().prefixes()`, its `metamodel_prefixes` import (l. 11) replaced by
    `load_toolkit` from `uml/toolkit.py` (lane `test-generator`, still proving the three namespaces).
    `naming.resolve_name` keeps its mapping argument, so `test_uml_naming.py`'s own
    `METAMODEL_PREFIXES` (l. 18) stays.
- **PD-8 Test gaps of #229.**
  - `tests/generator/unit/test_uml_naming.py`
    `test_the_name_patterns_are_the_linters`: `CLASS_NAME_PATTERN` and `SLOT_NAME_PATTERN` equal
    the patterns linkml's `standard_naming` lint rule applies (read from `linkml.linter.rules`, as
    the lint step loads them).
  - `Row` (`test_uml_rules.py` l. 54, a frozen dataclass whose last field `overrides` has a
    default) gains a last field `cites: str | None = None` (an `R-n`), so no existing row changes
    unless it is chosen to cite. `test_every_uml_rule_has_a_row` becomes
    `test_every_cited_rule_has_a_row`, parametrised over the `R-n` the `UmlRule` descriptions cite
    (a range `R-25..R-28` expanded), asserting at least one row in `ROWS`, `ROLE_ROWS` or
    `WORKFLOW_ROWS` has `cites` equal to it. Which rows carry it: for each cited `R-n`, at least
    one row of that rule's `ROWS_R<n>` list (for R-15/R-22 one row proving a toolkit slot by IRI and
    one proving `dct:identifier`; for R-25..R-28 one row each: default mixins, `rp_mixins`,
    `workflow` tag, drawn generalisation to a toolkit class), adding a row only where no existing
    one proves that `R-n` (expected: R-22, R-26, R-27, R-28).
  - The feature's first scenario gains a generalisation, a dependency and Thens on the URIs and the
    cardinalities; a Then step holds one assert; every assert in the R-30 rows and the two toolkit
    tests the review named has a message; the stage-2 spec sentences (tenant root, abstract root)
    get scenarios (spec delta) and feature tests.

### Error matrix

| Failure mode | How it is detected | Expected handling | Exit |
|---|---|---|---|
| `.qea` path does not exist, or is a folder | PD-1 step 1 | `rp-uml2linkml: <path>: no such file` | 2 |
| `.qea` not readable (permissions) | PD-1 step 2, `OSError` | `rp-uml2linkml: <path> cannot be read: Permission denied` | 2 |
| Not SQLite (an `.eap` Jet file, a text file, empty) | PD-1 step 2, header | `rp-uml2linkml: <path> is not an Enterprise Architect .qea (SQLite) file` (unchanged) | 2 |
| SQLite header but corrupt, or locked, or an error mid-read | PD-1, `sqlite3.Error` | `rp-uml2linkml: <path> cannot be read: <error>` | 2 |
| WAL-mode `.qea`, no `-wal` file | PD-1 step 3 `immutable=1` | read; no `-shm`/`-wal` created | 0 |
| WAL-mode `.qea` with a `-wal` file (EA open) | PD-1 step 3 | read with `mode=ro`, as today; the side files were there already | 0 |
| EA writes the file during the read | `sqlite3.Error` (`mode=ro` or `immutable=1`) | as "cannot be read"; re-run after EA saves (RISK-1) | 2 |
| Crafted file: a view named `t_object` | PD-2 | `rp-uml2linkml: <path> has no table t_object` | 2 |
| Crafted file: schema code (a view calling a function, a trigger) | `trusted_schema=OFF`, `query_only=ON`, PD-2 | not run; a view is refused by PD-2; a write is refused by SQLite | 2 |
| `--out` cannot be created, is a file, or is not writable | PD-3 step 1-2 `OSError` | `rp-uml2linkml: cannot write <out>: <reason>`; nothing changed | 2 |
| Disk full or error while dumping or staging | PD-3 step 3 `OSError` | same line naming the staged file; staging removed; `--out` unchanged | 2 |
| Disk error while moving | PD-3 step 5 `OSError` | same line naming the target; files moved so far stay, no report in `--out` (G-3); a re-run rewrites all (I-2) | 2 |
| A subfolder of `--out` (e.g. `workflows/`) on another filesystem | `OSError` `EXDEV` at the move | as a disk error while moving | 2 |
| A run was killed mid-write | the next run finds `out/.uml-write-*` | `stale-file` line "left by an interrupted run; delete it" | 0 |
| Two runs into one `--out` at once | — | not supported (how-to says so); each stages in its own folder, the last mover wins file by file | — |
| Drawn workflows the start-up check refuses (a rule PD-5 of `uml-roles-and-workflows` does not repeat) | PD-4, `InvalidWorkflow` | `rp-uml2linkml: the written files would stop the service: <library message, classes and workflows named, files as <out>/…>`; nothing moved | 1 |
| The staged root schema cannot be loaded by `SchemaView` | exception from `load_schema` | traceback: a converter bug (the schemas were just built from validated definitions) | — |
| A lone self-role on a class that is not a reference collection | PD-5 `_is_collection` false | plain `has_part` use, as today | 0 |
| A self-role and roles to two other classes | `_fix_member_classes` | `[toolkit_slot] Shelf: dct:hasPart roles to Book and Map: …` (unchanged) | 1 |
| Roles file with a byte the encoding cannot decode | PD-6 | `InvalidRoleDefinition: <path> is not UTF-8 text: …` at `install_service` | — |
| Roles file with a key twice in an entry | PD-6 | `InvalidRoleDefinition` naming the key (stricter, DEC-5) | — |
| The run is repeated after any failure above | — | safe: the converter is stateless and its output byte-identical (I-2) | — |

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Catch `Exception` around the reader or writer | Catch `sqlite3.Error`, `OSError` only | A converter bug must stay a traceback |
| Delete `out/.uml-write-*` left by another run | Report it | It may be a concurrent run's staging |
| Map every `sqlite3.DatabaseError` to "not a .qea" | PD-1's four messages | The seed's complaint (#229) |
| Re-implement `Workflows._check` rules in the converter | Call `Workflows.from_files` | The service's check is the truth (#259) |
| Fix `member_class` for a self-role beside another role | Only a lone self-role (PD-5) | That pair is nesting (DEC-2) |
| Write enum values as strings | The generated enum's `.value` | A-1 of `uml-to-linkml` |
| Touch `_merge`, `_settle` or the `merged-cycle` line | Leave them | generator-module-cycles owns them |
| Leave a new usage message untested | Assert the matrix line exactly, as the existing `test_uml_cli.py` tests do | The matrix text is the converter's contract with the modeller |

### Worked examples

- `rp-uml2linkml modle.qea …` (typo) → `rp-uml2linkml: modle.qea: no such file`, exit 2.
- A WAL-mode `library.qea`, EA closed, no `library.qea-wal` → read, and `ls` shows no new file.
- `--out` on a full disk at the third move → `rp-uml2linkml: cannot write out/app_shelves.yaml: No
  space left on device`, exit 2; `out/app.uml-report.txt` is absent; a re-run after freeing space
  writes the same bytes and the report.
- `«root» lib:Shelf` mixing `ReferenceCollection` with only a `dct:hasPart` role to `Shelf` →
  `slot_usage: {member_class: {equals_string: Shelf}}`, no `toolkit-slot-kept` line for the role.
- A roles file in UTF-8 with `role: rédacteur` on a `cp1252` host → loads `rédacteur`; a file with
  byte `0xff` → `InvalidRoleDefinition: roles.yaml is not UTF-8 text: …`.

### Idempotency

The converter is stateless (I-2): any failure above is retried by re-running it, and a successful
run's output is byte-identical to a run on a clean `--out`. Moving the report last makes the report
the marker of a complete write; it is the only file deleted before the moves, and it is rewritten
by the same run.

### Test coverage of the spec deltas

| Scenario | Test (tier) |
|---|---|
| rp-uml-import "a missing model file" | `test_uml_qea.py::test_a_missing_path_is_named_as_missing` (unit) |
| "a read error" | `test_uml_qea.py::test_a_corrupt_page_is_a_read_error_not_a_traceback` (unit) |
| "no side files" | `test_uml_qea.py::test_reading_a_wal_model_leaves_no_side_files` (unit) |
| "a view in place of a table" | `test_uml_qea.py::test_a_view_named_like_a_table_is_refused` (unit) |
| "an interrupted write" | `test_uml_write.py::test_a_failed_move_leaves_no_report_and_names_the_file` (unit) |
| "an output folder that cannot be written" | `test_uml_cli.py::test_an_unwritable_out_is_a_usage_error` (unit) |
| "a workflow the service would refuse" | `test_uml_write.py::test_the_start_up_check_refuses_a_staged_workflow` (unit) |
| "a collection of collections" | `test_uml_rules.py` row "a lone role to its own class fixes member_class" (unit) + feature |
| "a role to its own class in a collection hierarchy" | `test_uml_rules.py` rows "a self-role on an abstract collection whose subclass draws its own role stays nesting", "a subclass's self-role under a parent that fixes a member class stays nesting" (unit) |
| "an abstract collection narrowed by its subclasses" | carried unchanged from #274; its existing rows and `test_uml_generate.py` |
| "a tenant root", "an abstract root" | `tests/generator/feature/test_uml_import.py` (feature) |
| rp-access "a non-ASCII role", "bytes that are not UTF-8", "a key given twice" | `tests/unit/access/test_access_roles.py` (unit) |

Tests moved or rewritten: `test_every_uml_rule_has_a_row` is rewritten in place as
`test_every_cited_rule_has_a_row` (still in `tests/generator/unit/`, CI lane `test-generator`,
proving every cited rule has a row); the R-15/R-22 and R-25..R-28 rows it covered stay and gain
siblings. The feature's first scenario is extended in place (lane `test-generator`). The tests of
`QeaUsageError` and `StagedFileRefused` change their import only (same lane). `test_uml_qea.py::test_a_missing_file_is_not_an_ea_file` (l. 423) asserts
the behaviour PD-1 changes: it is rewritten as `test_a_missing_path_is_named_as_missing` (same
file, lane `test-generator`, now proving the "no such file" line). `test_a_text_file_is_not_an_ea_file`
and `test_uml_cli.py::test_a_file_that_is_not_sqlite_is_a_usage_error` stay unchanged and keep
proving the "not a .qea" line for a non-SQLite file.

## Risks / Trade-offs

- **RISK-1** EA writes the model during a read; with `immutable=1` SQLite may read a torn page.
  Likelihood low (the modeller runs the converter after saving), impact a usage error or, at worst,
  a model read half old; mitigation: `immutable=1` only without a `-wal` file (PD-1), and the
  how-to says to save and close EA first. Accepted.
- **RISK-2** `pragma trusted_schema` needs SQLite ≥ 3.31; an older system SQLite ignores it
  silently. Likelihood low (Python 3.12 builds ship newer), impact a crafted view could call a
  function; mitigation: PD-2 refuses views by name, `query_only` refuses writes. Accepted.
- **RISK-3** DEC-2 changes the output for a model that drew a lone self-role meaning nesting: its
  collections now have `member_class` = their own class and refuse `nests` data of `Book` shelves.
  Likelihood low (the conventions page told modellers to draw the member class); impact a service
  refusing data after regeneration; mitigation: the conventions page and the `CHANGELOG.md` `[Unreleased]` entry of task 1.9 state it;
  owner confirms (OPEN-2).
- **RISK-4** generator-module-cycles lets modules import each other; PD-4's `load_schema` must
  then load them. Likelihood of breakage low (`SchemaView` follows imports with a visited set);
  mitigation: that EPIC's converter task re-runs `test_the_start_up_check_refuses_a_staged_workflow`
  on a cyclic pair; named in its rabbit-holes by this EPIC's hand-over.
- **RISK-5** PD-4 adds a `SchemaView` load to a run that draws a workflow (≈ 1 s on the toolkit's
  metamodel). Likelihood certain, impact small; accepted (runs only with a workflow).
- **RISK-6** DEC-5 makes a hand-written roles file with a repeated key stop the service at start.
  Likelihood low, impact a start failure naming the key (it was silently last-wins); accepted,
  with the `CHANGELOG.md` `[Unreleased]` entry of task 1.9.
- **RISK-7** The #229 floor items in PD-7/PD-8 outgrow SMALL. Mitigation: PD-8's feature and spec
  scenario additions are cut first, to a follow-up issue, by the lead; PD-1 to PD-6 are not cut.

## Open Questions

None for the PLAN; the owner's questions are `inputs/qa.md` OPEN-1 to OPEN-4, and the PLAN is
complete under their recommended answers.

## Delivery decisions

- **D-1** (lead, stage 1) The task gate (`make test-changed check-quality`) could not finish for
  any builder: other sessions loaded the machine (load ≈ 20), `test-changed` widened to the fast
  suite because every converter edit regenerates manifests in every package, and the 120 s
  pytest timeout fired in unrelated library tests that pass alone. The lead re-ran each task's
  affected tests (T1, named in each commit) and relies on `make check-all` before the PR.
- **D-2** (lead) Builders worked in separate worktrees; the lead applied each task's source and
  tests to the stage branch and ran `make generate` there (P-0003), so the regenerated manifests
  never conflict.
- **F-T1** (tester after 1.3, Critical, accepted) A read-only `--out` printed `cannot write
  <out>/.uml-write-…: Permission denied`, naming the staging folder that `tempfile` failed to
  create and that does not exist. The error-matrix row "`--out` … is not writable" says
  `cannot write <out>`. Fix: an error naming the staging folder itself names `out`; an error
  naming a file inside staging keeps naming that file (row "Disk full … while staging"). Kept
  tests: `test_a_read_only_out_is_an_output_error_naming_out`,
  `test_the_command_exits_two_with_one_line_for_a_read_only_out`.

Under the floor:

- **F-T2** (tester, Warning) An `OSError` with no `errno` raised by the move loses its message
  (`[Errno None] None`). Only an injected `move` raises one; `os.replace` always sets `errno`.
  Its test `test_a_move_error_without_errno_keeps_its_message` is deleted.
