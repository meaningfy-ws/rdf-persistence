# Codebase notes: converter-hardening (secondary; never groomed)

Read on `develop` 25e23156, 2026-11-22, by the planner. Facts the PLAN rests on; line numbers are
of that commit.

## The reader (`rdf_persistence_generation/uml/qea.py`)

- `_open` (l. 163-174) connects with `file:<path>?mode=ro` and maps every `sqlite3.DatabaseError`
  of the first query to `<path> is not an Enterprise Architect .qea (SQLite) file`. A missing
  path raises `OperationalError: unable to open database file`, so a mistyped path reads as "not
  a .qea". An unreadable file (permissions) reads the same.
- `read_qea` (l. 148-160) runs `_check_schema` and `_Reading(...).read()`; a `sqlite3.Error`
  there (a corrupt page, a locked file) is not caught: a traceback.
- `_check_schema` (l. 177-186) takes the names of `sqlite_master` without its `type`: a view named
  `t_object` passes as the table.
- No `pragma trusted_schema` or `query_only` is set.
- `CLASS_TYPE`, `ENUMERATION_TYPE` (l. 108-109) are defined again in `classes.py` (l. 46-47).
- `QeaUsageError` (l. 140) lives here, not in `rdf_persistence_generation/exceptions.py`.

## The writer (`uml/write.py`)

- `write` stages in `tempfile.TemporaryDirectory(dir=out.parent, ...)`: beside `--out`, so a
  read-only parent or another filesystem (`EXDEV` from `os.replace`) fails.
- `_move` moves the files in path order; the report `<root>.uml-report.txt` sorts among them. An
  `OSError` mid-move is not caught: a traceback, old and new files mixed, the old report possibly
  replaced already.
- `_check_staged` runs only `load_role_definitions` and `load_workflow` per file (PD-4 of
  `uml-roles-and-workflows`). `Workflows.from_files(paths, view, rules)`
  (`rdf_persistence/collaboration/services/workflows.py` l. 117-129) is the start-up check; it needs
  a `SchemaView` (`load_schema` in `rdf_persistence/schema/services/schema.py` l. 68 resolves the
  `rdf_persistence/model/<module>` imports the converted root writes) and `AccessRules`.
- `StagedFileRefused` (l. 30) lives here.

## The CLI (`uml/cli.py`)

- Exit 0 written, 1 model problems or `StagedFileRefused`, 2 usage (`UsageError`,
  `PrefixesFileError`, `QeaUsageError`).
- `metamodel_prefixes()` loads the metamodel; `convert` loads it again through `Toolkit`
  (`uml/toolkit.py`). `convert(model, settings, metamodel_prefixes)` has 4 callers in
  `tests/generator`.

## Member class (`uml/slots.py`)

- `_member_roles` (l. 599-620) skips `target == usage.holder.label`; `_fix_member_classes`
  (l. 623-639) fixes one target per holder, two targets are a `toolkit_slot` problem.
- The toolkit's `ReferenceCollection` description (`rdf_persistence/model/rp_collections.yaml`
  l. 22-26): "A collection of collections has the collection class as its member class."
- `rp-reference-collections`, requirement "A collection may nest collections of its own kind": a
  nesting collection holds collections of the same class **and** member class; "A collection whose
  member class is itself a collection class SHALL NOT set `nests`."
- `reference/uml-conventions.adoc#member-class` (l. 400-413) says a role to the own class is
  nesting and stays `has_part`.

## The roles loader (library)

- `load_role_definitions` (`rdf_persistence/access/services/access.py` l. 73-98):
  `path.read_text()` with no encoding; catches `OSError`, `yaml.YAMLError`; a file whose top level
  is a list.
- `read_mapping` (`rdf_persistence/core/services/yaml_files.py` l. 42-61): UTF-8, unique keys
  (`_UniqueKeyLoader`), `UnicodeDecodeError` and `RecursionError` mapped to the caller's error;
  it refuses a non-mapping, so the roles loader cannot call it as it is.
- `rp-access` has no requirement on reading the roles file.

## String constants (#229 "Structure", A-1 in spirit)

- `classes.py` `RP_PATH`, `META`; `slots.py` `OWNED`; `mixins.py` `RP_MIXINS`, `WORKFLOW`;
  `tags.py` `RP_MIXINS` (again), `GRAPH`; `convert.py` `MODULE_KIND`, `DOMAIN`; `workflows.py`
  `WORKFLOW_TAG`. The generated enums are `RpAnnotation`, `ModuleKind`, `GraphKind` in
  `rdf_persistence/core/domain/generated/rp_core.py`.
- `slots.py` l. 542, 577: `assert slot is not None`; `mixins.py` l. 74: `# type: ignore[union-attr]`.

## Module cycles (the separate EPIC generator-module-cycles, #208/#206)

- `convert.py` `_merge`, `_settle`, `_module_graph`, `_note_merges` (l. 147-208) merge packages
  that import each other into one module (D-5 of `uml-to-linkml`), reported as `merged-cycle`; the
  `rp-uml-import` requirement states it. That EPIC changes this code; this one does not touch it.

## Tests

- `tests/generator/unit/test_uml_rules.py` `Row(case, rule, uml, check, overrides)`;
  `test_every_uml_rule_has_a_row` (l. 2994) is parametrised over `UmlRule`, so R-15 and R-22
  (one value `toolkit_slot`) and R-25..R-28 (one value `toolkit_mixins`) are proven by one row each.
- `tests/generator/feature/uml_import.feature`, first scenario "A package with a root and a part".
- `rp-generate` does not read the roles or workflow files (no use of `load_role_definitions` or
  `load_workflow` in `rdf_persistence_generation` outside `uml/`).
- `install_service(schema: Path, rules: AccessRules | Path, workflows: Sequence[Path] = (), ...)`
  (`rdf_persistence/api/entrypoints/service.py` l. 37-104) loads the roles file and the workflow
  files when it is called, before serving.
