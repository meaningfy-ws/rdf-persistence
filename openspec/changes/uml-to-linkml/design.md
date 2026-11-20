<!-- PLAN (design half) of uml-to-linkml. PLAN = this file + tasks.md.
     Evidence: read-only probes of a real EA file (temp/uml-probe/*.py, run 2026-11-20 against the
     first consumer's model; results quoted as counts only, no consumer names). -->

> Derives from: EPIC `uml-to-linkml` ([proposal.md](proposal.md)), issue #196; spec delta
> [specs/rp-uml-import/spec.md](specs/rp-uml-import/spec.md).

# Design: uml-to-linkml

## Context

No UML importer exists. The generator package `rdf_persistence_generation/` holds `rp-generate`
([cli.py](../../../rdf_persistence_generation/cli.py)), its steps
([steps.py](../../../rdf_persistence_generation/steps.py): lint, boundary, hard, rules, lock check,
renderers) and its records in
[model/rp_generation.yaml](../../../rdf_persistence_generation/model/rp_generation.yaml)
(`CheckProblem`, `GeneratedFile`, the view-models). The toolkit metamodel is
`rdf_persistence/model/rp*.yaml`; `rp.yaml` imports every module.

Facts the PLAN rests on (read 2026-11-20, `develop` `c671fefb`):

| # | Fact | Where |
|---|---|---|
| F-1 | Class annotations are the `RpAnnotation` values whose description starts "Class annotation": `graph`, `database`, `rp_path`, `rp_iri_type`, `rp_unlabelled`, `rp_writes`, `workflow` | `rdf_persistence/model/rp_core.yaml` `RpAnnotation` |
| F-2 | Allowed annotation values already live in one table, `ALLOWED_ANNOTATIONS`, plus `PATTERNED_ANNOTATIONS` (checked against the `url_segment` pattern, `_segment_pattern()`) | `checks/hard.py:72-99, :208` |
| F-3 | The hard check refuses a `slot_usage`, attribute or alias of a **toolkit-filled** slot on any stored class. Toolkit-filled = annotated `toolkit_filled: true`, read at run time; today eight: `was_associated_with`, `started_at_time`, `ended_at_time`, `generations`, `invalidations` (`rp_provenance`), `from_state_iri`, `to_state_iri` (`rp_discussion`), `transition_comment` (`rp_workflow`). `generated_at_time` (`Provenanced`) is **not** annotated: the application writes it, so the converter may narrow it | `checks/toolkit_filled.py`; `rdf_persistence/model/rp_provenance.yaml` `generated_at_time`; spec `rp-generation` "A consumer does not redefine what the toolkit fills" |
| F-4 | Every root or owned class must include `Described`; `rp_unlabelled: true` only makes its `label` optional | `checks/hard.py` `_described_problems`; `schema_structure.apply_defaults` |
| F-5 | Every class, slot, enum needs `title` and `description`; every permissible value also `meaning` | `checks/hard.py` `_schema_problems`, `_value_problems` |
| F-6 | A `unique_keys` entry on a root needs `rp_unique_scope: tenant`; on a non-root, no scope is the in-aggregate key; `consider_nulls_inequal: false` is refused today | `checks/hard.py` `_key_problems`, `_scoped_key_reasons` |
| F-7 | Lint `standard_naming`: classes and enums `[A-Z][a-zA-Z0-9]+`, slots and permissible values `[a-z][_a-z0-9]+`; `canonical_prefixes` refuses `dct` for `dcterms` | `rdf_persistence_generation/lint.yaml`; linkml `linter/rules.py` `PATTERNS` |
| F-8 | The boundary check already accepts a root that is `is_a: Activity` with `AggregateRoot` (TC-102 `activity-root`) | `tests/generator/unit/test_boundary_check.py` `PASSING` |
| F-9 | Owned slots are written `owned: true` and `inlined_as_list: true` when multivalued | `tests/fixtures/library/books.yaml` `chapters` |
| F-10 | pydantic generation is split, one Python module per schema module (`pydantic_split`) | `extensions/pydantic_split.py` |
| F-11 | Toolkit modules are imported as `rdf_persistence/model/<module>` and resolved by the metamodel import map | `tests/fixtures/library/books.yaml` `imports` |
| F-12 | `rdf_persistence_generation.{cli,config,…}` import no `linkml` (only `linkml_runtime`): contract `works-without-the-generate-extra` | `.importlinter` |

### What the real EA file shows (rabbit-hole: boundaries)

Probe `temp/uml-probe/{boundaries,members,scoped,cycles}.py` on the first consumer's `.qea`
(SQLite, 2.99 MB, read with `mode=ro`), converted subtree = 12 packages:

| Question | Evidence |
|---|---|
| Is a boundary model containment? | **No.** Boundaries are `t_object` rows (`Object_Type='Boundary'`, `Stereotype` NULL); every class inside one has `ParentID=0` and its own `Package_ID`. Nothing in `t_object`, `t_connector` or `t_xref` links a class to a boundary. |
| Then how? | **Geometry** on `t_diagramobjects` (`RectTop`, `RectLeft`, `RectRight`, `RectBottom`). Each of the 27 boundaries is placed on exactly one diagram; no boundary is nested in another; no class lies in two boundaries; no class shown on a boundary's diagram straddles its edge. |
| Coordinates | `RectTop > RectBottom` on all 520 placements (y grows negative downward). The reader normalises with `min`/`max`, so either orientation works. |
| Roots per boundary | 23 boundaries hold exactly one «root»; 1 holds a «tenant root» and its parts; 3 (one package) hold classes with no stereotype. 23 hold only their root, 4 also hold 1–2 parts. |
| Boundary names | "Aggregate: <class>" in 24 of 27: a convention, not data. Not read. |
| Composite associations | None: `SourceIsAggregate = DestIsAggregate = 0` on all 75 associations; no `Aggregation` connector. Boundaries are the only ownership the model uses. |
| Stereotypes | In `t_object.Stereotype` (single): `root`, `tenant root`, `loaded graph`, one enumeration `workflow states`, one empty string. `t_xref` holds no further stereotype for this subtree. |
| Tagged values | `t_objectproperties` (`Property`, `Value`): `graph`, `workflow`, `rp_mixins` (×4), `rp_unlabelled` (×3). |
| Associations | 70, all `Direction='Source -> Destination'`, role only at the destination (`DestRole`, prefixed), `DestCard` ∈ {`0..*`, `0..1`, `1`, `1..*`}, none missing. |
| Attributes | All prefixed, types `xsd:string|anyURI|boolean|date|dateTime|nonNegativeInteger`, bounds in `LowerBound`/`UpperBound` (`0|1`, `1|*`). Enumeration literals have `Stereotype='enum'`, empty type; 21 of 27 prefixed. |
| Dependencies | 7, all class → enumeration, named by `DestRole` (SEMIC style). |
| Generalisations | 25, one parent each; parents include one drawn `rp:` class and drawn `skos:`/`sh:` classes. |
| Notes | 41 classes, 36 attributes, 65 connectors carry a `Note`/`Notes`; no HTML markup. |
| Shared names | 10 role names and 4 attribute names occur on several classes; 9 names span packages, and for each one package is reached by all the others. |
| Import cycles | **15 package pairs refer to each other in a cycle** (associations, generalisations, dependencies). See PD-14 and SPIKE-2. |

## Goals / Non-Goals

**Goals**
- G-1: `rp-uml2linkml` converts a `.qea` package subtree into one `module_kind: domain` LinkML
  module per package plus a root schema, by the rules R-1..R-29 below.
- G-2: on the generic fixture model, the output passes `rp-generate`'s lint, boundary, hard and rules
  steps unchanged (stage 1: lint and boundary; stage 2: all four).
- G-3: a second run on an unchanged model writes byte-identical files.
- G-4: an element no rule maps fails the run, naming element and rule; nothing is written.
- G-5: DEC-4 settled by SPIKE-1 with a recorded pass or fail.

**Non-Goals**
- XMI, LinkML → UML, diagram output (no-gos). Reading diagrams beyond boundary rectangles.
- Attribute and connector tagged values (`t_attributetag`, `t_connectortag`): no rule uses them.
- Re-implementing `rp-generate`'s checks in the converter (anti-pattern A-3).
- Any change to `rdf_persistence/` unless SPIKE-1 or SPIKE-2 requires it, then as its own task.

## Rule table (open until stage 2 starts: DEC-5)

Sources: **B** = issue body table, **C1..C4** = the four comments in
[inputs/seed.md](inputs/seed.md#comments). R-1..R-13 follow the body's row order and R-14..R-19
comment 1's, so the consumer's own numbers (it cites "rule 13", "rule 15", "rule 17") are ours.
Each rule is one member of the `UmlRule` enum (PD-2); a failure names it. A rule added before the
freeze is appended as R-30, R-31… with its source and date; the freeze date is written here by task
2.1. Stage = where it is built.

| Id | UML | LinkML | Source | Status | Stage | How (PD) |
|---|---|---|---|---|---|---|
| R-1 | package | module `<root>_<package>.yaml`, `module_kind: domain`; a root schema importing them | B | active | 1 | PD-5, PD-14 |
| R-2 | class `pfx:Name` | class `Name`, `class_uri: pfx:Name`; a foreign prefix keeps its IRI | B | active | 1 | PD-6 |
| R-3 | abstract class | `abstract: true` | B | active | 1 | — |
| R-4 | generalisation | `is_a` first parent, `mixins` others | B | narrowed by PD-30: one domain parent | 1 | PD-9 |
| R-5 | attribute `pfx:name : xsd:T [l..u]` | slot, `slot_uri`, `range` by the XSD map, `required` when l ≥ 1, `multivalued` when u is `*` | B | active | 1 | PD-7, PD-8 |
| R-6 | association, destination role and multiplicity | slot on the source, `range` = destination | B | active | 1 | PD-8 |
| R-7 | enumeration | enum; literals → permissible values, `meaning` when prefixed | B | active | 1 | PD-10 |
| R-8 | dependency class → enumeration named by its role | enum-ranged slot | B | active | 1 | PD-8 |
| R-9 | notes on class, attribute, connector | `description` | B | active | 1 | PD-11 |
| R-10 | «root» | `mixins: [AggregateRoot]` + `rp_path` (derived, overridable) | B | active | 1 | PD-12 |
| R-11 | boundary holding a root and classes, or composite association | slots from the root to those classes `owned: true` | B | active | 1 | PD-13 |
| R-12 | stereotype listed as not generated | no class; listed in the report | B | active | 1 | PD-15 |
| R-13 | same slot name and `slot_uri` on several classes | one shared slot, `slot_usage` where range or cardinality differ | B | refined by R-24 | 1 | PD-16 |
| R-14 | generalisation to a toolkit class | toolkit import and mixin (`is_a` for a non-mixin); no new class | C1 | superseded by R-25..R-28 (kept as R-28) | — | — |
| R-15 | attribute or role whose IRI is a toolkit slot's `slot_uri` | that toolkit slot | C1 | amended by R-22 (not `id`) | 2 | PD-18 |
| R-16 | association to a class not generated | `range: uri` | C1 | superseded by R-29 | — | — |
| R-17 | class tagged values `rp_path`, `workflow`, `graph`, `rp_unlabelled`, `database` | class annotations | C1 | superseded by R-20 (DEC-2) | — | — |
| R-18 | «tenant root» | `graph: meta`, no `AggregateRoot` | C1 | active | 2 | PD-19 |
| R-19 | class or slot without a title | `title` = the name split into words | C1 | active | 1 | PD-6 |
| R-20 | class tagged value named like a toolkit class annotation | that annotation, value checked | C2.1, DEC-2 | active | 2 | PD-20 |
| R-21 | tagged value `unique_key = <name>: <a>, <b>[; nulls=equal]` | `unique_keys` entry; `rp_unique_scope`; `consider_nulls_inequal: false` | C2.2, DEC-3 | active | 2 | PD-21 |
| R-22 | attribute `dct:identifier` | new slot `identifier`, `slot_uri: dcterms:identifier`; `id` stays the IRI | C3.1 | active | 2 | PD-18 |
| R-23 | abstract class whose concrete subclasses are all «root» and which is a slot's range | `mixins: [AggregateRoot]`, no `rp_path` | C3.2 | active | 2 | PD-19 |
| R-24 | one slot on classes of several packages | defined once in the module the others import; `slot_usage` elsewhere; else fail | C3.3 | active | 2 | PD-16 |
| R-25 | «root» and labelled parts | default mixins `Described`, `Tracked` (`--default-mixins`); a part tagged `rp_unlabelled=true`: `Described` only (PD-29) | C4.1 | active | 2 | PD-17 |
| R-26 | tagged value `rp_mixins=<C>[,<C>…]` | mixin for a mixin class, `is_a` for a non-mixin (`Activity`); module imported | C4.1 | active | 2 | PD-17 |
| R-27 | tagged value `workflow=<name>` | `UnderWorkflow` mixin (+ the annotation, R-20) | C4.1 | active | 2 | PD-17 |
| R-28 | drawn generalisation to a toolkit class | as R-26; the drawn toolkit class is not generated | C1 kept by C4.1 | active | 2 | PD-17 |
| R-29 | association to a not-generated class / to an excluded package | `range: uri` / no slot, one report line | C4.2 | active | 2 | PD-15 |

Run-level invariants (not mappings, so not rules): I-1 an unmapped element fails the run and
nothing is written (`UmlRule.no_rule`); I-2 a second run is byte-identical; I-3 the report lists
everything left out.

## Decisions

EPIC decisions DEC-1..DEC-6 hold as written in [proposal.md](proposal.md#key-decisions). New
planning decisions:

- **PD-1 Layout.** A subpackage `rdf_persistence_generation/uml/`: `qea.py` (reader), `naming.py`,
  `toolkit.py` (metamodel index, stage 2), `classes.py`, `slots.py`, `convert.py` (orchestration),
  `write.py`, `cli.py`. Command line (the EPIC's line is illustrative; this one is binding):
  `rp-uml2linkml <model.qea> --package <name|path> --prefixes <file> --out <folder>
  [--root-name app] [--exclude-package <path>]… [--default-mixins Described,Tracked]
  [--not-generated <stereotype>]…` (`--not-generated` default: `loaded graph`, PD-15). Console script `rp-uml2linkml = "rdf_persistence_generation.uml.cli:main"`
  in `pyproject.toml` `[project.scripts]`. It needs no `generate` extra (stdlib `sqlite3`, `yaml`,
  `linkml_runtime`); `rdf_persistence_generation.uml` is added to the source modules of the
  contract `works-without-the-generate-extra` (F-12).
- **PD-2 Records are generated models.** The reader's records and the report are LinkML classes in
  `rdf_persistence_generation/model/rp_generation.yaml`, regenerated with `make generate`:
  `UmlModel`, `UmlPackage`, `UmlClass`, `UmlAttribute`, `UmlLink` (association, dependency or
  generalisation: `kind`, source, target, role, card, `whole_end`), `UmlTaggedValue`,
  `UmlBoundary` (id, name, diagram, member class ids), `UmlSettings` (the prefixes file and CLI
  values), `ReportLine` (`kind`: `ReportKind` enum, `element`, `message`); enums `UmlRule`
  (`no_rule` + one value per active rule, its description citing R-n), `UmlLinkKind`,
  `ReportKind`. `UmlRule` has exactly these 24 values (the superseded R-14, R-16, R-17 have none;
  R-15 and R-22 share one, R-25..R-28 share one): R-1 `package_module`, R-2 `class_iri`, R-3 `abstract_class`,
  R-4 `generalisation`, R-5 `attribute_slot`, R-6 `association_slot`, R-7 `enumeration`, R-8
  `dependency_enum_slot`, R-9 `notes_description`, R-10 `root_class`, R-11 `boundary_owned`, R-12
  `not_generated`, R-13 `shared_slot`, R-15/R-22 `toolkit_slot`, R-18 `tenant_root`, R-19 `title`,
  R-20 `class_annotation`, R-21 `unique_key`, R-23 `abstract_root`, R-24
  `shared_slot_across_packages`, R-25..R-28 `toolkit_mixins`, R-29 `left_out_link`; plus `no_rule`
  and `activity_root`. `ReportKind` values: `not-generated`, `excluded-link`, `outside-link`,
  `no-note`, `implicit-meaning`, `toolkit-filled`, `toolkit-slot-kept`, `ignored-tag`,
  `ignored-stereotype`, `merged-cycle`, `stale-file` (in the schema with `_`, which
  `standard_naming` requires; the report prints the `-` form, as written throughout this design).
  A problem is the existing `CheckProblem` with `rule` = a `UmlRule` value, printed
  by `problems.format_problem`. The LinkML output is built as `linkml_runtime` `SchemaDefinition`
  objects, never dicts.
- **PD-3 Reader** (`qea.py`). Opens `file:<path>?mode=ro` with `uri=True`; a file that is not
  SQLite or lacks one of the tables below is a usage error (exit 2). It reads only these columns:

  | Table | Columns |
  |---|---|
  | `t_package` | `Package_ID`, `Name`, `Parent_ID`, `Notes` |
  | `t_object` | `Object_ID`, `Object_Type`, `Name`, `Alias`, `Note`, `Package_ID`, `Stereotype`, `Abstract`, `ea_guid` |
  | `t_attribute` | `ID`, `Object_ID`, `Name`, `Notes`, `Type`, `Classifier`, `LowerBound`, `UpperBound`, `Pos`, `Stereotype` |
  | `t_connector` | `Connector_ID`, `Connector_Type`, `SubType`, `Stereotype`, `Notes`, `Start_Object_ID`, `End_Object_ID`, `SourceRole`, `SourceCard`, `SourceIsAggregate`, `DestRole`, `DestCard`, `DestIsAggregate`, `PDATA1` |
  | `t_objectproperties` | `Object_ID`, `Property`, `Value`, `Notes` (`Value='<memo>'` → the text is in `Notes`) |
  | `t_xref` | `Client`, `Name`, `Description` (only to find a second stereotype: `Name='Stereotypes'`, two or more `Name=<non-empty>;` entries) |
  | `t_diagramobjects` | `Diagram_ID`, `Object_ID`, `RectTop`, `RectLeft`, `RectRight`, `RectBottom` |

  `--package` names the subtree root by name, or by path `A/B` when two packages share a name
  (ambiguous name → exit 2 listing the paths). Converted = every class and enumeration whose
  package is in the subtree and not under an `--exclude-package` path. Ignored object types:
  `Package`, `Note`, `Text`, `Boundary` with a stereotype (reported). Any other object type in the
  subtree (`Activity`, `Component`, `Interface`, `Object`, `DataType`, an n-ary `Association`
  node…) is `no_rule`. An association class (connector `SubType='Class'`, or `PDATA1` naming a
  class) is `no_rule`.
- **PD-4 Boundary membership** (the rabbit-hole, from the evidence above). Members of a boundary
  *b* = the classes and enumerations whose rectangle on a diagram where *b* is placed lies wholly
  inside *b*'s rectangle (edges inclusive, coordinates normalised with `min`/`max`). If *b* is
  placed on several diagrams, the member sets must be equal, else `no_rule` naming *b* and the
  diagrams. A class rectangle that intersects *b* without lying inside it is `no_rule` ("straddles
  boundary"); so is a class placed twice on *b*'s diagram, once inside and once outside. A class
  inside two boundaries is `no_rule`. The boundary's name is not read.
- **PD-5 Modules and files.** One module per subtree package that holds at least one converted
  class or enumeration. Module name = `<root-name>_` + the package path below `--package`, each
  segment lower-cased with every run of non-`[a-z0-9]` replaced by `_` (`rare-books` →
  `rare_books`), nested segments joined by `__` (`MODEL/library/rare-books` →
  `app_library__rare_books`), so a nested path never collides with a single segment holding `_`.
  Classes that sit directly in the `--package` package go to the module `<root-name>_main`; a
  child package named `main` then collides and is a problem naming both. File `<module>.yaml`. Root schema `<root-name>.yaml` (default
  `app`) imports `linkml:types` and every module. Each module imports `linkml:types`, the toolkit
  modules its classes use (F-11 form, sorted) and the domain modules its classes refer to (range,
  `is_a`, enum), sorted. Module `id` = `schema_base` + module name; `title` = the package name split
  into words, sentence case; `description` = the package note, else "The <package> package of the
  <root-name> model, converted from UML." The **prefixes file** (`--prefixes`) is YAML:

  ```yaml
  schema_base: https://example.org/ns/library/   # module ids: <schema_base><module>
  default_prefix: lib
  version: "1"                                   # the root schema's quoted version
  prefixes:
    lib: https://example.org/ns/library#
    dct: http://purl.org/dc/terms/
  ```
  A missing key or a non-mapping is a usage error (exit 2).
- **PD-6 Names, IRIs and titles.** A name `pfx:Local` is expanded with the prefixes file; an
  unknown prefix is a problem (one per prefix, naming the first element). Output CURIEs are
  re-compacted: an IRI namespace the metamodel names (`dcterms`, `prov`, `skos`, `rp`…) takes the
  metamodel's prefix name (so `dct:identifier` → `dcterms:identifier`, F-7), else the file's name.
  An unprefixed name gets no explicit `class_uri`/`slot_uri` (implicit through `default_prefix`).
  Class and enum name = `Local` (must match `[A-Z][a-zA-Z0-9]+`); slot name = `Local` in
  snake case (`hasChapter` → `has_chapter`, `ISBNRecord` → `isbn_record`; must match
  `[a-z][_a-z0-9]+`). Two converted elements with one name and different IRIs, or a domain class
  named like a toolkit class, is a problem naming both. `title` (R-19) = `Alias` when set, else
  the local name split at case changes into words, first word capitalised, the rest lower-cased
  unless all capitals ("ISBNRecordFile" → "ISBN record file").
- **PD-7 XSD map** (R-5): `xsd:string`→`string`, `xsd:normalizedString`→`string`,
  `xsd:anyURI`→`uri`, `xsd:boolean`→`boolean`, `xsd:date`→`date`, `xsd:dateTime`→`datetime`,
  `xsd:time`→`time`, `xsd:integer`/`xsd:int`/`xsd:long`→`integer`,
  `xsd:nonNegativeInteger`→`integer` + `minimum_value: 0`, `xsd:positiveInteger`→`integer` +
  `minimum_value: 1`, `xsd:decimal`→`decimal`, `xsd:double`→`double`, `xsd:float`→`float`. An
  attribute typed by a converted enumeration (`Classifier` = its `Object_ID`, or `Type` = its name)
  ranges over the enum. Any other type, or a class type, is `no_rule` naming attribute and type.
- **PD-8 Multiplicity** (R-5, R-6, R-8). Accepted: `l..u` with l ∈ {0, 1} and u ∈ {1, `*`}, and the
  shorthands `1`, `*` (= `0..*`), `0..1`. `required: true` when l = 1; `multivalued: true` when u
  = `*`. Anything else (`2..5`, `3`) or a missing card on a role or attribute is `no_rule`
  (PD-32). A slot is made at each association end that has a role: `DestRole` → slot on the
  source with `DestCard`; `SourceRole` → slot on the destination with `SourceCard`. An association
  with no role, or a dependency to an enumeration with no `DestRole`, is `no_rule`. `Direction` is
  not read.
- **PD-9 Generalisation** (R-4). One parent among converted domain classes → `is_a`. Two or more
  domain parents → `no_rule` (PD-30). Toolkit parents: stage 2 (PD-17). A parent outside the
  subtree that is not a toolkit class, or in an excluded package → `no_rule`.
- **PD-10 Enumerations** (R-7). Literal → permissible value key = the local name in snake case
  (`ADMIN` → `admin`, `lib:onLoan` → `on_loan`), `title` per PD-6, `description` from its note,
  `meaning` = the expanded literal when prefixed, else `<default_prefix>:<literal as written>` and a
  report line `implicit-meaning` (F-5 requires a meaning). Two literals with one key → problem.
  Order: `Pos`, then name.
- **PD-11 Notes** (R-9). `description` = the note with `\r\n` → `\n` and outer whitespace stripped;
  an empty note writes no description and adds a report line `no-note` (PD-28: no placeholder;
  `rp-generate`'s hard check then names the element, F-5). A role's note is the connector's
  `Notes`.
- **PD-12 Roots** (R-10). «root» → `mixins` starts with `AggregateRoot`; `rp_path` = the
  `rp_path` tagged value if present (stage 2 checks it), else the plural of the class name in
  kebab case: `y` after a consonant → `ies`; `s`, `x`, `z`, `ch`, `sh` → `+es`; else `+s`
  (`Book` → `books`, `Library` → `libraries`, `Box` → `boxes`). Two roots with one `rp_path` →
  problem naming both. The module imports `rdf_persistence/model/rp_core`.
- **PD-13 Ownership** (R-11). A slot from a member *m* of boundary *b* to a member *p* ≠ *b*'s root
  is `owned: true`. A composite association (`SourceIsAggregate=2`: the source is the whole) makes
  the destination role's slot owned. `DestIsAggregate=2` on a destination-role slot (the part points
  at its whole), and any `Aggregation` connector, are `no_rule` (PD-33). Shared aggregation (`=1`)
  is a plain reference. An owned multivalued slot gets `inlined_as_list: true`, an owned single one
  `inlined: true` (F-9). A boundary with no «root» or «tenant root» member, or with two, is
  `no_rule` naming the boundary. Whether every part is reachable is `rp-generate`'s boundary
  check, not the converter's (A-3).
- **PD-14 Import cycles.** The real model has 15 package pairs in a cycle. Stage 1 runs SPIKE-2.
  If generation of a two-module cycle works, modules stay one per package. If it fails, the
  packages of each strongly connected component are written as one module named after the
  component's first package in path order, and a report line `merged-cycle` names the packages
  (PD-27). The verdict is recorded in `## Delivery decisions` before task 2.5 starts.
- **PD-15 Left out** (R-12, R-29). `--not-generated <stereotype>` (repeatable; default the one
  value `loaded graph`) names class stereotypes that produce no class; each such class is a report
  line `not-generated`, and a slot to it is `range: uri`. A slot to a class in an excluded package
  is not made: report line `excluded-link` naming the connector as `<Source>.<role> -> <Target>`.
  A dependency to an excluded enum: the same. A class stereotype other than `root`,
  `tenant root`, the not-generated list or empty is `no_rule` naming class and stereotype
  (PD-31); a connector stereotype likewise; an attribute stereotype other than `enum` on a
  literal is a report line `ignored-stereotype`. A slot to a class outside the subtree (not excluded,
  not toolkit) is `range: uri` with a report line `outside-link`.
- **PD-16 Shared slots** (R-13, R-24). Slots are keyed by name. All usages of one name must share
  one expanded IRI, else a problem naming the name and both IRIs. The slot is defined once, with
  the properties (`range`, `required`, `multivalued`, `description`) of its first usage in order
  (module path, class name, `Pos`/role); every other class whose usage differs in any of these gets
  a `slot_usage` with exactly the differing ones. Home module (R-24) = the one module, among the
  modules using it, that every other using module reaches by imports; when several qualify (a
  cycle), the first in path order; when none, a problem `[shared_slot_across_packages] <slot>: used in
  <m1>, <m2> and no one of them is imported by the others`.
- **PD-17 Toolkit classes and mixins** (R-25..R-28). `toolkit.py` loads `rp.yaml` with
  `rdf_persistence.schema.services.schema.load_schema` and indexes each toolkit class by name and by
  expanded `class_uri`, with its `mixin` flag and its module. A drawn class is a toolkit class when
  its IRI equals a toolkit `class_uri` (`prov:Activity` → `Activity`) or it is in the `rp`
  namespace with a toolkit class's name (`rp:ReferenceCollection`); it is not generated. Mixins of
  a class, in this order, without repeats: `AggregateRoot` (R-10, R-23); the `rp_mixins` names in
  tag order, then drawn toolkit parents in `Connector_ID` order, each a mixin class (a non-mixin
  goes to `is_a`); the `--default-mixins` (default `Described,Tracked`) on «root» classes and on
  owned non-root classes; `UnderWorkflow` when `workflow` is tagged. A part tagged
  `rp_unlabelled=true` gets `Described` only and the annotation (PD-29, F-4). Two `is_a` sources
  (a domain parent and `Activity`, or two non-mixin toolkit classes) → `no_rule`. An unknown name
  in `rp_mixins` or `--default-mixins` → problem listing the toolkit class names. Each used toolkit
  class's module is imported.
- **PD-18 Toolkit slots** (R-15, R-22). An attribute or role whose expanded IRI is a toolkit slot's
  `slot_uri` uses that slot, except `id` (`identifier: true`): `dct:identifier` makes a new slot
  `identifier` (`slot_uri: dcterms:identifier`). When the class does not inherit the slot through a
  toolkit mixin it is added to `slots`; a `slot_usage` carries `required: true` only when the UML
  says l = 1 and the toolkit slot's induced value on the class is not required. A multivalued
  difference, or an XSD type that maps to another range than the toolkit slot's, keeps the
  toolkit's and adds a report line `toolkit-slot-kept`. A **toolkit-filled** slot (F-3) never gets
  a `slot_usage`: the narrowing is dropped and reported as `toolkit-filled` (PD-26).
- **PD-19 Tenant root and abstract roots** (R-18, R-23). «tenant root» → annotation `graph: meta`,
  no `AggregateRoot`, no `rp_path`; a `graph` tag with another value → problem. R-23: an abstract
  class all of whose concrete descendants in the converted model are «root», and which is the range
  of at least one generated slot, gets `AggregateRoot` (no `rp_path`, no default mixins); its
  concrete «root» subclasses still list `AggregateRoot` (PD-17 order).
- **PD-20 Tagged values** (R-20, DEC-2). Class annotations = the `RpAnnotation` values whose
  metamodel description starts "Class annotation" (F-1), read from the metamodel at run time. A tag
  with such a name becomes that annotation. Its value is checked with the hard check's own tables
  (F-2): `checks/hard.py` `ALLOWED_ANNOTATIONS` and `PATTERNED_ANNOTATIONS` (already public) and
  `segment_pattern()` (the one rename: from `_segment_pattern`), so a new annotation such as
  `rp_on_referenced_delete` needs no change here. A failing value → problem
  `[class_annotation] <Class>: rp_writes: 'sometimes' is not one of ('service', 'toolkit')`. A tag
  named like an `RpAnnotation` value that is not a class annotation (`owned`, `module_kind`…) →
  problem "is not a class annotation". `rp_mixins`, `unique_key` → PD-17, PD-21. Any other tag →
  report line `ignored-tag`.
- **PD-21 Unique keys** (R-21, DEC-3). `unique_key` tag value grammar
  `<name> ":" <attr> ("," <attr>)* [";" "nulls=equal"]`, whitespace-tolerant; one key per tag (EA
  allows the tag several times). `<attr>` is a slot name or the attribute's UML name. On a root or
  an R-23 abstract root: `annotations: {rp_unique_scope: tenant}`; elsewhere no scope (F-6).
  `nulls=equal` writes `consider_nulls_inequal: false` (refused by the hard check until
  `unique-key-nulls-equal` lands, DEC-3). A bad grammar, unknown attribute or a non-identifier name
  → problem naming class and tag.
- **PD-22 Output and report** (`write.py`). Problems are collected for the whole model; any problem
  → every problem printed with `format_problem`, sorted, exit 1, nothing written. Otherwise the
  files are dumped with `linkml_runtime.dumpers.yaml_dumper` into a temporary folder beside
  `--out` and moved into place with `os.replace`; the report `<root-name>.uml-report.txt` is one
  `<kind>\t<element>\t<message>` line per item, sorted. A `<root-name>_*.yaml` in `--out` that this
  run did not write is not deleted: report line `stale-file`. Order is fixed everywhere (modules
  by path; classes, slots, enums by name; class `slots` by attribute `Pos`, then roles and
  dependencies by slot name; permissible values per PD-10), so I-2 holds.
- **PD-23 Exit codes**: 0 written; 1 model problems; 2 usage (arguments, unreadable or non-SQLite
  file, missing table, unknown or ambiguous `--package`, bad prefixes file). Same as `rp-generate`.
- **PD-24 Test fixture.** No binary is checked in. `tests/generator/uml_qea.py` (a helper, not a
  test module) builds a `.qea` in `tmp_path` with `sqlite3`: `CREATE TABLE` for the seven tables of
  PD-3 with exactly those columns, and a builder API (`package`, `cls`, `attribute`, `association`,
  `dependency`, `generalisation`, `tag`, `boundary(diagram, rect, members)`). `EA_COLUMNS`, a
  constant in the helper, lists each table's real EA columns (the `pragma table_info` of the probe,
  2026-11-20); a unit test asserts the DDL's columns are a subset, so the fixture cannot invent a
  column. The generic model `library` (prefix `lib:`), golden output under
  `tests/generator/fixtures/uml/golden/`, regenerated only by `make refresh-golden` (its `-k`
  gains `uml_`).
- **PD-25 Docs.** How-to `docs/modules/ROOT/pages/howto/uml-to-linkml.adoc` ("Generate the model
  from UML": command, prefixes file, rule table as a user reference, report kinds, then
  `rp-generate`), its line in `nav.adoc` and its question in `questions.adoc`; a row in the
  front-end list of `architecture/generation.adoc`; the `rp-generation` MODIFIED delta that the
  proposal lists but the change lacks (`specs/rp-generation/spec.md`, one requirement: "LinkML may
  be generated from a UML class model").

### SPIKE-1: may an application root be `is_a: Activity`? (DEC-4)

Read so far (code, no run):

| Concern | Finding | Source |
|---|---|---|
| Boundary check | Passes: `_direction_problems` leaves roots out of the use cases; `_may_be_referred_to` accepts it; TC-102 `activity-root` covers it | `checks/boundary.py:51-124` |
| Hard check | Passes for `mixins [AggregateRoot, Described, Tracked]` + `rp_path`. **Fails** once a `slot_usage` narrows `started_at_time` (F-3): the issue's example `slot_usage: {started_at_time: {required: true}}` cannot be written | `checks/toolkit_filled.py:14` |
| Commit recording | The commit's activity is a separate `Add`/`Replace`/`Remove` with a fresh `urn:uuid:` id, recorded in the provenance graph only (`_RECORDED`, `ID_TAKEN` are `GRAPH $provenance`); the root keeps its policy IRI in its own graph. No query reads `?x a prov:Activity` across graphs | `persistence/services/session.py:145-146, 1466-1560`; `provenance/services/provenance.py` |
| Toolkit-filled at write | Only the message bus refuses a filled `started_at_time` (`_refuse_filled`, commands only); `session.add` and the generic routes do not | `messaging/services/messagebus.py:96` |
| Event stream | Carries the commit's `Add`, never the stored root | `events/services/relay.py`, `api/entrypoints/sse.py:42` |
| Frames | `framed_classes` lists the root once (roots first, then Activity descendants not yet named) | `extensions/jsonld_context.py:149` |

The spike adds `Review` (the TC-102 class: `is_a: Activity`, `mixins: [AggregateRoot,
Described, Tracked]`, `rp_path: reviews`) to `tests/fixtures/library/books_activities.yaml`,
runs `make generate`, and tests:

| Id | Assertion | Test |
|---|---|---|
| S-1 | `rp-generate` generates the toy with `Review` (all steps) | `make generate` exit 0 |
| S-2 | a `Review` with a `slot_usage` on `started_at_time` gets a `toolkit_filled` problem | `tests/generator/unit/test_hard_check.py`, new row |
| S-3 | `session.add(Review(…, started_at_time=t))`, commit: the provenance graph holds one new activity, typed `rp:Add`, `urn:uuid:` id ≠ the review's id, one generation with `entity` = the review IRI and `entity_class` = `lib:Review` | `tests/unit/services/test_activity_root.py` |
| S-4 | reading the review back gives an equal model, `started_at_time` = t | same file |
| S-5 | the event hub offers exactly one activity for the commit, an `Add` | same file |
| S-6 | `POST /reviews` with `started_at_time` → 201; `GET` returns it | `tests/unit/entrypoints/test_activity_root_routes.py` |

**Pass** = S-1..S-6 green with no change under `rdf_persistence/`. Then the converter allows
`Activity` as `is_a` of a root (PD-17), and never narrows a toolkit-filled slot (PD-18). **Fail** =
any of S-1, S-3..S-6 red: the converter refuses `rp_mixins=Activity` and a drawn generalisation to
`prov:Activity` on a «root» with `[activity_root] <Class>: an aggregate root may not be an Activity
(DEC-4 spike: <first failing S-id>)`, the tests stay as the record, and the toy change is reverted.
The verdict goes to `evidence/spike-dec4.md` and `## Delivery decisions`. Timebox: one task (1.7).
Lane after merge: the unit lane (`make test-unit-ci`), and S-2 the generator lane.

### SPIKE-2: do cyclic module imports generate? (PD-14)

Two converted packages whose classes point at each other (`lib:Book.shelf → Shelf`,
`lib:Shelf.featured → Book`, packages `books` and `shelves`) → converter → `rp-generate` (write
mode) into a `tmp_path` project → `import` the generated package and build one `Book`. Pass =
exit 0 and the import works. Test: `tests/generator/integration/test_uml_cycle.py` (generator lane,
it needs the `generate` extra and writes Python). The verdict sets PD-14.

## Algorithm / approach

`main(argv)` → parse → read settings (PD-5) → `read_qea(path, package, excluded)` → `UmlModel`
(PD-3, PD-4) → `convert(model, settings, toolkit)` → `(schemas, report)` or problems → `write`
(PD-22). `convert` is pure: no I/O but the metamodel load, done once by the CLI. Passes, in order:
(1) resolve names and IRIs of every element (PD-6) — problems collected; (2) classify classes:
generated, toolkit, not-generated, excluded, outside; (3) classes (PD-9, PD-12, PD-17, PD-19,
PD-20, PD-21); (4) slots from attributes, roles, dependencies (PD-7, PD-8, PD-13, PD-15, PD-18);
(5) share slots and choose homes (PD-16: the reachability it uses comes from the classes'
references, a shared slot counting for every module that uses it); (6) imports and modules
(PD-5, PD-14), recomputed after (5) so a home module also imports the module of its slot's range,
and the cycle components taken from these final imports; (7) if any
problem, stop. Idempotency: the run has no state but its output; the same input gives the same
bytes (I-2), so re-running after a crash is safe.

Worked example (stage 2, the fixture). Package `MODEL/library`, prefixes file as PD-5:
«root» `lib:Book` (note "A book held by the library.", tags `rp_mixins=StoredFile`,
`unique_key = title_subtitle: title, subtitle`), attributes `dct:title : xsd:string [1..1]`,
`lib:subtitle : xsd:string [0..1]`, `dct:identifier : xsd:string [1..1]`; association
`lib:hasChapter 1..*` → `lib:Chapter` (tag `rp_unlabelled=true`); both inside one boundary;
`lib:shelvedOn 0..1` → «root» `lib:Shelf`. Output `models/app_library.yaml` (excerpt):

```yaml
imports: [linkml:types, rdf_persistence/model/rp_annotations, rdf_persistence/model/rp_core,
          rdf_persistence/model/rp_files]
classes:
  Book:
    title: Book
    description: A book held by the library.
    class_uri: lib:Book
    mixins: [AggregateRoot, StoredFile, Described, Tracked]
    slots: [title, subtitle, identifier, has_chapter, shelved_on]
    unique_keys:
      title_subtitle:
        unique_key_slots: [title, subtitle]
        annotations: {rp_unique_scope: tenant}
    annotations: {rp_path: books}
  Chapter:
    class_uri: lib:Chapter
    mixins: [Described]
    annotations: {rp_unlabelled: 'true'}
slots:
  has_chapter: {slot_uri: lib:hasChapter, range: Chapter, required: true, multivalued: true,
                inlined_as_list: true, annotations: {owned: 'true'}}
  identifier: {slot_uri: dcterms:identifier, range: string, required: true}
  shelved_on: {slot_uri: lib:shelvedOn, range: Shelf}
```

`title` reuses no toolkit slot (the toolkit's `label` is `skos:prefLabel`), so it is a new slot
`title` with `slot_uri: dcterms:title`. A «root» `lib:Loan` tagged `rp_mixins=Activity` with
`prov:startedAtTime : xsd:dateTime [1..1]` → `Loan: {is_a: Activity, mixins: [AggregateRoot,
Described, Tracked], annotations: {rp_path: loans}}`, imports `rp_provenance`, no new slot, no
`slot_usage`, report line `toolkit-filled	Loan.started_at_time	the toolkit fills
started_at_time; [1..1] is not carried` (PD-26, if SPIKE-1 passes).

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| A-1 Keep a list of tagged values or annotation values in the converter | Read the class annotations from `RpAnnotation` (F-1) and check values with `hard.ALLOWED_ANNOTATIONS` (F-2) | DEC-2: a new annotation must need no change here |
| A-2 Infer boundary members from the boundary's name or the package | Geometry on the boundary's diagram (PD-4) | The name is a convention the probe saw broken in 3 of 27 |
| A-3 Re-check ownership, roots' paths or the toolkit-filled rule inside the converter | Leave them to `rp-generate`; test that its steps pass on the golden output | Two copies of a rule drift |
| A-4 Build the LinkML as dicts or write YAML by string templates | `SchemaDefinition` objects and `yaml_dumper` (PD-2) | Models, not dicts; typos in metaslots go unnoticed |
| A-5 Iterate SQLite rows or Python sets in their natural order when writing | Sort as PD-22 says | I-2: SQLite row order is not guaranteed |
| A-6 Open the `.qea` read-write, or with `sqlite3.connect(path)` | `file:<path>?mode=ro`, `uri=True` | EA files are the modellers' source; a write corrupts it |
| A-7 Check a binary `.qea` into the tests | Build it with `tests/generator/uml_qea.py` (PD-24) | Reviewable, no consumer data |
| A-8 Write a `slot_usage` on a toolkit-filled slot | Drop it and report it (PD-18) | F-3: `rp-generate` refuses it |
| A-9 Stop at the first problem | Collect all, print sorted, write nothing (PD-22) | A modeller fixes the EA model in one round |
| A-10 Consumer names in fixtures, tests, docs | `lib:` library model | `make check-docs`; no-go |

### Test specifications

Tiers (testing.adoc "Two pyramids"): the generator pyramid `tests/generator/`, except S-3..S-6
(library pyramid). Each converter rule test is a row of one parametrised table in
`tests/generator/unit/test_uml_rules.py`, plus `test_every_uml_rule_has_a_row` (testing rule 6).

| Id | Tier, file | Input | Expected | Edge cases |
|---|---|---|---|---|
| TC-1 | unit, `test_uml_qea.py` | fixture with nested packages, `--package MODEL/library` | `UmlModel` with the subtree's classes only | ambiguous name → exit 2 listing paths; missing table → exit 2; a text file → exit 2 |
| TC-2 | unit, `test_uml_qea.py` | boundary rect (-20,30,320,-298) and members inside, on the edge, straddling, outside | members = inside + edge; straddle → `no_rule`; outside not a member | positive y orientation; boundary on 2 diagrams equal / unequal; class in two boundaries |
| TC-3 | unit, `test_uml_qea.py` | tag `Value='<memo>'`, `Notes='books'` | tag value `books` | two stereotypes in `t_xref` → `no_rule` |
| TC-4 | unit, `test_uml_naming.py` | `hasChapter`, `ISBNRecord`, `ADMIN`, `Book`, `Library`, `Box`, `ISBNRecordFile` | `has_chapter`, `isbn_record`, `admin`, rp_path `books`, `libraries`, `boxes`; title "ISBN record file" | one-letter slot `x` → problem (F-7) |
| TC-5 | unit, `test_uml_rules.py` | one row per rule R-1..R-29 active | the LinkML fragment of the rule's column | each rule's failure branch as its own row |
| TC-6 | unit, `test_uml_rules.py` | `dct:identifier` attribute; `prov:startedAtTime [1..1]` on an Activity root | `identifier` slot; no `slot_usage`, `toolkit-filled` report line | `skos:prefLabel [0..1]` on a Described class → `slot_usage` none |
| TC-7 | unit, `test_uml_rules.py` | `rp_writes=sometimes`; `owned=true` as class tag; `junctionKind=x` | problems with the PD-20 messages; `ignored-tag` line | `rp_path=Books` (pattern) → problem |
| TC-8 | unit, `test_uml_rules.py` | `unique_key = k: title, subtitle; nulls=equal` on a root; same on a part | scope tenant + `consider_nulls_inequal: false`; part: no scope | `k title` (no colon), unknown attr, name `1k` → problems |
| TC-9 | unit, `test_uml_rules.py` | `lib:hasParent` in `catalogue` and `shelves`, `shelves` imports `catalogue` | slot in `app_catalogue` only, `slot_usage` in `app_shelves` if different | neither imports the other → `shared_slot_across_packages` problem; same name, other IRI → problem |
| TC-10 | unit, `test_uml_cli.py` | a model with 3 faults | exit 1, 3 sorted lines on stderr, `--out` unchanged (file set and bytes) | exit 2 for a bad prefixes file; `stale-file` line |
| TC-11 | unit, `test_uml_golden.py` | the fixture `library` | output = golden (exact text, exact file set); second run byte-identical | report file compared too |
| TC-12 | unit, `test_uml_qea.py` | `EA_COLUMNS` vs the helper's DDL | subset | — |
| IT-1 | integration, `test_uml_generate.py` | golden output in a `tmp_path` project with a `[tool.rp-generate]` target | stage 1: `generate(…, (LINT_STEP, BOUNDARY_STEP), check=True)` → `[]`; stage 2: lint, boundary, hard, rules → `[]` | — |
| IT-2 | integration, `test_uml_cycle.py` | SPIKE-2 | as SPIKE-2 | — |
| IT-3 | feature, `uml_import.feature` + `test_uml_import.py` | the spec delta's 7 scenarios | as the spec | — |
| IT-4 | unit (library), S-3..S-6 | SPIKE-1 | as SPIKE-1 | — |

## Error matrix

The converter has no external service; its "services" are the file, the prefixes file and the
metamodel. Every model problem is printed `[<rule>] <element>: <message>` by `format_problem`
(exit 1); a usage error is one line `rp-uml2linkml: <message>` on stderr (exit 2).

| Failure mode | Detected by | Handling (exact text) | Exit |
|---|---|---|---|
| `.qea` missing, unreadable, not SQLite (an `.eap` Jet file) | `sqlite3.DatabaseError` on the first query | `rp-uml2linkml: <path> is not an Enterprise Architect .qea (SQLite) file` | 2 |
| A PD-3 table or column missing (another EA version, a foreign file) | `sqlite_master` lookup; `pragma table_info` per table before the first select | `rp-uml2linkml: <path> has no table <t>` / `rp-uml2linkml: <path>: table <t> has no column <c>` | 2 |
| `--package` unknown / ambiguous | `t_package` lookup | `no package <p>` / `package <p> is ambiguous: <path1>, <path2>; name it by path` | 2 |
| Prefixes file missing key or not a mapping | load | `<file>: missing <key>` / `<file>: not a mapping` | 2 |
| Unknown CURIE prefix | PD-6 | `[class_iri] <element>: prefix <pfx> is not in <file>` | 1 |
| Unmapped element (association class, n-ary node, `Interface`, unknown stereotype, `2..5`, missing card, roleless association, two domain parents, `Aggregation` connector) | PD-3, PD-8, PD-9, PD-13, PD-15 | `[no_rule] <element>: <what it is>: no rule converts it` | 1 |
| Boundary ambiguity (straddle, placed twice, two boundaries, unequal diagrams, 0 or 2 roots) | PD-4, PD-13 | `[no_rule] <boundary or class>: <reason>: no rule converts it` | 1 |
| Name clash (two IRIs one name; domain class named like a toolkit class) | PD-6, PD-16 | `[class_iri] <name>: <iri1> and <iri2> both map to <name>` | 1 |
| Bad tagged value / unique key | PD-20, PD-21 | messages of PD-20, PD-21 | 1 |
| Activity root while SPIKE-1 failed | PD-17 | `[activity_root] <Class>: an aggregate root may not be an Activity (DEC-4 spike: S-n)` | 1 |
| Shared slot without home | PD-16 | `[shared_slot_across_packages] …` (PD-16) | 1 |
| Disk error while moving files into `--out` | `OSError` from `os.replace` | traceback (a bug or a full disk); files already moved stay; a re-run rewrites all (I-2) | 1 |
| `--out` holds a hand-written `<root>_x.yaml` | PD-22 | not deleted, `stale-file` line | 0 |
| Output fails `rp-generate` on the consumer's model (missing notes, an unowned class) | the consumer's `rp-generate` | the how-to says to run `rp-generate --check` next; not the converter's check (A-3) | — |
| `checks.hard` pulls `linkml` into the `uml` package | `make check-architecture` (contract F-12) | move the three tables to `checks/annotation_values.py`, imported by both | — |
| The run is repeated after a crash | — | safe: stateless, same bytes (I-2) | — |

## Risks / Trade-offs

Found by attacking the PLAN against the real file's evidence (step 7); each has its row above or a
PD.

- **RISK-1** (high likelihood, high impact): cyclic package imports (15 pairs in the real model)
  break split pydantic generation. Mitigation: SPIKE-2 in stage 1, PD-14 fallback (PD-27).
- **RISK-2** (high, medium): the real model lacks notes on about a quarter of its classes and on
  most enumeration literals, so `rp-generate` fails on the first real run (F-5). Accepted: the
  report's `no-note` lines list them for the modeller (PD-28); the acceptance demo shows the count.
- **RISK-3** (medium, medium): drawn foreign classes used only as parents (`skos:`, `sh:`) become
  concrete classes that no root owns, which the boundary check refuses. Accepted as a modelling
  fix (mark them abstract in EA); the acceptance demo names them.
- **RISK-4** (low, medium): another EA version names a column differently. Mitigation: PD-3 checks
  every column first and exits 2 naming it; `EA_COLUMNS` records the version seen.
- **RISK-5** (low, low): a `linkml-runtime` upgrade changes `yaml_dumper`'s layout. Detected by
  TC-11's golden; `make refresh-golden` and a review of the diff.
- **RISK-6** (medium, medium): rules arrive until stage 2 starts (DEC-5). Mitigation: R-30… are
  appended to the rule table with source and stage; one that does not fit MEDIUM goes to a follow-up
  issue; task 2.1 writes the freeze date.
- **RISK-7** (medium, low): adding `Review` to the toy (SPIKE-1) shifts the toy's goldens, the
  model-shape snapshot and the scenario map. Mitigation: task 1.7 runs `make generate`,
  `make refresh-snapshot`, `make refresh-served-golden` and `make refresh-map` and reviews their
  diffs; the TC-102 `activity-root` row of `test_boundary_check.py` keeps only its
  `book_slot_over` edit (the class now exists) and still runs in the generator lane.
- **RISK-8** (low, high): composite orientation in EA (`*IsAggregate`, `Aggregation`) is unverified,
  as the real model has none. Mitigation: only `SourceIsAggregate=2` is read; the rest fails
  (PD-33).
- **Trade-off:** geometry makes a boundary's meaning depend on a diagram's layout; moving a class
  out of a box on the diagram changes ownership. Accepted: it is how the modellers draw aggregates,
  and PD-4 fails on every ambiguous placement instead of guessing.

## Owner decisions (2026-11-20, round 2)

The owner accepted every planner recommendation ([inputs/qa.md](inputs/qa.md#round-2-2026-11-20)).
Each is a decision of this PLAN:

- **PD-26 Toolkit-filled narrowing.** The converter never narrows a toolkit-filled slot (F-3): it
  drops the `required` and reports it (`toolkit-filled`, PD-18). The spec delta's scenario "a root
  that is an activity" says so (edited 2026-11-20).
- **PD-27 Cycles.** If SPIKE-2 fails, the packages of each import cycle are written as one module
  (PD-14); the run does not fail on a cycle.
- **PD-28 Missing notes.** No placeholder description; a `no-note` report line per element
  (PD-11); `rp-generate` then names it.
- **PD-29 Unlabelled parts.** A part tagged `rp_unlabelled=true` gets `Described` only (its label
  optional through the toolkit's defaults, F-4) and no `Tracked`; this is how C4.1's "gets neither
  label slot" is read.
- **PD-30 One domain parent.** Two or more generalisations to domain classes fail (`no_rule`);
  R-4's "mixins (others)" applies to toolkit mixins only.
- **PD-31 Unknown stereotypes fail** (PD-15). A consumer passes such a stereotype with
  `--not-generated`, or brings a rule before the DEC-5 freeze.
- **PD-32 Missing multiplicity fails** (PD-8), rather than taking UML's default `1`.
- **PD-33 Composites.** Only `SourceIsAggregate=2` is read (PD-13) until an EA sample with a
  composition drawn is supplied; it then becomes a follow-up.
- **PD-34 `Review` stays in the toy** as the permanent guard of DEC-4 (SPIKE-1, RISK-7).

## Delivery decisions

(Filled during delivery: SPIKE-1 and SPIKE-2 verdicts, the DEC-5 freeze date, accepted review
findings.)

- **D-1 Review set** (2026-11-20). Rule P-0005 holds over the MEDIUM default of the workflow file:
  each stage gets one L2+L3 pass (task 1.9); the full review (L1, L2, L3 apart, L4+L5 as one) runs
  once, in task 2.8. No adversarial tester: the PLAN has no `## Invariants` section and the
  appetite is below LARGE.
- **D-2 SPIKE-2 first** (2026-11-20, the developer: "stage 1 starts with the two spikes"). SPIKE-2
  asks whether `rp-generate` generates two domain modules that import each other; it does not need
  the converter. It runs now on two hand-written LinkML modules (`books` ↔ `shelves`, the
  SPIKE-2 classes) in a `tmp_path` project, as
  `tests/generator/integration/test_module_import_cycle.py`, kept as the guard of PD-14. The
  converter round trip stays IT-2 in task 1.8. The verdict now sets PD-14 before task 1.5, which
  lays out the modules (R-1), instead of before 2.5.
- **D-3 Order** (2026-11-20, rule R-0004). SPIKE-1 (1.7) and SPIKE-2 run first, in parallel
  (disjoint files; SPIKE-2 writes only into `tmp_path`). Task 1.1 runs beside them in its own
  builder worktree (`.worktrees/uml-to-linkml-1.1`), because 1.1 and 1.7 both run `make generate`;
  their generated files are disjoint (the generator's records vs the toy), and the lead re-runs
  `make check-generated` after joining them. Then 1.2 ∥ 1.4, then 1.3, as the roadmap.
- **D-4 Test folders** (2026-11-20). `tests/unit/` is organised by feature, not by layer: S-3..S-5
  and S-6 go into the feature folders that hold the provenance and route tests, not the
  `tests/unit/services/` and `tests/unit/entrypoints/` the PLAN names. `evidence/spike-dec4.md`
  names the paths.
- **D-5 SPIKE-2 verdict: fail; PD-14 takes its second branch** (2026-11-20,
  [evidence/spike-cycles.md](evidence/spike-cycles.md)). `rp-generate` accepts two domain modules
  that import each other (exit 0), but the split pydantic modules (F-10) import each other at module
  level and the package fails with a circular `ImportError`. So, per PD-27, the packages of each
  import cycle are written as one module named after its first package in path order, with a
  `merged-cycle` report line; task 1.5 builds the module layout this way. The cycle test stays as
  `xfail(strict=True, raises=ImportError)`: it fails loudly the day the generator learns cycles,
  and then PD-14's first branch can replace PD-27. The generator gap is ours: issue #208.
- **D-6 Records as built** (2026-11-20, task 1.1; amends PD-2). Slots are global in
  `rp_generation.yaml` and `kind`, `package`, `classes`, `links`, `stereotype` are taken, so:
  `UmlLink.link_kind`, `ReportLine.report_kind`, the model's lists `uml_packages`, `uml_classes`,
  `uml_links`, `uml_tagged_values`, `uml_boundaries`, attributes under `UmlClass.uml_attributes`.
  `UmlLink` carries both ends (`source_role`/`_card`/`_aggregate`, `target_…`) and the raw EA
  aggregation flags instead of `whole_end`: the reader copies columns, the converter derives the
  whole end (PD-13). A new class `UmlPrefix` (`prefix_name`, `namespace`) keeps
  `UmlSettings.prefixes` a list of models, not a dict (P-0007). `UmlSettings` holds the prefixes
  file's keys and the CLI values, not the `.qea` path or `--out` (I/O).
- **D-7 SPIKE-1 verdict: pass** (2026-11-20, [evidence/spike-dec4.md](evidence/spike-dec4.md)).
  S-1..S-6 green with no file under `rdf_persistence/` changed: an application root may be
  `is_a: Activity` (DEC-4). PD-17 allows `Activity` as the `is_a` of a root; the `activity_root`
  refusal of task 2.3 stays inactive. PD-18 and PD-26 stand: the hard check refuses a narrowed
  `started_at_time` on `Review` (S-2). `Review` stays in the toy (PD-34). Adding it shifted four
  toy-enumeration tests (`test_openapi`, `test_documents`, `test_allowed_actions_adversarial`,
  `test_ext_jsonld_context`), each given its `Review` row (RISK-7). The scenario-map rows of the
  seven spike tests are added in task 1.9.
- **D-8 Naming as built** (2026-11-20, task 1.4; amends PD-6 and D-6). `resolve_name` returns the
  generated `UmlName` (`name`, `iri`, `curie`), since the model guard refuses a hand-written result
  type. It takes the prefixes as a `Mapping[str, str]` index built from the `UmlPrefix` records
  (P-0007 allows a dict as an index). A name that breaks F-7 is a problem with rule `class_iri`
  for classes and enums and `attribute_slot` for slots and permissible values; task 1.5 dedupes
  unknown-prefix problems to one per prefix. The 1.1 record slot `alias` is renamed `uml_alias`:
  `alias` is a slot of the records moved out of the generation schema, which
  `test_technical_split` guards. Every new `.py` under `rdf_persistence_generation/` changes the 25
  `rp-manifest.json` files (they hash the generator's sources); the lead commits them, regenerated
  with `make generate`, with the task. Gate: `make test-changed` against a detached builder worktree
  ran fewer tests than `make test-fast` and missed the `alias` clash, so builders in a builder
  worktree run `make test-fast check-quality`.

Alignment with the model2owl UML conventions and the SEMIC style (developer, 2026-11-20, round 3;
the conventions read at https://docs.ted.europa.eu/M2O/latest/uml/conceptual-model-conventions.html
and its checkers page):

- **D-9 Why model2owl is not run first.** `linkml-engineering` derives LinkML from UML through
  model2owl. Not here: model2owl reads an XMI export, not the `.qea` (DEC-1); its documentation
  states no LinkML output; and it knows nothing of the toolkit's roots, boundaries, mixins and
  annotations, which are most of the rule table. The converter follows model2owl's UML conventions
  instead, as D-10..D-14 align them.
- **D-10 Empty enumerations** (amends PD-10, R-7, R-8). An enumeration with no literals is a
  controlled list kept outside the model (model2owl `rule:gen-controlled-list-empty`, a SKOS concept
  scheme): an attribute or dependency ranging over it becomes `range: uri`, with a report line
  `external-list` naming the enumeration. An enumeration with literals stays an enum (R-7). The
  `permissive`/`restrictive` tag on an enumeration is an `ignored-tag` line.
- **D-11 Multiplicity** (amends PD-8; supersedes PD-32). Any `l..u` with integers `0 ≤ l ≤ u`, or
  `u = *`, and the shorthands `n` (= `n..n`) and `*` (= `0..*`): `required: true` when l ≥ 1;
  `multivalued: true` when u > 1 or `*`; `minimum_cardinality: l` when l > 1;
  `maximum_cardinality: u` when 1 < u < `*`. A missing multiplicity is `0..*` (model2owl
  `rule:attributes-multiplicity`) with a report line `unspecified-multiplicity`; "exactly one" is
  written `1..1`. In a `.qea` only a connector's card can be missing (`NULL` or empty: 91 of the
  real file's association ends); EA stores an attribute's blank multiplicity as `1`/`1`, the same
  as an explicit `1..1` (38 of 68 attributes in the real file), so an attribute's bounds are taken
  as stored. A malformed card (`2..1`, `a..b`) is `no_rule`.
- **D-12 Language strings** (amends PD-7). `rdf:langString` (and `rdf:PlainLiteral`) are never
  dropped or narrowed to `string`. The toolkit has no language-string range yet (and
  `api/services/documents.py` strips `@language` from value objects), and this EPIC changes no
  library code, so until the toolkit change lands such an attribute is `no_rule`:
  `[no_rule] <Class>.<attribute>: rdf:langString has no toolkit range yet (#209): no
  rule converts it` (the toolkit change: issue #209). When the toolkit's range lands, PD-7 maps to it with no other change. The
  real model has no such attribute.
- **D-13 Abstract stereotype** (amends PD-15, R-3). A class stereotyped `Abstract` (any case) is
  `abstract: true`, as is EA's `Abstract` flag; the stereotype is not reported.
- **D-14 Direction and implicit identity** (amends PD-3, PD-6, PD-8). The reader also reads
  `t_connector.Direction`: an association is accepted `Source -> Destination` (target role) or
  `Bi-Directional` (both roles); any other direction is `no_rule` (model2owl
  `connector-direction-21/24`). A class or enum whose expanded IRI is `<default_prefix>:<its LinkML
  name>` gets no explicit `class_uri` (the implicit URI is the same, `modelling-conventions` rule
  2); slots keep `slot_uri`, as their snake-case name differs from the IRI's local name.
- **D-15 Parallel build of 1.3, 1.5 and 1.6** (2026-11-20, the developer: "continue in parallel").
  The reader (1.3), the converter (1.5) and the writer half of 1.6 run at once, each in its own
  builder worktree, against the records of 1.1 and this interface:
  `convert(model, settings, metamodel_prefixes) -> (schemas, report_lines, problems)`, pure, each
  schema named after its module; `write(schemas, report_lines, out, root_name) -> added report
  lines`, writing `<schema.name>.yaml`. The converter's tests build `UmlModel` records directly; the
  reader-to-output path is tested by 1.6's golden and IT-1, which the lead runs after the three
  join (CLI, console script, golden). Both 1.3 (`UmlLink.direction`) and 1.5 (two `ReportKind`
  values) change `rp_generation.yaml`: the lead joins them, takes one generated side and runs
  `make generate` (P-0003). The D-14 direction check is added to 1.5 after 1.3 joins. In stage 1 a
  slot shared across modules is refused, naming stage 2 (task 2.6, R-24).
- **D-16 Authority** (2026-11-20, the developer: "dont wait on me, feel free to merge admin too").
  For this EPIC the lead commits, pushes, opens and merges each stage PR into `develop` without
  waiting for the developer, with `gh pr merge --merge --admin` where a required review would
  otherwise block. Limits kept (`epic-delivery`, Authority): merge only once the PR lists check runs
  and all are green; nothing destructive beyond the normal git flow; the grant ends with the EPIC.
  The DEC-5 question before stage 2 is still asked.
- **D-17 Reader as built** (2026-11-20, task 1.3; amends PD-3, PD-4, PD-13). `read_qea` returns
  the `UmlModel` or every `no_rule` problem, sorted; usage errors are a typed `QeaUsageError`
  whose text the CLI prefixes with `rp-uml2linkml: `. A stereotyped `Boundary` is ignored without
  a report line (the reader has no report channel; PD-3's "(reported)" is dropped). A connector
  of a type the reader does not know (`Aggregation`, `Abstraction`, `ControlFlow`…) touching a
  converted class is `no_rule` in the reader, as `UmlLinkKind` has no value for it; connectors to
  `Note`, `Text`, `Boundary` or `Package` objects are skipped. A non-empty `PDATA1` other than `0`
  on an association names an association class (no association in the real file carries one).
  Boundaries count only when they hold a converted class, and their straddle checks look at
  converted classes only. Tags keep file order within a name (for `rp_mixins`, `unique_key`). Two
  amendments for task 1.6: an `--exclude-package` that matches no package of the subtree is a usage
  error (`no package <p> under <root>`), not silently ignored; and the reader puts the classes at
  the far end of a link that are not converted (outside the subtree, excluded) in a new
  `UmlModel.uml_outside_classes` (no attributes), so the converter can name them in report lines
  (PD-15) and stage 2 can recognise drawn toolkit classes (PD-17).
