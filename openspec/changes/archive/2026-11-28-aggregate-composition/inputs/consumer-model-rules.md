<!-- Secondary input, never groomed: the consumer's developer guide, "The model rules" (develop/index.adoc l.99-128, commit 7a51e99), and its tools/ea/README.md (the conventions C-1..C-13), quoted 2026-11-28. -->

=== The model rules

* The Enterprise Architect model `docs/mwb2_ea_model_v1.qea` is the source of the domain model; the
  LinkML in `models/` is generated from it (ADR-008). One converted module per EA package, several
  aggregates each (the xref:architecture/model.adoc#generated[model page] lists the files); the
  hand-written files are `workbench.yaml` (the served root), `mwb2_prefixes.yaml` and
  `technical/api.yaml`. Access, the roles (ADR-002) and the workflows are converted from EA too.
* Every model artefact is generated: the LinkML modules, Python classes, SHACL shapes, the JSON-LD
  context, the TypeScript types, the diagrams. Generated folders and converted modules are never
  edited; CI regenerates and fails on a difference (`make check-generated`).
* No hand-written models: no `BaseModel`, enum, dataclass, `TypedDict` or `NamedTuple` in `mwb2/`,
  and no hand-typed data types in `frontend/`. Data goes through the generated models, not bare dicts.
* A changed model should break a test. If it does not, a test is missing.
* A converter or generator that produces the wrong thing is fixed in rdf-persistence, never patched
  here.

To change a data class:

. Edit the model in EA, following the conventions in `tools/ea/README.md`
  (`python3 tools/ea/qea_conventions.py docs/mwb2_ea_model_v1.qea models/mwb2_prefixes.yaml`
  checks them), then close EA.
. Run `make generate`: it converts EA (`make convert-model`), then runs `rp-generate`.
. Read the converter's report, `models/mwb2.uml-report.txt`, for anything it left out or folded into
  a toolkit slot. A refusal names the EA element and the rule.
. Add conformance cases for any new constraint kind, and run the tests.
. Commit the `.qea`, the converted YAML and the generated code together. A change that needs a new
  schema version raises it in `models/mwb2_prefixes.yaml`
  (xref:develop/rdf-persistence.adoc#schema-change[Changing the schema]).

== Where the code goes

---

# EA model tools

The domain model is drawn in Enterprise Architect: `docs/mwb2_ea_model_v1.qea`, package `MWB2`. A `.qea`
file is a SQLite database; these scripts read it with Python's standard library only.

| Script | What it does |
|---|---|
| `qea_dump.py` | Prints every MWB2 diagram as text: elements, attributes, notes, links. `python3 tools/ea/qea_dump.py docs/mwb2_ea_model_v1.qea > temp/ea-dump.md` |
| `qea2puml.py` | Exports MWB2 diagrams to PlantUML, one file per diagram, for the text mirror in the spine. `python3 tools/ea/qea2puml.py docs/mwb2_ea_model_v1.qea openspec/changes/domain-model-v2/analysis/draft-6 project resources business source target conceptual-mapping technical-mapping packaging validation access` (the `workflows` Statechart is not exported: its name equals the class diagram `conceptual-mapping`) |
| `qea_conventions.py` | Checks the model against the conventions the UML converter needs (v2-02 design.md, C-1..C-13); one Markdown row per convention, exit 1 on a failure. `python3 tools/ea/qea_conventions.py docs/mwb2_ea_model_v1.qea models/mwb2_prefixes.yaml` |

All three are read-only. Close or reload EA after any script that writes the file (`Ctrl+Shift+F11`).

The converter is not here: `make convert-model` runs rdf-persistence's `rp-uml2linkml` on the
`.qea` and writes `models/mwb2*.yaml` and its report; `make generate` runs it, then `rp-generate`.
A model change is made in EA and regenerated, never by editing those files (`develop/index.adoc`,
section "The model rules").

## `history/`

The one-off scripts that changed the model during the tandem sessions of 2026-11-18/19, kept as a
record of what was done and why (each script's docstring says what it changed, and the matching round
is in `openspec/changes/domain-model-v2/inputs/epic-session.md`). They are not meant to be run again:
most refuse to run twice.

**Never run `history/puml2qea.py` on the current model:** it was the first import of draft 5 and wipes
everything under MWB2's sub-packages before writing.
