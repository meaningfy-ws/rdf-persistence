<!-- Parents: issues #229 (the floor of uml-to-linkml's full review, design.md D-29), #258, #259,
     #260, #261 (the follow-ups of uml-roles-and-workflows, design.md D-11, D-12a, D-14, D-15,
     D-16). Seeds archived verbatim in inputs/seed.md. -->

# EPIC: Harden the UML-to-LinkML converter

**Golden-thread parents:** `openspec/changes/archive/2026-11-21-uml-to-linkml/` (design.md D-29,
"under the floor"; hand-over "Open") and `openspec/changes/archive/2026-11-21-uml-roles-and-workflows/`
(design.md D-11, D-12a, D-14, D-15, D-16); the capabilities `rp-uml-import` and `rp-access`.

## Appetite

**SMALL.** One capability, `rp-uml-import`, touched where it reads, checks and writes, plus the
library's roles loader it relies on and the pages a modeller follows. The converter's structure is
reused as it is. One stage, one pull request.

## Why

`rp-uml2linkml` converts the consumer's real model, but its edges are soft: a mistyped path reads
as "not a .qea file", a read error or a disk error ends in a traceback, a failed write leaves old
and new files mixed, a WAL-mode model gets side files beside it, and the files it writes are never
checked the way the service checks them at start, so a file the converter accepts can still stop
the service. A collection of collections drawn as the toolkit describes it converts without its
member class. A reader of the how-to cannot start the service from it with confidence. The
library reads the roles file in the locale's encoding. Each was found by a review and left under
the floor; the converter is now used, so they cost more each time.

## Solution outline

1. **Read safely.** The reader tells a missing or unreadable file from a file that is not SQLite,
   turns any read error into a usage error, leaves no side file beside the model, and refuses what a
   crafted file could hide (views in place of tables, schema code).
2. **Write all or say so.** Staging happens inside `--out`; the report is moved last, so a missing
   report means an interrupted write; a disk error is one usage line, not a traceback.
3. **Check as the service will.** When a run draws a workflow, the staged roles and workflow files
   are checked together against the staged schema with the library's own start-up check (#259).
4. **A collection of collections** drawn as a lone `dct:hasPart` role to its own class gets its own
   class as `member_class` (#260).
5. **The library reads the roles file as UTF-8**, a bad byte being `InvalidRoleDefinition` (#258).
6. **The cheap half of the review's floor (#229):** errors in `exceptions.py`, generated enums
   instead of repeated strings, no `assert` or `type: ignore` in production code, the metamodel
   read once, and the test gaps the review named.
7. **Docs (#261):** starting the service with converted roles and workflows answered on the
   service-start page and the how-to, then a cold read.

## Key decisions

- **DEC-1:** the deep restructure of #229 (one owner for package paths and exclusion, passes
  returning values instead of filling `Context`, `slots.py` split, the import-graph code out of
  `convert.py`, `Usage`/`Composed` generated or justified, a "convert is pure" contract, indexes
  for repeated scans) is **not** in this EPIC — reason: it moves the converter's structure, which a
  SMALL appetite keeps, and its import-graph half is rewritten by the EPIC generator-module-cycles
  (#208/#206) anyway; rejected: doing it now (MEDIUM, and work thrown away when the cycle merge
  goes). Owner to confirm: `inputs/qa.md` OPEN-1.
- **DEC-2:** a lone `dct:hasPart` role to the collection's own class fixes `member_class` to that
  class; a role to its own class beside a role to another class stays nesting, the other class
  being the member class (as today) — reason: the toolkit's `ReferenceCollection` description and
  `rp-reference-collections` ("a collection whose member class is a collection class SHALL NOT set
  `nests`"); rejected: a nesting tag or stereotype (a new convention for a case the two roles already
  tell apart). Owner to confirm: OPEN-2.
- **DEC-3:** the whole-model check runs in the converter only when the run draws a workflow, on the
  files this run writes, and a refusal fails the run as `StagedFileRefused` does today (exit 1,
  nothing moved); the converter's own PD-5 checks stay first so they can name the EA element —
  reason: #259's proposal; rejected: checking hand-written files left in `--out` (they are reported
  as stale, not the run's).
- **DEC-4:** a disk or folder error while writing is a usage error, exit 2, one
  `rp-uml2linkml: cannot write <path>: <reason>` line — reason: the model is fine, the setup is
  not; rejected: exit 1 (reserved for model problems). Owner to confirm: OPEN-4.
- **DEC-5:** the roles loader reads through the same reader as the workflow loader, so a key given
  twice in one entry is refused too — reason: one way to read the toolkit's YAML files; rejected: a
  UTF-8 fix alone (two readers drift again). Owner to confirm: OPEN-3.

## Rabbit-holes

- **Module cycles.** Anything near `_merge`/`_settle` or the `merged-cycle` line belongs to
  generator-module-cycles. The whole-model check (DEC-3) loads the staged schema with `SchemaView`;
  when that EPIC lets the converter write modules that import each other, the check must still
  load them (`SchemaView` follows cyclic imports; design.md RISK-4). Order: this EPIC can land
  before or after it; neither waits.
- **`immutable=1` on a file EA is writing.** Reading a WAL file whose changes are still in its
  `-wal` file with `immutable=1` would miss them; design.md decides when it is safe.
- **The docs questions of #261** can each grow into a feature ("accept a folder of workflows"); the
  EPIC answers what the code does today and changes no service behaviour.

## No-gos

- The deep restructure listed in DEC-1, including moving any of the import-graph code.
- No change to how packages that import each other are merged, or to the `merged-cycle` line (the
  EPIC generator-module-cycles, #208/#206).
- No new service behaviour for #261 (no folder or glob for `workflows=`, no new start-up check);
  only docs, with a test where a stated behaviour has none.
- No new UML convention (no nesting tag or stereotype).
- No check of hand-written roles or workflow files the run did not write.
- No consumer terms in code, tests or docs.

---

## What Changes

- `rp-uml2linkml` reads the `.qea` without side files and with every read error a usage error;
  it writes into `--out` all or reports which file failed; it checks a drawn workflow with the
  service's start-up check before writing.
- A lone `dct:hasPart` role to the collection's own class now writes `member_class` (a model that
  drew such a role gets one more `slot_usage`; **behaviour change** for such models, DEC-2).
- `load_role_definitions` reads UTF-8 and refuses a bad byte and a key given twice with
  `InvalidRoleDefinition` (**stricter**: a roles file with a repeated key in an entry now stops the
  service at start, DEC-5).
- Converter internals: errors in `exceptions.py`, generated enums for annotation names and values,
  the metamodel read once; tests closing the review's gaps.
- Docs: `user-manual/serve.adoc`, `howto/uml-to-linkml.adoc`, `reference/uml-conventions.adoc`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rp-uml-import`: reading and writing safely (added); the workflow requirement gains the
  whole-model check; the toolkit-reuse requirement gains the collection of collections and
  scenarios for its tenant-root and abstract-root sentences.
- `rp-access`: reading the role definitions file (added).

## Impact

`rdf_persistence_generation/uml/` (`qea.py`, `write.py`, `cli.py`, `slots.py`, `convert.py`,
`context.py`, `classes.py`, `links.py`, `mixins.py`, `tags.py`, `workflows.py`, `toolkit.py`),
`rdf_persistence_generation/exceptions.py`, `rdf_persistence_generation/model/rp_generation.yaml`
(one enum, regenerated), `rdf_persistence/access/services/access.py`,
`rdf_persistence/core/services/yaml_files.py`; tests under `tests/generator/` and
`tests/unit/access/`; three docs pages. No public API signature changes except `convert`'s third
argument (a `Toolkit` instead of the prefixes mapping), which only the CLI and tests call.
