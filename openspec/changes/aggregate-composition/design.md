<!-- PLAN (design half) of aggregate-composition. PLAN = this file + tasks.md. -->

# Design: aggregate-composition

> Derives from: EPIC `aggregate-composition` (`proposal.md`, issues #437, #435, three items of
> #343), DEC-1 to DEC-13, DEC-4 as re-shaped on 2026-11-28 (`inputs/qa.md` "Re-shape").
> Q&A: `inputs/qa.md` (Q1–Q11). Follow-up: `dependent-aggregates` (lifts DEC-7's refusal).
> Attack: `evidence/attack.md`, A-1..A-26, each folded in (its "Resolved in" column).
> Codebase read on 2026-11-28 in this worktree; file and line references are to that state.

## Context

`rp-uml2linkml` learns ownership in two places: `links.py` `_is_owned` (an association end with
`SourceIsAggregate = 2`, a composite association) and `owned_pairs` / `_boundary_pairs` (every
member-to-non-root pair of a boundary, membership from `qea.py` `_Boundaries`, rectangle geometry).
Roots come from the «root» stereotype (`classes.py` `_register`, `is_root`); `_check_root_paths`
runs inside `collect_elements`, before any link is read. `qea.py` `LINK_KINDS` maps Association,
Dependency and Generalization; every other connector type touching a converted class is a
`no_rule` problem at read time (`_Reading._link`), Aggregation and Realisation included. The
reader reads `t_diagram` and `t_diagramobjects` (geometry included) but not `t_diagramlinks`.
`cli.py` always writes; it has no check mode. Findings are `CheckProblem` (fails the run) or
`ReportLine` (`ReportKind`, written to `<root>.uml-report.txt`); both are generated records of
`rp_generation.yaml`.

Today a concrete class that is neither «root» nor owned gets neither `AggregateRoot` nor the
default mixins (`mixins.py` `_defaults`): a "plain" class the library cannot store. Many unit rows
of `tests/generator/unit/test_uml_rules.py` draw such classes (`root=None`), which matters for
RISK-5.

## Goals / Non-Goals

**Goals**
- G-1: compositions (EA Aggregation, strong) beside their associations make owned, inlined slots
  at any depth; the composite association and boundary geometry no longer do (DEC-2, DEC-3).
- G-2: roots are derived and reported; a «root» drawing that disagrees fails; one that agrees
  converts to byte-identical schemas (DEC-5, DEC-6).
- G-3: «own graph» to a not-generated part converts; to a generated part fails naming
  `dependent-aggregates` (DEC-7). Pointers into another aggregate's part fail (DEC-8).
- G-4: a Realisation from an Object to its classifier is accepted (DEC-9, #435).
- G-5: `rp-uml2linkml --check` reports every problem and convention line, writes nothing, exits 1
  on any (DEC-10); the generic part of C-1..C-12 and DEC-11 are findings.
- G-6: the guide, the conventions page and the rulebook carry the terms, the deletion test, the
  diagram kinds, the conventions and the adopted rules (DEC-12).

**Non-Goals**: the EPIC's no-gos. No change to `rdf_persistence/` behaviour (PD-9 adds one
metamodel enum value, read by no library code). No geometry. No plug-in API for consumer checks.

## Decisions

Each decision has an anchor (`design.md#pd-1`, `#d-5`, `#risk-9`); tasks link them.

- <a id="pd-1"></a>**PD-1** (DEC-2, RISK-1, [D-4](#d-4), [D-5](#d-5)): the reader normalises a
  composition once. An Aggregation connector becomes a generated `UmlComposition` record
  (`composition_id`, `whole_id`, `part_id`, `own_graph: bool`, `uml_stereotype`, `role`) in a new
  `UmlModel.uml_compositions`, not a `UmlLink`. The end columns alone decide (D-5): `2` in
  exactly one of `SourceIsAggregate`/`DestIsAggregate` is a composition whose whole is that end;
  `1` in either is a shared aggregation (a problem, DEC-2); `2` in both, or `0` in both, is a
  problem naming the connector; any other value is `no_rule`. `SubType` is not read (EA leaves it
  empty on the rows observed). `Start`/`End` order is never read after that. One function
  (`_composition`) holds this; every later pass reads `whole_id`/`part_id`. `QeaBuilder.aggregation`
  writes, for whole W and part P: drawn whole → part `Connector_Type='Aggregation'`, `SubType`
  NULL, `Start=W`, `End=P`, `SourceIsAggregate=2`, `DestIsAggregate=0`; drawn part → whole
  `Start=P`, `End=W`, `SourceIsAggregate=0`, `DestIsAggregate=2`; shared: `1` in place of `2`.
  Rejected: a `UmlLinkKind.composition` on `UmlLink` (every link pass would have to re-read the
  diamond columns, which is RISK-1's failure mode); a `SubType` cross-check (D-5). Compositions
  feed `_outside_rows` like links, so an outside or excluded end is listed in
  `uml_outside_classes` and named, never a `LookupError` (A-9). Task 1.0 records Sparx's
  documentation of these columns; the developer's EA probe is an acceptance check before the
  release ([RISK-9](#risk-9), task 1.12).
- <a id="pd-2"></a>**PD-2** (DEC-2 as amended by [D-6](#d-6)): the association beside a composition is found among the converted
  associations between the two classes that give a slot held by the whole and ranging over the
  part (a `Source -> Destination` association whole → part, or a `Bi-Directional` one with the
  part-side role). The classes must match exactly: an association to a sub- or superclass of the
  composition's part is not a candidate (A-17). None: problem "a composition needs an association
  whole → part that names the role". Two or more candidates: the composition names the one it
  marks by a role written on it (EA `DestRole`/`SourceRole` on the Aggregation, equal to the
  association's role); so one whole may hold two owned roles to one part class (two compositions,
  each naming its role) beside an internal reference (A-3). Two or more candidates and no
  matching role on the composition: problem naming the roles. A role on a composition that
  matches no candidate is a problem. A note on a composition, or a role where a single candidate
  makes it unneeded, is a `composition-named` convention line.
- <a id="pd-3"></a>**PD-3** (DEC-3): an Association with `SourceIsAggregate = 2` is a `boundary_owned` problem
  whose message names the fix ("draw an Aggregation (composition) whole → part beside a plain
  association"); the existing refusal of `DestIsAggregate = 2` keeps its text. `_is_owned` reads
  the tree only (PD-5). A shared association end (`1`) stays a plain reference, as today.
- <a id="pd-4"></a>**PD-4** (DEC-4, DEC-5): the tree and the roots are built in a new module
  `rdf_persistence_generation/uml/aggregates.py`, after `collect_elements` and `parents`, before
  any slot is read. DEC-4 (re-shaped) is a tree of instances; at class level the compositions
  form a graph. Part-ness is inherited down generalisation from any part, abstract or concrete
  (A-16): a composition to `Chapter` makes `Appendix is_a Chapter` a part too. A whole may be
  abstract; its parts are reached when a concrete descendant of it is reached. A part class may
  have several whole classes (A-2) and a composition may recurse (`Section ◆ Section`, A-1), so a
  part class may belong to several aggregates (A-4). Tops are the derived roots, the «tenant
  root», and abstract classes whose concrete descendants are all tops. The pass computes, by a
  walk from every top, `reached_from`: for each part class the set of tops that reach it. Checks,
  each a `boundary_owned` problem naming the classes: a part class with an empty `reached_from`
  (it names the part and its whole classes; this covers a cycle no top enters, named as the
  cycle's classes in order); a class drawn «root» that is a part (`root_class`, PD-6). A
  recursive composition whose class some top reaches is accepted. `_check_root_paths` moves out
  of `collect_elements` to run after derivation.
- <a id="pd-5"></a>**PD-5** (DEC-5): derivation. A class is a derived root when it is in `ctx.elements`, concrete,
  not an enumeration, not «tenant root», in a package whose `module_kind` is `domain`, and no composition's part
  (directly or by inheritance, PD-4). Not-generated and drawn toolkit classes are never in
  `ctx.elements`, so they are excluded by construction. `UmlElement` gains `is_drawn_root`
  (from the stereotype); `is_root` is set by derivation. The owned slots are the slot ends of PD-2's
  associations; `_classes` takes "is a part" from the tree, not from "a range of an owned slot".
  Each root (and the tenant root, when it has parts) gets one `root` report line:
  `root  Book  parts Chapter, Page` (parts in tree order, depth-first, each once, recursion shown
  once; parts reached through an abstract whole the root inherits are listed), `no parts` when none.
  The `module_kind` of each package is read before derivation by a pure helper
  `package_kinds(packages, tags) -> dict[package_id, kind]` from the package's tagged value
  (default `domain`); it reports nothing. `_module_kinds` keeps its per-module conflict check
  where it is, so no problem is reported twice (A-5).
- <a id="pd-6"></a>**PD-6** (DEC-6): when any class is drawn «root», the drawn set and the derived set are
  compared; each class in one only is a `root_class` problem: "drawn «root» but a part of X" or
  "derived root (no composition's part) but not drawn «root»". Equal sets give one
  `deprecated-root` line naming the count. The comparison covers the concrete classes of domain
  modules only (A-12): a «root» on an abstract class is a `root_class` problem "abstract «root»:
  drop it, the abstract-root rule derives it"; a «root» in a non-domain module keeps today's
  meaning (`AggregateRoot` and `rp_path`) and is outside the comparison, so a stored access class
  still converts.
- <a id="pd-6a"></a>**PD-6a** (DEC-6, A-15): the byte-identical claim is narrowed to what holds. It covers the
  schema files and side files (roles, workflows), not the report (which gains `root` and
  `deprecated-root` lines and is re-goldened with a reviewed diff, RISK-4), and only models whose
  boundaries restate compositions: every boundary-owned association is the only association
  between its two classes, its pair is drawn as a composition, and no boundary owned a
  part → part reference. Today a boundary owns every member-to-non-root association; such a model
  (an internal reference owned by accident, a self-association) changes output when redrawn. That
  is RISK-10; the migration note tells the modeller to diff the schemas.
- <a id="pd-7"></a>**PD-7** (DEC-6, no-go geometry): boundaries are read by name and diagram only. `_Boundaries`
  and its geometry problems (straddle, placed twice, members differ between diagrams, "a boundary
  needs exactly one root") are deleted; `UmlBoundary.member_ids` is removed. A boundary in a
  converted package whose name (after an optional leading `Aggregate:`) is not the written name of
  a derived root or the tenant root is a `boundary-disagrees` convention line (D-1: DEC-6's
  "members are not one root and its parts" cannot be known without geometry). `QeaBuilder.boundary`
  gains `package=` and `name=` so a fixture boundary sits in a converted package (A-24).
- <a id="pd-8"></a>**PD-8** (DEC-7): «own graph» is the composition's stereotype (case-insensitive, as stereotypes
  are read today). Any other stereotype on a composition is a `no_rule` problem. The part must be
  a class left out as `NOT_GENERATED` by a `--not-generated` stereotype (not a drawn toolkit class);
  a generated part is a `boundary_owned` problem: "«own graph» to a generated class needs
  `dependent-aggregates`; mark the part with a not-generated stereotype or draw a plain
  composition". A plain composition to a not-generated part is a problem ("a not-generated part is
  stored apart: use «own graph»"). A class whose whole (transitively) is a not-generated «own
  graph» part is left out as not generated with a `not-generated` line "inside the own graph of X";
  it takes no part in derivation, and links to it range over `uri` as for any not-generated class.
  Order (A-8): the left-inside marking runs first, then the refusals. A composition whose whole
  is not generated or left inside converts to nothing and is exempt from every composition rule,
  whatever its part's stereotype: a not-generated part under a not-generated whole, a plain or
  «own graph» composition inside an own graph, all accepted. Left-inside classes are removed from
  `ctx.elements` and from `parent_of` (A-7); a generalisation to or from one is a
  `boundary_owned` problem "X is inside the own graph of Y; it cannot take part in a
  generalisation", so no later pass meets a dangling label. Ends that are not converted classes
  (A-9): a part or whole outside the subtree or in an excluded package is a `boundary_owned`
  problem "the composition crosses the converted subtree"; a drawn toolkit class as part or whole
  is a problem "toolkit classes are composed by mixins, not compositions"; an enumeration as part
  is `no_rule`; the «tenant root» as part is `root_class`. A domain whole composing a part of a
  non-domain module is a problem naming both packages (A-25), since `rp-generate`'s boundary
  check would refuse the import later.
- <a id="pd-9"></a>**PD-9** (DEC-7): the whole's slot (PD-2's association) ranges over `uri`, is not `owned`, and
  carries the slot annotation `rp_loaded_graph: true`. The tag is declared as a new `RpAnnotation`
  value in `rdf_persistence/model/rp_core.yaml` ("Slot annotation, `true` when the slot's values
  are the IRIs of graphs loaded for the holder's aggregate and deleted with it; the converter writes
  it for an «own graph» composition"), regenerated by the lead with `make generate`; no library
  code reads it in this change. Rejected: an undeclared tag (the metamodel is where every `rp_` tag
  is listed and documented; an undeclared one cannot be checked). D-2. `checks/hard.py`
  `ALLOWED_ANNOTATIONS` gains `RpAnnotation.RP_LOADED_GRAPH: BOOLEAN`, so `rp_loaded_graph: maybe`
  fails `rp-generate`'s hard check (A-22). Because `tags._ANNOTATION_NAMES` lists every
  `RpAnnotation`, a class tagged `rp_loaded_graph` in UML now gets "not a class annotation" where
  it got `ignored-tag`; the error matrix lists it.
- <a id="pd-10"></a>**PD-10** (DEC-8): every converted association end that is not owned and ranges over a
  generated class T is a pointer. It is refused only when T is a composition part (or, for an
  abstract T, every concrete descendant is one) and the holder shares no top with T:
  `reached_from(T)` and the holder's tops (itself when a top, else its `reached_from`) do not
  intersect (A-4, A-13). It is then a `boundary_owned` problem "points at X, a part of Y; point at
  Y" (Y: the tops of X). Every other target keeps today's behaviour: roots, the tenant root, an
  abstract all-root class, a part of an aggregate the holder belongs to (an internal reference),
  and classes that are no part at all (access, technical and value classes, classes inherited
  from a toolkit root, an abstract class mixing roots and parts). This also covers the pointer
  half of C-9. C-9's second half (a role owned on one whole and a pointer elsewhere) applies to
  domain slots only; a slot replaced by a toolkit slot (`split_toolkit`, e.g. `dct:hasPart` of a
  `ReferenceCollection`) is exempt (A-26).
- <a id="pd-11"></a>**PD-11** (DEC-9): the reader reads a Realisation (`Realisation` or `Realization`) whose source
  is an Object of the converted packages into a new `UmlObject.realised_ids` (multivalued), never a
  `UmlLink`. In the converter (`roles.py` `_is_role`, before the classifier is read): no classifier
  and one Realisation → the target is the classifier; a Realisation to another class than the
  classifier, or two Realisations to different classes → a `role_definition` problem naming the
  Object and both classes. A Realisation from anything other than an Object stays a `no_rule`
  problem (the existing `test_uml_qea.py` row keeps its meaning). An Object of a domain class stays
  refused as today. Edge cases (A-20): an Object in an excluded package, or outside the subtree,
  with a Realisation to a converted class is skipped with an `excluded-link` / `outside-link` line;
  the reader keeps a Realisation whose Object is converted and whose target is outside the subtree
  (it is read for the classifier, the target listed as an outside class); a Realisation drawn
  class → Object is read by its ends' types, not its direction, so it counts as the Object's.
- <a id="pd-12"></a>**PD-12** (DEC-10, DEC-11): diagrams are read by membership only. A new generated `UmlDiagram`
  (`diagram_id`, `name`, `package_id`, `diagram_type`, `element_ids`, `hidden_connector_ids`) is
  read from `t_diagram`, `t_diagramobjects` (`Object_ID` only) and `t_diagramlinks`
  (`DiagramID`, `ConnectorID`, `Hidden`). A connector is shown on a diagram when both its ends are
  members and no `t_diagramlinks` row hides it (EA's own display rule; RISK-6). Statecharts are
  out. A class diagram of a converted package is an aggregates diagram when its name ends with the
  suffix ` · aggregates` (U+00B7 between spaces); only then is the prefix checked against the
  package name (DEC-11's `<module>` is read as the package name, the one name a modeller sees in
  EA, A-18). Lines: an aggregates diagram showing an element other than a class, note, text or boundary, or a
  connector other than a composition, a NoteLink or a generalisation (`aggregates-diagram`); any
  other class diagram of a converted package showing a composition (`composition-diagram`); an
  aggregates diagram whose name does not start with its own package's name (`aggregates-diagram`).
  EA shows every connector whose ends are on a diagram, so the guide tells the modeller to hide
  the associations on the aggregates diagram and the compositions on the others (task 3.2).
- <a id="pd-13"></a>**PD-13** (DEC-10): convention kinds. The new `ReportKind` values are `root`,
  `deprecated_root`, `boundary_disagrees`, `composition_named`, `aggregates_diagram`,
  `composition_diagram`, `unprefixed_name`, `unused_enumeration`, `drawn_toolkit_parent`,
  `tenant_required_pointer`. `CONVENTION_KINDS`, the `frozenset[ReportKind]` in
  `uml/conventions.py` whose lines fail `--check`, is exactly these eleven:
  `boundary_disagrees`, `composition_named`, `aggregates_diagram`, `composition_diagram`,
  `unprefixed_name`, `unused_enumeration`, `drawn_toolkit_parent`, `tenant_required_pointer`,
  `no_note`, `unspecified_multiplicity`, `implicit_meaning`. `deprecated_root`
  is informational: a model that still draws an agreeing «root» passes `--check`, so CI can gate a
  model during the whole transition (migration steps 1–4) and the modeller drops «root» at step 5
  without a red build in between. `toolkit_slot_kept` stays informational (A-14): the conventions page
  prescribes the abstract reference collection whose role is reported `toolkit-slot-kept`, and
  `slots._kept` writes the line when a drawn shape differs from the toolkit slot, not when an
  attribute repeats one; C-8's breach is already folded into the toolkit slot. A test pins that
  the page's reference-collection model passes `--check`. Informational
  kinds (`root`, `deprecated_root`, `not_generated`, `outside_link`, `excluded_link`, `toolkit_filled`, `toolkit_slot_kept`, `role`,
  `workflow`, `derived_iri`, `external_list`, `ignored_tag`, `ignored_stereotype`, `stale_file`)
  never fail `--check`. Rejected: an annotation per enum value in the generated model (the
  generated Python enum does not carry annotations).
- <a id="pd-14"></a>**PD-14** (DEC-10): `--check` is a flag of `rp-uml2linkml`; `--out` becomes required unless
  `--check` is given. It reads and converts exactly as a run does, never calls `write`, prints the
  problems to stderr as today and the convention lines to stdout in the report format
  (`<kind>\t<element>\t<message>`), and exits 1 when either is non-empty, 0 otherwise, 2 on a usage
  error. The whole-model check (`howto/uml-to-linkml.adoc#whole-model`) loads staged files, so
  `--check` does not run it; the guide says so. A normal run never fails on a convention line.
  Reader problems short-circuit, as today (A-21): when `read_qea` returns problems (a bad diamond,
  a Realisation from a class), `--check` prints only those and exits 1; the converter's problems
  and the convention lines follow once they are fixed. The guide says so.
- <a id="pd-15"></a>**PD-15** (DEC-10): the C-x classification below is the port list; the conventions are written
  generically (no package list, no banned-name table: "toolkit slot" means the toolkit's
  `slot_uri`s the converter already knows).
- <a id="pd-16"></a>**PD-16** (DEC-12, P-0014): the conventions page `reference/uml-conventions.adoc` holds each
  convention with a UML snippet (PlantUML, as the page's existing snippets) and the LinkML it
  becomes; its `[#boundary]` section is rewritten as `[#composition]`, its "What fails" table
  updated. The guide `howto/uml-to-linkml.adoc` gains the terms, the deletion test, the two diagram
  kinds, the `--check` step and links to the rules and to the conventions page. The guide names
  `rdf_persistence_generation.uml.qea.read_qea` as the public reader a consumer's own checks reuse.
- <a id="pd-17"></a>**PD-17**: stages. Stage 1 the converter core (composition, tree, roots,
  transition, own graph, pointers, Realisation) because every later finding reads the tree; stage
  2 `--check`, diagrams and the ported conventions; stage 3 docs, rules and changelog. Each stage
  one PR. No release is cut between stage 1 and stage 3 (A-23): stage 1 ships breaking refusals
  while the migration's first step (`--check`) arrives in stage 2. Each task passes its own task
  gate (A-11): the tasks that change the reading of ownership are one task (1.6), and nothing is
  removed before its last reader goes.
- <a id="pd-18"></a>**PD-18** (DEC-13.1): the boundary geometry leaves `qea.py` by deletion, not by a move: DEC-6
  stops reading it, so `_Boundaries`, `Rect`, `_relation`, `INSIDE`/`STRADDLE`/`OUTSIDE` and the
  `Rect*` columns of `t_diagramobjects` in the reader's required-columns table are removed. The
  boundary is read as a `UmlBoundary` (name, package, diagrams) by a membership-only function.
  Pinned by a unit test that the required columns of `t_diagramobjects` are `Diagram_ID` and
  `Object_ID` only, and by an `ast-grep` acceptance (no `RectTop`/`RectLeft` in
  `rdf_persistence_generation/`). Rejected: moving the geometry to a module of its own (nothing
  would call it).
- <a id="pd-19"></a>**PD-19** (DEC-13.2): the new passes are functions of their inputs, never reading
  or writing `Context`:
  - `aggregates.py` `package_kinds(packages: list[UmlPackage], tags: list[UmlTaggedValue]) ->
    dict[int, str]`;
  - `aggregates.py` `derive_aggregates(elements: list[UmlElement], compositions:
    list[UmlComposition], links: list[UmlLink], parent_of: Mapping[int, str], package_kinds:
    Mapping[int, str], left_out: Mapping[int, LeftOutReason]) -> UmlAggregates`;
  - `aggregates.py` `check_pointers(usages: list[Usage], toolkit_usages: list[Usage], aggregates:
    UmlAggregates, elements: list[UmlElement]) -> list[CheckProblem]` (tested in
    `test_uml_aggregates.py`, task 1.7);
  - `conventions.py` `convention_lines(model: UmlModel, elements: list[UmlElement], aggregates:
    UmlAggregates, usages: list[Usage]) -> list[ReportLine]`;
  - `conventions.py` `missing_notes(elements: list[UmlElement], usages: list[Usage],
    toolkit_usages: list[Usage]) -> list[ReportLine]` (PD-20).
  `Usage` (`slots.py`) is a hand-written class (the rest of #343), so it is an allowed input; only
  `Context` is forbidden. `UmlAggregates` is a generated record of
  `rp_generation.yaml` (P-0007): `root_ids`, `tenant_root_id`, `part_of` as a list of
  `UmlPartOf`, one row per (part, whole) (`part_id`, `whole_id`, `own_graph`, `composition_id`),
  `reached_from` as a list of `UmlReach` (`part_id`, `top_ids` multivalued; A-4), `owned_ends` as
  a list of `UmlOwnedEnd` (`link_id`, `holder_id`), `left_inside_ids` (PD-8), `problems`,
  `report_lines`. `convert.py` merges the returned findings into `ctx.findings` and the derived
  flags into the `UmlElement`s, in one visible sequence.
- <a id="pd-19a"></a>**PD-19a** (DEC-13.2, A-6): no import-linter contract. The new passes need `Usage`
  (`slots.py`), the direction rule (`links.py`) and `local_of`/`path_of` (`context.py`), each of
  which imports `uml.context`, and import-linter counts indirect imports; a contract would force
  the split of `slots.py` and `context.py`, which is the rest of #343. DEC-13 item 2 is kept as
  "the new passes take arguments and return values": pinned by a unit test,
  `test_uml_pass_signatures.py`, that inspects the five functions of PD-19 (no parameter
  annotated `Context`; parameters of generated records, `Usage`, mappings or lists of them; a
  return annotation that is a generated record, a mapping, or a list of generated records) and
  calls each with hand-built records. Rejected: a contract with `allow_indirect_imports` (it would
  fail at once); moving the helpers now (beyond the appetite).
- <a id="pd-20"></a>**PD-20** (DEC-13.3, A-19): one home for "no note". The three sites are `classes.py`
  `_described` (a class or an enumeration), the enumeration-literal line (`classes.py:374`) and
  `slots.py` `described` (an attribute, a role, an enumeration dependency). They return the
  description only. `conventions.py` `missing_notes(elements, usages, toolkit_usages)` writes every
  `no-note` line, enumeration literals included and the attributes `split_toolkit` moved to the
  toolkit usages included, with today's element names and message, so the report text does not
  change. Pinned by the stage-2 golden report unchanged in its `no-note` lines, a new row with a
  noteless attribute that becomes a toolkit slot and a noteless literal, the existing
  `test_uml_no_note_coverage.py` unchanged, and an `ast-grep` acceptance: `ReportKind.NO_NOTE`
  occurs once in `rdf_persistence_generation/uml/`.
- **Left open of #343**: one owner for package paths and exclusion; `Usage`/`Composed` as
  generated records; the split of `slots.py`; the import-graph code of `convert.py`; shared helpers
  across peer passes; an import contract for the existing passes; indexes for large models. The PR
  of stage 1 says so on #343, as does refactoring the existing passes the way PD-19 shapes the new
  ones.

## Classification of the consumer's C-1..C-12 (DEC-10)

Test: a convention whose breach changes the generated LinkML is meaning (problem); otherwise
presentation (convention line, fails `--check` only).

| C | Convention | Class | Finding here |
|---|---|---|---|
| C-1 | prefixed names in the prefix map | unknown prefix: already enforced (problem `class_iri`); unprefixed: presentation | `unprefixed-name` for a class, attribute or role (an enum literal keeps `implicit-meaning`); the boundary-name half is not ported (C-7) |
| C-2 | named role with multiplicity | already enforced: no role is a `no_rule` problem; no multiplicity is `unspecified-multiplicity` | none new; `unspecified-multiplicity` becomes a convention kind |
| C-3 | notes everywhere | already enforced as `no-note` | none new; `no-note` becomes a convention kind |
| C-4 | a concrete class is a root, tenant root or part | meaning, subsumed by DEC-5/DEC-6 (every concrete class now is one, visibly) | `root` lines; DEC-6 problems |
| C-5 | every enumeration used by a dependency | presentation (the enum is generated either way) | `unused-enumeration` |
| C-6 | one module per package; acyclic imports | module per package already enforced (`package_module`); acyclic: not ported (DEC-10); the package list is consumer-specific | none |
| C-7 | boundaries | not ported, replaced by DEC-6 | `boundary-disagrees` (PD-7) |
| C-8 | no attribute duplicates a toolkit slot | already enforced: the converter folds the attribute into the toolkit slot (R-15) | none new; `toolkit-slot-kept` stays informational (PD-13, A-14); the banned table is not ported |
| C-9 | a role IRI owned on one class kind, never also a pointer | meaning: its pointer half is DEC-8 (PD-10); a role owned by one whole and used as a pointer to a root elsewhere splits one slot into owned and referencing usages | `boundary_owned` problem "role R is owned on W and a pointer on H" |
| C-10 | pointers over roots | meaning, DEC-8 | PD-10 problem |
| C-11 | domain only drawn; toolkit classes by tagged value | presentation (a drawn toolkit parent and `rp_mixins` give the same LinkML, R-28); the consumer's tag table is not ported | `drawn-toolkit-parent` for a generalisation to a drawn toolkit class (a drawn `rp:RoleDefinition` that classifies Objects is not reported) |
| C-12 | a required pointer is satisfiable at tenant creation | presentation by DEC-10's test (the LinkML is the same; the tenant cannot be created at run time) | `tenant-required-pointer` for a required pointer from the tenant root or its parts to a class outside its aggregate |

C-13 (the consumer's own attributes) stays in the consumer (DEC-10); it reuses `read_qea`.

## Algorithm / approach

Order in `convert` (PD-19 makes it explicit):

1. `collect_elements` (classes admitted, «root» kept as `is_drawn_root`), `parents`,
   `package_kinds` (PD-5, A-5).
2. `derive_aggregates(...)` → `UmlAggregates`: (a) mark the classes below a not-generated «own
   graph» part as left inside, and exempt compositions whose whole is not generated or left
   inside (PD-8, A-8); (b) refuse ends that are not converted classes, a generated «own graph»
   part, a plain composition to a not-generated part, a cross-kind composition (PD-8, A-9, A-25);
   (c) index compositions by part, inheriting part-ness down `parent_of` from any part (A-16);
   (d) the derived roots (PD-5); (e) walk from each top (a visited set per top, so recursion
   terminates), filling `reached_from`; refuse part classes with none (A-1, A-2); (f) find each
   composition's association (PD-2, A-3, A-17) → `owned_ends`, or the `uri` + `rp_loaded_graph`
   end for «own graph»; (g) the DEC-6 comparison (PD-6, A-12); (h) `root` lines.
3. Merge into `ctx`: `is_root`, part flags; remove left-inside classes from `ctx.elements` and
   `parent_of` (A-7); then `_check_root_paths`.
4. `link_usages(ctx, model, owned_ends)`: owned only by `owned_ends`; composite associations
   refused (PD-3).
5. `check_pointers(...)` (PD-10, C-9) → problems.
6. Layout, `mark_abstract_roots`, classes (a part is a tree member), toolkit slots, roles
   (PD-11), workflows, as today.
7. `convention_lines(...)`: notes (PD-20), names, enumerations, diagrams, toolkit parents,
   boundaries, tenant pointers.
8. A normal run writes when there is no problem; `--check` prints and exits (PD-14).

The conversion stays pure and deterministic: every list is sorted by connector id, object id or
label before use, so a second run is byte-identical (the existing "stable output" scenario).
Nothing is retried; a run is read-only on the `.qea` and all-or-nothing on `--out`, as today.

### Worked example 1: a shelf and its books, depth 3

Package `library` (domain). Drawn: `lib:Shelf`, `lib:Book`, `lib:Chapter`, `lib:Page`,
`lib:Reader`, no «root» anywhere.

```
Shelf   ──lib:holds 0..*──────▶ Book      Shelf   ◆──── Book     (Aggregation, diamond at Shelf)
Book    ──lib:hasChapter 1..*─▶ Chapter   Book    ◆──── Chapter
Chapter ──lib:hasPage 1..*────▶ Page      Chapter ◆──── Page
Reader  ──lib:borrows 0..*────▶ Book      (no composition)
```

EA may store `Shelf ◆ Book` as Start=Book, End=Shelf with the diamond column at the Shelf end;
PD-1 reads whole = Shelf either way (the exact columns are recorded by task 1.0). Adding
`Book ◆ Section`, `Section ◆ Section` (subsections) is accepted: Book reaches Section, and each
section instance sits in one whole (DEC-4 re-shaped). Derived roots: Reader, Shelf; Book, Chapter, Page are parts. Report:
`root Reader no parts`, `root Shelf parts Book, Chapter, Page`. LinkML: `holds`, `has_chapter`,
`has_page` carry `owned: true` and `inlined_as_list: true`; Shelf and Reader mix in
`AggregateRoot` with `rp_path`. `Reader.borrows → Book` points into Shelf's part: problem
"Reader.borrows points at Book, a part of Shelf; point at Shelf". Retargeted to Shelf, the run
writes. Drawn the old way (Shelf and Reader «root», a boundary) plus the compositions: the same
schemas and a `deprecated-root` line.

### Worked example 2: a shelf count and its loaded reports (the generic form of #437 A.5)

```
lib:ShelfCount            ◆«own graph»── lib:CountReport «loaded graph»
                          ◆«own graph»── lib:ShapeReport «loaded graph»
lib:ShapeReport           ◆───────────── lib:ShapeResult   (plain: inside the report's graph)
each composition drawn beside an association lib:countReport / lib:shapeReport / lib:result
```

Converted: `ShelfCount.count_report` and `ShelfCount.shape_report` have `range: uri`, no `owned`,
`annotations: {rp_loaded_graph: true}`; `CountReport` and `ShapeReport` are not generated (as
today); `ShapeResult` is left out "inside the own graph of ShapeReport", and `lib:result` gives no
slot. Report: `root ShelfCount no parts`. Adding `lib:Inventory ◆«own graph»── lib:ShelfCount`
(a generated part) is a problem naming `dependent-aggregates`; nothing is written.

### Worked example 3: recursive sections, a shared part class, a pointer into a part (DEC-4 re-shaped)

Package `library` (domain), no «root». Each composition beside its association:

```
Book    ◆── Section   (lib:hasSection 1..*)       Journal ◆── Section  (lib:hasSection 0..*)
Section ◆── Section   (lib:hasSubsection 0..*)    Reader  ──lib:cites 0..*──▶ Section
```

`derive_aggregates` returns (ids by label for reading):

| record | rows |
|---|---|
| `root_ids` | Book, Journal, Reader |
| `part_of` (`UmlPartOf`) | (Section, Book), (Section, Journal), (Section, Section) |
| `reached_from` (`UmlReach`) | Section: {Book, Journal} |
| `owned_ends` | Book.has_section, Journal.has_section, Section.has_subsection |

Accepted: the recursion is entered from Book and Journal, and one part class sits under two
wholes of different tops; each Section instance is inlined in exactly one whole's graph.
Report: `root Book parts Section`, `root Journal parts Section`, `root Reader no parts`.
`check_pointers`: `Reader.cites` ranges over Section, whose tops {Book, Journal} do not meet
Reader's {Reader}, so it is a problem. `rp-uml2linkml --check` prints to stderr

```
[boundary_owned] Reader.cites: points at Section, a part of Book, Journal; point at Book or Journal
```

and exits 1 with nothing on stdout and nothing written. Retargeted to `Book`, it exits 0. Without
the two root compositions (only `Section ◆ Section`), Section is in a cycle no top enters:
`[boundary_owned] Section: compositions form a cycle Section → Section that no root reaches`.

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Read `Start_Object_ID` as the whole | Read the diamond column once (PD-1) | EA stores the drawing direction (RISK-1) |
| Infer a part from multiplicity, names or `1..1` | Only compositions | DEC-5, rabbit-hole |
| Keep `_Boundaries` "for the report" | Name-only boundary line (PD-7) | No-go: no geometry |
| Fill `Context` inside `aggregates.py`/`conventions.py` | Return `UmlAggregates`, findings (PD-19) | DEC-13.2 |
| Copy the consumer's package list, banned table or tag table | Generic reading (PD-15) | Principle 3 |
| Make a presentation line a problem in a normal run | A convention line; `--check` fails on it | DEC-10, Q10 |
| Hand-write a dataclass for the tree | Generated records in `rp_generation.yaml` | P-0007 |
| Edit a golden by hand | `make refresh-golden` and a reviewed diff | the golden is the byte-identity proof |
| Use consumer names in fixtures, specs or docs | the `lib:` library domain | AGENTS.md principle 3 |

## Error matrix

Every problem row: exit 1, nothing written, the problem printed sorted as today. A line row of a
kind in `CONVENTION_KINDS` ([PD-13](#pd-13)) writes in a normal run and exits 1 under `--check`;
a line row marked informational never fails `--check`.

| Input | Finding | Message (element: text) |
|---|---|---|
| Aggregation with value `1` at an end (shared) | problem `boundary_owned` | `W -> P`: a shared aggregation; draw a composition (strong) or a plain association |
| Aggregation with no end marked, or both | problem `no_rule` | `A -> B`: composition with no single diamond end |
| Composition, no association whole → part | problem `boundary_owned` | `W -> P`: a composition needs an association W → P that names the role |
| Composition, two or more such associations and no role on the composition (D-6) | problem `boundary_owned` | `W -> P`: two associations (r1, r2) beside one composition; name one on the composition |
| Composite association (`SourceIsAggregate=2`) | problem `boundary_owned` | `W.r`: a composite association; draw an Aggregation (composition) W → P beside a plain association |
| Recursive composition (`Section ◆ Section`) a top reaches | accepted | — |
| Part class under several wholes (same or different tops) | accepted; the part belongs to each | — |
| Cycle no top enters | problem `boundary_owned` | `A`: compositions form a cycle A → B → A that no root reaches |
| Part class no top reaches | problem `boundary_owned` | `P`: no root reaches it (wholes W1, W2) |
| Association to a sub- or superclass of the composition's part | not a candidate (then "no association") | as "Composition, no association" |
| Two candidates, the composition names one role | accepted | — |
| Role on a composition matching no candidate | problem `boundary_owned` | `W -> P`: role r names no association W → P |
| Aggregate value other than 0, 1 or 2 at an end (D-5) | problem `no_rule` | `A -> B`: aggregate value V |
| `SubType` empty or any value (D-5) | not read | — |
| Part or whole outside the subtree or excluded | problem `boundary_owned` | `W -> P`: the composition crosses the converted subtree |
| Drawn toolkit class as part or whole | problem `boundary_owned` | `W -> P`: toolkit classes are composed by mixins |
| Enumeration as part | problem `no_rule` | `W -> E`: composition to an enumeration |
| «tenant root» as part | problem `root_class` | `T`: the tenant root cannot be a part |
| Domain whole, part in a non-domain module | problem `boundary_owned` | `W -> P`: a domain part cannot live in module kind K (packages a, b) |
| Generalisation to or from a class inside an own graph | problem `boundary_owned` | `X`: inside the own graph of Y; it cannot take part in a generalisation |
| Composition under a not-generated or left-inside whole | accepted, converts to nothing | — |
| «root» on an abstract class | problem `root_class` | `C`: abstract «root»: drop it, the abstract-root rule derives it |
| «root» in a non-domain module | accepted as today, outside the DEC-6 comparison | — |
| Pointer to an access, technical or value class | accepted as today | — |
| Class tagged `rp_loaded_graph` in UML | problem (was `ignored-tag`) | `C`: rp_loaded_graph is not a class annotation |
| `rp_loaded_graph: maybe` in LinkML | `rp-generate` hard check | not a boolean |
| Realisation from an excluded or outside Object | line `excluded-link` / `outside-link` | — |
| «root» drawn on a part / derived root not drawn | problem `root_class` | `C`: drawn «root» but a part of W / a root (no composition's part) but not drawn «root» |
| «own graph» to a generated class | problem `boundary_owned` | `W -> P`: «own graph» to a generated class needs dependent-aggregates |
| Plain composition to a not-generated class | problem `boundary_owned` | `W -> P`: a not-generated part is stored apart; use «own graph» |
| Other stereotype on a composition | problem `no_rule` | `W -> P`: connector stereotype S |
| Pointer into another aggregate's part (C-10) | problem `boundary_owned` | `H.r`: points at P, a part of W; point at W |
| Role owned on W and a pointer elsewhere (C-9) | problem `boundary_owned` | `r`: owned on W and a pointer on H |
| Realisation to another class than the classifier | problem `role_definition` | `obj`: realises X but its classifier is Y |
| Two Realisations from one Object to different classes | problem `role_definition` | `obj`: realises X and Y |
| Realisation from a class | problem `no_rule` (as today) | `A -> B`: Realisation connector |
| Model draws «root», sets agree | line `deprecated-root`, informational (PD-13: does not fail `--check`) | model: N «root» stereotypes agree with the derived roots; drop them |
| Boundary naming no root | line `boundary-disagrees` | boundary name: names no root; a boundary is an annotation |
| Note on a composition, or a role where one candidate makes it unneeded | line `composition-named` | `W -> P`: the association carries the role and note |
| Aggregates diagram with an association or non-class | line `aggregates-diagram` | diagram: shows X |
| Other class diagram with a composition | line `composition-diagram` | diagram: shows the composition W → P |
| Unprefixed class, attribute or role | line `unprefixed-name` | name: no prefix |
| Enumeration no dependency uses | line `unused-enumeration` | enum: used by no dependency |
| Generalisation to a drawn toolkit class | line `drawn-toolkit-parent` | C: prefer `rp_mixins=T` |
| Required pointer from the tenant aggregate outward | line `tenant-required-pointer` | `T.r`: required, cannot be set when the tenant is created |
| `--check` without `--prefixes` or `--package` | usage | exit 2, one `rp-uml2linkml:` line |
| Run without `--check` and without `--out` | usage | exit 2: `--out` is required unless `--check` |
| A `.qea` without `t_diagramlinks` | usage (the existing missing-table rule) | exit 2 naming the table; EA always has it (RISK-6) |

## Risks / Trade-offs

- <a id="risk-1"></a>**RISK-1** EA connector direction (likelihood medium, impact high: a silently
  flipped tree). Mitigation: PD-1 reads the end column in one function (D-5); unit rows draw each
  composition both ways (Start=whole and Start=part) and expect the same `UmlComposition`; the
  golden is drawn part → whole on purpose.
- <a id="risk-2"></a>**RISK-2** a consumer redraws before the release (likelihood low, impact medium). Mitigation:
  DEC-6 keeps «root» models converting byte-identical once compositions are added; the changelog
  migration note (below) gives the order; the consumer is told the change id at release.
- <a id="risk-3"></a>**RISK-3** rule drift between this repository's adopted rules and the consumer's copies
  (likelihood medium, impact low). Accepted (Q8): the consumer retires its copies in its next model
  round; each adopted note quotes its source.
- <a id="risk-4"></a>**RISK-4** output changes when a model is redrawn (likelihood medium, impact high). Mitigation:
  the stage-1 and stage-2 goldens are redrawn with compositions and keep their schema files
  byte-identical; only the report golden changes, reviewed line by line; a unit test converts one
  model drawn both ways and compares the schemas.
- <a id="risk-5"></a>**RISK-5** (planner) existing tests draw plain concrete classes, which become
  derived roots (likelihood high, impact medium: many `test_uml_rules.py` rows change).
  Mitigation: task 1.6 sweeps them; a row that tested ownership through a boundary becomes a composition row; a row
  that drew a non-root, non-part class on purpose adds the composition or the abstract flag that
  states its intent; no assertion is loosened.
- <a id="risk-6"></a>**RISK-6** (planner) `t_diagramlinks` rows: EA writes one only for some connectors. Mitigation:
  PD-12 shows a connector when both ends are on the diagram unless a row hides it, so a missing row
  never hides a connector. Accepted: a connector hidden by another mechanism is read as shown, so
  the worst case is a spurious convention line, never a changed schema.
- <a id="risk-7"></a>**RISK-7** (planner) PD-9 touches `rdf_persistence/model/rp_core.yaml` (one enum value, no code
  reads it) against the no-go "no runtime change in `rdf_persistence/`". Accepted by D-2;
  `make check-generated` proves the regenerated files.
- <a id="risk-8"></a>**RISK-8** (planner) a model that draws no «root» at all gets roots silently (DEC-6 applies only
  when «root» is drawn). Mitigation: the `root` lines list them; `--check` does not fail on them
  (informational); the guide tells a modeller to read the `root` lines after each redraw.
- <a id="risk-9"></a>**RISK-9** (attack A-10) EA's diamond encoding on an Aggregation is assumed,
  not observed (likelihood medium, impact high). Observed on 2026-11-28 in the one EA-saved
  `.qea` on this machine (read-only, column values only): no Aggregation connector; composite
  associations carry `SourceIsAggregate=2`, `DestIsAggregate=0`, `SubType` empty;
  `t_diagramlinks` has `DiagramID, ConnectorID, Geometry, Style, Hidden, Path, Instance_ID`.
  Mitigation: PD-1 reads the end columns only and ignores `SubType` (D-5), so the direction never
  matters and an empty `SubType` is accepted; task 1.0 records Sparx's documentation of the
  columns in `evidence/ea-connectors.md`; fixtures use PD-1's stated columns. Stays open until the
  developer's EA probe (D-4) passes as the `@manual` scenario "An EA-drawn composition reads the
  same either way" of `features/composition.feature`, checked in task 1.12 before any release.
- <a id="risk-10"></a>**RISK-10** (attack A-15) a boundary model outside PD-6a's precondition changes output when
  redrawn (likelihood medium, impact medium). Mitigation: the migration note says to diff the
  converted schemas; `--check` lists what differs only as problems (a pointer into a part) or
  `root` lines; the precondition is stated in the guide.

## Tests that move or change

| Test | Change | Lane afterwards | What it proves |
|---|---|---|---|
| `tests/generator/unit/test_uml_boundaries.py` `test_a_boundary_with_two_roots_is_a_no_rule_problem` | deleted in 1.6 (no geometry) | — | replaced in stage 2 by the `boundary-disagrees` row of `test_uml_conventions.py` (task 2.4); between the two no release is cut (PD-17, A-23) |
| same file, the note/boundary-end and excluded-enum tests | kept | `make test-generator` | a connector to a boundary object is still skipped |
| `tests/generator/unit/test_uml_qea.py` TC-2 "boundary membership by geometry" block | deleted; replaced by membership-only boundary and diagram reading tests | `make test-generator` | the reader reads no geometry (PD-18) |
| `test_uml_qea.py` "unknown connector" Realisation rows | kept; class → class Realisation stays a problem | `make test-generator` | PD-11 accepts Objects only |
| `test_uml_rules.py` R-11 rows (boundary owned, composite owns, boundary with no root, tenant root's boundary, `_owned_on_one_class`) | rewritten as composition rows; the composite row becomes the DEC-3 refusal; `_owned_on_one_class` becomes the C-9/DEC-8 refusal | `make test-generator` | the tree is the only owner |
| `test_uml_rules.py` rows with plain concrete classes | intent made explicit (RISK-5) | `make test-generator` | unchanged assertions |
| `test_uml_golden.py` stage1, stage2 | fixtures redrawn with compositions, schema goldens byte-identical, report golden re-recorded | `make test-generator` | DEC-6 byte-identity (RISK-4) |
| `tests/generator/feature/uml_import.feature` "A package with a root and a part" | rewritten: compositions, no boundary | `make test-generator` | the living scenario, MODIFIED in the delta |
| `test_uml_cli.py` | `--out` optional under `--check` | `make test-generator` | PD-14 |
| `test_uml_no_note_coverage.py` | unchanged | `make test-generator` | PD-20 keeps the report text |
| `tests/generator/integration/test_uml_generate.py`, `test_uml_cycle.py` | fixtures redrawn | `make test-containers` | the converted output still generates |

## Release note and consumer migration (DEC-3, breaking)

`CHANGELOG.md`, under the release that carries this change, **BREAKING** `rp-uml2linkml`:

1. Upgrade, then run `rp-uml2linkml --check` on the unchanged model: every composite association
   is listed, alone, as a problem (D-15); the `root` lines appear once no problem is left. The
   baseline to diff against is the last conversion made with the previous release (D-16).
2. In EA, for each aggregate, draw an Aggregation (composition, strong) from the whole to each part
   beside the existing association; replace each composite association by a plain association plus
   a composition. Keep «root» for now.
3. Convert and diff the schemas against the last conversion: they are byte-identical when each
   boundary-owned association was the only one between its classes and the pairs form the
   compositions you drew (PD-6a); any other difference is a reference a boundary owned by
   accident; decide it. The report gains `root` and `deprecated-root` lines. A `root_class` problem
   names a class to fix.
4. Move loaded-graph parts to «own graph» compositions; point only at roots.
5. Drop «root» and turn boundaries into annotations; add `<package> · aggregates` diagrams.
   An agreeing «root» does not fail `--check` (`deprecated-root` is informational, PD-13), so
   steps 1–4 can run under a CI gate.
6. Put `rp-uml2linkml --check` in CI; retire the model's own copies of the conventions check.

## Spec deltas

`specs/rp-uml-import/spec.md`: MODIFIED "A UML class model converts to toolkit-conformant LinkML"
(boundaries out, compositions in; its first scenario rewritten) and "Role definitions drawn in UML
convert to the roles file" (Realisation); ADDED "Aggregates are drawn as compositions",
"Roots are derived from the compositions", "A part stored in its own graph", "Pointers target
roots", "The conventions check". Features: `features/*.feature` (four files, Q9's groups).

## Open Questions

None open. The three the planner raised were decided by the lead (R-0007), below. Two EPIC
changes were made by the lead, each to be validated by the developer: DEC-4 re-shaped (attack A-1,
A-2) and DEC-2 amended ([D-6](#d-6), attack A-3, logged in `inputs/qa.md`). The EPIC's Impact
line "new link kind" was corrected by the lead to "a new composition record" (PD-1).

## Delivery decisions

Decisions the lead took without the developer, shown for validation at the end (R-0007).

- <a id="d-1"></a>**D-1 (was OPEN-1)**, lead, 2026-11-28: PD-7's name-only reading. `boundary-disagrees` fires when a
  boundary's name names no derived root; no membership is read (the geometry no-go holds).
  Rejected: reading boundary geometry for the transition line.
- <a id="d-2"></a>**D-2 (was OPEN-2)**, lead, 2026-11-28: PD-9 declares `rp_loaded_graph` in `RpAnnotation`
  (`rdf_persistence/model/rp_core.yaml`). It is metamodel data that no library code reads, so the
  no-go "no runtime change in `rdf_persistence/`" holds in substance. Rejected: an undeclared
  converter tag, which `rp-generate`'s lint would not know.
- <a id="d-3"></a>**D-3 (was OPEN-3)**, lead, 2026-11-28: C-12 stays a convention line (`--check` fails on it).
  Revisit if a second consumer needs it as a problem.
- <a id="d-4"></a>**D-4**, lead, 2026-11-28 (the developer away, delivery granted): task 1.0 does not wait for the
  developer's EA drawing. The reader takes the whole from whichever end column (`SourceIsAggregate`
  or `DestIsAggregate`) holds 2, as EA already writes it for composite associations
  (`SourceIsAggregate=2` observed), so the drawing direction never matters. 1 is a shared
  aggregation. Both columns set follow PD-1; `SubType` is not read ([D-5](#d-5) supersedes the
  earlier wording here). Fixtures use the columns PD-1 states. The developer's
  scratch-model probe moves to the acceptance review, before the release (RISK-9 stays open until
  then). Rejected: blocking stage 1 on the probe.
- <a id="d-5"></a>**D-5** (gate G-1), lead, 2026-11-28: for an Aggregation connector, the end column alone decides.
  2 at one end is a composition whose whole is that end, 1 is a shared aggregation (a problem),
  and 2 at both ends or at neither is a problem. `SubType` is not read: EA leaves it empty on the
  rows observed. This supersedes any other `SubType` rule in PD-1, the error matrix, RISK-9 and
  task 1.0.
- <a id="d-6"></a>**D-6** (gate G-5), lead, 2026-11-28: DEC-2 is amended (logged in `inputs/qa.md`). When several
  associations between a whole and a part could carry a composition's property, a role written on
  the composition names the one it marks owned (attack A-3: two owned roles plus an internal
  reference to one part class). No candidate, or several and no role, stays a problem.
- **D-7**, lead, 2026-11-28 (delivery): the machine's test queue is shared with other sessions and
  serialises every gate (about 25 minutes each, mostly queued). Parallel builders on disjoint files
  run only their narrow checks; the lead runs one task gate (`make test-changed check-quality`)
  for the batch before its commit. Edits under `rdf_persistence_generation/` stale the generated
  stamp: builders run narrow tests with the freshness plugin off and the lead regenerates before
  the gate.
- **D-8**, lead, 2026-11-28 (delivery, tasks 1.4/1.8): (a) an excluded or outside Object with a
  Realisation is skipped without a report line. The reader returns only `UmlModel` and has no
  place for one, so PD-11's "with a line" is dropped. Rejected: a skipped-realisations record for
  an edge case. (b) The error-matrix row "other stereotype on a composition: `no_rule`" is the
  converter's, in task 1.6: the reader carries the stereotype as written.
- **D-9**, lead, 2026-11-28 (delivery, task 1.5): `UmlAggregates` gains `loaded_graph_ends` (the
  ends of «own graph» compositions to a not-generated part, which 1.6 marks `rp_loaded_graph`; never
  in `owned_ends`). PD-19's `derive_aggregates` also takes `drawn_toolkit` and `class_names`: its
  six listed inputs cannot tell a drawn toolkit class from a not-generated one, nor name a class
  that is not an element. Rejected: `UmlPartOf.link_id` (a part row is per class pair, not per
  connector).
- **D-10**, lead, 2026-11-28 (delivery, task 1.7): PD-10 narrowed. A pointer's target counts as a
  part only when it is in `UmlAggregates.reached_from` (a concrete part, or an abstract part whose
  descendants the tree walks). An abstract class that is no part itself, but whose concrete
  descendants are all parts of other aggregates, is not refused. `check_pointers` keeps PD-19's
  signature, with no `parent_of`. Rejected: a `parent_of` input for that rarer case (a signature
  and model change for a shape no test or consumer draws).
- **D-11**, lead, 2026-11-28 (delivery, task 1.11): the redrawn library runs `rp-generate`'s lint
  and boundary steps, not every step. Its enumeration value `poetry` has no note on purpose (the
  no-note tests need it), so the hard check refuses it. The shelf-count model runs every step.
  1.11's accept line is reworded so. Rejected: a note on `poetry`, which changes a fixture other
  tests rely on.
- **D-12**, lead, 2026-11-28 (delivery, stage 1 PR): `develop` is merged into the branch, not rebased
  under it. `dependent-aggregates` stage 1 had changed the same metamodel, so every one of the
  branch's commits conflicted on generated manifests. One merge resolves them once: the generated
  files are regenerated from the merged sources. P-0002's aim, conflicts surfaced before review,
  holds. Rejected: replaying eight commits through the same generated conflicts.
- **D-13**, lead, 2026-11-28 (stage 1 review, PR #448, one L2+L3 pass, no Critical): all seven
  findings are under the floor.
  - W1: a generalisation with both ends inside an own graph is reported twice
    (`aggregates.refuse_inside_generalisations`); a follow-up for stage 2's conventions work.
  - W2: the two-roots boundary row is deferred to task 2.4 (A-23); C-9 replaces the old
    owned-on-one-class row.
  - W3: the 8 skips are `test_uml_pass_signatures.py`'s checks of `convention_lines` and
    `missing_notes`, which stage 2 writes.
  - W4: `MODULE_KIND`/`DOMAIN` re-declared in `aggregates.py` (use the generated enums in stage 2).
  - S5: split `_Pass` before stage 2 adds passes.
  - S6: cache `part_ids` and the ancestors.
  - S7: a test pinning `_adopt`'s order.
- **D-14**, lead, 2026-11-28 (stage 2, tasks 2.1–2.4):
  - `UmlComposition` gains `note`, so `composition-named` covers a note as well as a role.
  - `convention_lines` takes `drawn_toolkit` beside PD-19's inputs, as `derive_aggregates` does.
  - `CONVENTION_KINDS` lives in `uml/conventions.py`, and `cli.py` imports it.
  - D-13's W1 (the doubled problem) and W4 (re-declared constants) are fixed in passing.
  - `t_diagramlinks`' columns were checked against an EA-saved file's schema.
- **D-15**, lead, 2026-11-28 (stage 2 review, PR #449, no Critical):
  - W1 re-labelled Critical (the spec disagreed with the code). Under `--check` a converter problem
    stops the check as it stops a run, so the convention lines are printed only when there is no
    problem. The spec delta now says so, and a fixer pins it with a test. Rejected: printing both,
    which would report conventions of a model that cannot convert.
- **D-16**, lead, 2026-11-28 (stage 3): a cold reader of the guide found contradictions, all
  fixed:
  - the redraw steps against D-15 (problems come alone; the baseline comes from the previous
    release);
  - the deletion-test direction and its Reader example;
  - two disagreeing "What fails" rows;
  - undefined terms ("loaded graph", an internal change id).

  P-0040 is reworded through the rulebook to the right direction ("let W hold a pointer to the
  root of X's aggregate"). The fix pass touched docs and one rule note only. It is verified by
  `make check-docs` and the rule lint; the stage's full gates, run on the same code, are not
  repeated. The guide's Mermaid snippets stand in for the PlantUML that task 3.1 named, because
  the page already uses Mermaid.
  - Under the floor: W2, the seeds of rows the reviewer did not read; S3, the `NO_NOTE` alias kept
    for the one-occurrence acceptance; S4, the Statechart filter in both reader and pass; S5, a
    misplaced comment; S6, lookup by label in `_tenant_pointer_lines`.

