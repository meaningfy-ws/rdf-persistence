EPIC: aggregate-composition (proposal.md, issues #437 and #435, three items of #343). Decisions: design.md PD-1 to PD-20 (with PD-6a, PD-19a), DEC-1 to DEC-13 (DEC-4 re-shaped); attack rows A-1..A-26.

> Derives from: EPIC `aggregate-composition`. LARGE: three stages, one pull request each.

Every task: the failing test first, in the tier named; narrow checks `uv run pytest <file>` and
`make lint`; task gate `make test-changed check-quality`; commit body
`Refs: aggregate-composition <task> <PD>`. Builders never commit and never run `make generate` or
`uv sync`: a task that changes `rp_generation.yaml` or `rp_core.yaml` stops after the YAML, the
lead runs `make generate` and `make check-generated`, and the builder continues. Unit and feature
tests of `tests/generator/` run in `make test-generator`; its integration tests in
`make test-containers` (lead). Fixtures use the `lib:` library domain only (principle 3). The
moved and rewritten tests are listed in design.md "Tests that move or change"; none loses an
assertion without a replacement row. Every decision a task cites links its anchor in design.md
(`design.md#pd-n`, `#d-n`, `#risk-n`).

## 1. Stage 1: compositions, derived roots, own graph, pointers, Realisation

- [x] 1.0 Lead ([RISK-9](design.md#risk-9), [D-4](design.md#d-4), [D-5](design.md#d-5)); does not
  gate any task. Read Sparx EA's documentation of `t_connector` (`SourceIsAggregate`,
  `DestIsAggregate` on an Aggregation) and record it, with the columns already observed (an EA
  file with no Aggregation; composite associations `SourceIsAggregate=2`, `DestIsAggregate=0`,
  `SubType` empty), in `evidence/ea-connectors.md`. Read-only, `sqlite` `mode=ro`, column values
  only, never model content. Accept: the record exists and either agrees with
  [PD-1](design.md#pd-1)'s columns or names the difference for the lead. The developer's EA probe is
  not here: it is the `@manual` scenario of task 1.12.
- [x] 1.1 Lead: `openspec validate aggregate-composition --strict`; the MODIFIED requirements of
  [`specs/rp-uml-import/spec.md`](specs/rp-uml-import/spec.md) copy the living text and scenarios
  and change only the composition, boundary and Realisation sentences. Developer signs off
  `features/*.feature`. Accept: validate passes; a diff against `openspec/specs/rp-uml-import/spec.md`
  shows only those.
- [x] 1.2 Unit, generation model, additive only ([PD-1](design.md#pd-1), [PD-11](design.md#pd-11),
  [PD-12](design.md#pd-12), [PD-13](design.md#pd-13), [PD-19](design.md#pd-19)). First,
  failing: `tests/generator/unit/test_uml_records.py` rows building `UmlComposition`,
  `UmlDiagram`, `UmlAggregates` (`UmlPartOf` per (part, whole), `UmlReach` with `top_ids`,
  `UmlOwnedEnd`), `UmlObject.realised_ids`, `UmlElement.is_drawn_root`, the new `ReportKind`
  values. Nothing is removed here (`UmlBoundary.member_ids` goes in 1.6, A-11). Then
  `rp_generation.yaml`; the lead regenerates. Accept: rows pass; `make check-generated`; the task
  gate green.
- [x] 1.3 Unit, metamodel annotation ([PD-9](design.md#pd-9), [D-2](design.md#d-2), A-22),
  parallel to 1.2. First, failing: a row in `tests/unit/schema/test_schema_structure.py` that
  `RpAnnotation.RP_LOADED_GRAPH` exists with its description; a row in
  `tests/generator/unit/test_hard_check.py` that `rp_loaded_graph: maybe` on a slot is refused and
  `true` accepted. Then `rp_core.yaml` (the lead regenerates) and `ALLOWED_ANNOTATIONS`. Accept:
  pass; `make check-generated`; no file of `rdf_persistence/` other than the YAML and the generated
  ones changes.
- [x] 1.4 Unit, reader of compositions ([PD-1](design.md#pd-1), [D-5](design.md#d-5), A-9),
  after 1.2. File `tests/generator/unit/test_uml_qea.py`. First, failing:
  `test_a_composition_reads_its_whole_from_the_diamond_end` (parametrised over PD-1's two
  drawings, `SubType` NULL; each gives one `UmlComposition` with the same `whole_id`, `part_id`);
  `test_subtype_is_not_read` (`Strong`, `Weak`, NULL give the same record); refused rows: shared
  (`1`), no end marked, both marked, an aggregate value other than 0/1/2;
  `test_own_graph_is_read_from_the_stereotype`; `test_a_composition_end_outside_the_subtree_is_listed`
  (in `uml_outside_classes`). Then `qea.py` and `QeaBuilder.aggregation(...)`. Until 1.6 wires the
  tree, `convert` refuses every composition with a `no_rule` problem "composition: not converted
  yet", so no task between leaves an Aggregation converting silently; a row pins it and 1.6
  deletes both. Geometry is untouched here. Accept: all pass; the task gate green.
- [x] 1.5 Unit, the tree and the roots as a pure pass ([PD-2](design.md#pd-2),
  [PD-4](design.md#pd-4), [PD-5](design.md#pd-5), [PD-6](design.md#pd-6), [PD-8](design.md#pd-8),
  [PD-19](design.md#pd-19), [PD-19a](design.md#pd-19a), [D-6](design.md#d-6); worked example 3 of
  design.md is one row), after 1.2; not wired yet, so the gate is green alone. New
  `tests/generator/unit/test_uml_aggregates.py`, calling `derive_aggregates` and `package_kinds`
  with hand-built records and no `Context`: depth 3; part-ness inherited from an abstract and from
  a concrete part (A-16); abstract whole with two concrete roots, the part reached from both (A-4);
  recursive `Section ◆ Section` under `Book` accepted (A-1); one part class under two wholes of
  one top and of two tops, accepted (A-2); a cycle no top enters and an unreachable part class
  refused, naming the classes; the "what is not a root" outline; `package_kinds` from tags (A-5);
  DEC-6 both disagreements, the abstract «root» (A-12), a «root» in an access package kept as today,
  the agreeing `deprecated-root`; `root` lines with inherited and recursive parts; «own graph» to a
  not-generated part, to a generated part (names `dependent-aggregates`), plain composition to a
  not-generated part; a not-generated part under a not-generated whole accepted, nested «own graph»
  inside an own graph accepted (A-8); left-inside classes with a generalisation to one refused
  (A-7); ends outside, excluded, toolkit, enumeration, «tenant root» as part (A-9); a domain whole
  with a part in a technical package (A-25); PD-2: none, two with and without a role on the
  composition, a role naming no candidate, an association to the part's subclass (A-3, A-17). New
  `tests/generator/unit/test_uml_pass_signatures.py` (PD-19a). Then `uml/aggregates.py`. Accept:
  all pass; the task gate green.
- [x] 1.6 Unit, the tree replaces boundaries, one task ([PD-3](design.md#pd-3),
  [PD-5](design.md#pd-5), [PD-7](design.md#pd-7), [PD-17](design.md#pd-17),
  [PD-18](design.md#pd-18), [PD-19](design.md#pd-19), [RISK-5](design.md#risk-5), A-11),
  after 1.4 and 1.5. The lead may give it to two builders by file, with one task gate at the end.
  First, failing: in `tests/generator/unit/test_uml_rules.py` the R-11 rows rewritten (composition
  owns, a single part inlined, the composite association refused naming the two-connector form,
  the tenant root's composition part owned, an «own graph» slot with `rp_loaded_graph`); in
  `test_uml_qea.py` `test_the_reader_reads_no_geometry` and the membership-only boundary row
  (name, package). Then, together: `convert.py` (`_build` order of design.md "Algorithm", the
  1.4 stopgap deleted), `links.py` (`owned_ends` replaces `owned_pairs`; `_boundary_pairs`
  deleted), `qea.py` (`_Boundaries` and the geometry deleted), `UmlBoundary.member_ids` removed
  (the lead regenerates), `classes.py` (`is_drawn_root`; `_check_root_paths` after derivation),
  `convert._classes` (a part is a tree member); `QeaBuilder.boundary(..., package=, name=)` (A-24).
  In the same task, so the gate is green: the TC-2 geometry block and
  `test_uml_boundaries.py`'s two-roots test deleted (their replacement is 2.4's row, A-23); the
  RISK-5 sweep of `test_uml_rules.py` and the other `test_uml_*.py` rows whose plain concrete
  classes now derive as roots (intent stated, no assertion loosened); `uml_library.py` and
  `uml_library_stage2.py` redrawn with a composition beside each owned association, with the
  columns [PD-1](design.md#pd-1) states, keeping «root» and a boundary in a converted package
  named for its root; the goldens refreshed by the lead (`RP_REFRESH_GOLDEN=1`). Accept: the schema
  goldens byte-identical; the report golden diff shows only `root` and `deprecated-root` lines
  (no `boundary-disagrees`: the fixture boundary names its root); `ast-grep` finds no
  `RectTop`/`RectLeft` in `rdf_persistence_generation/`; `make test-generator` green.
- [x] 1.7 Unit, pointers ([PD-10](design.md#pd-10), [PD-19](design.md#pd-19), C-9, A-13, A-26),
  after 1.6. `test_uml_aggregates.py`, calling `aggregates.check_pointers(usages, toolkit_usages,
  aggregates, elements)` with records and no `Context`; then wired in `convert.py`. Rows: into another aggregate's part (problem names slot, part, roots); to a
  root, the tenant root, an abstract all-root class, a part of an aggregate the holder shares
  (accepted); to an access, a technical and a value class and an abstract class mixing roots and
  parts (accepted as today); a role owned on one whole and a pointer elsewhere (refused); the same
  with `dct:hasPart` kept as a `ReferenceCollection`'s toolkit slot (accepted).
  `_owned_on_one_class` in `test_uml_rules.py` becomes the C-9 refusal. Accept: all pass.
- [x] 1.8 Unit, Realisation, reader and roles together ([PD-11](design.md#pd-11), A-20), after
  1.2.
  `test_uml_qea.py`: `test_a_realisation_from_an_object_is_read_as_realised` (either drawing
  direction); class → class stays a problem; an excluded Object is skipped with a line; a target
  outside the subtree is kept. `tests/generator/unit/test_uml_roles.py`: agreeing (roles file
  unchanged), no classifier (target taken, also outside the subtree), disagreeing and two-target
  (problem `role_definition` naming both classes); an Object of a domain class still refused. Then
  `qea.py` (`QeaBuilder.realisation(...)`) and `roles.py`. Accept: all pass.
- [x] 1.9 Unit, the byte-identity claim ([PD-6a](design.md#pd-6a), [RISK-4](design.md#risk-4),
  [RISK-10](design.md#risk-10)), after 1.6. `test_uml_golden.py`
  `test_a_model_drawn_both_ways_converts_the_same` (the stage-1 model with «root» and a boundary,
  and with neither, give identical schemas) and
  `test_a_boundary_model_outside_the_precondition_changes_output` (a boundary that owned a
  part → part reference: after the redraw the slot is a plain reference, as PD-6a says). Accept:
  both pass.
- [x] 1.10 Feature, after 1.6–1.8: the scenarios (all but `@manual`) of
  [`features/composition.feature`](features/composition.feature),
  [`derived_roots.feature`](features/derived_roots.feature),
  [`own_graph_and_pointers.feature`](features/own_graph_and_pointers.feature) and the Realisation
  outline of [`conventions_check.feature`](features/conventions_check.feature) (spec:
  [requirements of rp-uml-import](specs/rp-uml-import/spec.md)), appended verbatim to
  `tests/generator/feature/uml_import.feature`;
  the existing "A package with a root and a part" rewritten to its MODIFIED form; steps in
  `test_uml_import.py`. Accept: all pass in `make test-generator`.
- [x] 1.11 Integration, after 1.9: `tests/generator/integration/test_uml_generate.py` converts the
  redrawn library and the shelf-count model of design.md example 2 and runs `rp-generate` on each.
  Lead runs `make test-containers`. Accept ([D-11](design.md#d-11)): the library passes lint and
  boundary; the shelf count generates with every step and has the `rp_loaded_graph` slots as
  `uri`.
- [x] 1.12 Lead: `make check-all`, `make test-containers`, `make check-generated`; review (two
  grouped runs, LARGE); PR into `develop`; a comment on #343 naming the three items done and the
  rest open; the consumer told the change id (D-12). No release is cut before stage 3 merges
  ([PD-17](design.md#pd-17), A-23). Before any release (stage 1 merged or later): the developer runs
  the `@manual` scenario "An EA-drawn composition reads the same either way" of
  [`features/composition.feature`](features/composition.feature) ([RISK-9](design.md#risk-9),
  [D-4](design.md#d-4)); the lead records EA's columns in `evidence/ea-connectors.md`. Accept: both
  drawings give the same schemas and the shared one is refused; if EA writes other columns than
  [PD-1](design.md#pd-1) states, PD-1 and `QeaBuilder.aggregation` are corrected before the release.

## 2. Stage 2: the conventions check and diagrams

- [x] 2.1 Unit, CLI ([PD-14](design.md#pd-14), [PD-13](design.md#pd-13)). `tests/generator/unit/test_uml_cli.py`: `--check` on a model with a
  problem exits 1 and leaves a filled `--out` byte-identical (no report rewritten); with only a
  convention line exits 1 and prints it to stdout in report format; clean exits 0, prints nothing,
  needs no `--out`; a run without `--check` and without `--out` exits 2; a normal run with a
  convention line exits 0 and writes; a reader problem short-circuits and is the only output
  (A-21); a model with only an agreeing «root» (`deprecated-root`) exits 0. Then `cli.py`. Accept: all pass.
- [x] 2.2 Unit, diagrams ([PD-12](design.md#pd-12), [RISK-6](design.md#risk-6)), after 2.1. `test_uml_qea.py`: `UmlDiagram` membership from
  `t_diagramobjects` and `t_diagramlinks` (a connector is shown when both ends are members, hidden
  when a row says so, shown when no row exists); `QeaBuilder.diagram_link(...)` with
  `t_diagramlinks`'s real EA columns in `EA_COLUMNS`. New
  `tests/generator/unit/test_uml_conventions.py`: `aggregates-diagram` (association shown, enum
  shown, a diagram ending ` · aggregates` whose prefix is not its package; a diagram without the
  suffix is never read as one), none for a NoteLink, a generalisation or a boundary
  on an aggregates diagram (A-18), `composition-diagram`, Statechart ignored. Then
  `qea.py` and `uml/conventions.py`. Accept: all pass.
- [x] 2.3 Unit, one home for "no note" ([PD-20](design.md#pd-20), [PD-19](design.md#pd-19)),
  parallel to 2.2.
  `tests/generator/unit/test_uml_no_note_coverage.py` passes unchanged before and after; new rows
  in `test_uml_conventions.py` call `missing_notes` with records and no `Context`, and pin today's
  text for a noteless class, enumeration literal, attribute, role, and an attribute that becomes a
  toolkit slot (A-19), each written before the move and passing on today's code. Then move the
  three writes (`classes._described`, the literal line, `slots.described`) into `conventions.py`. Accept: `ast-grep` finds `ReportKind.NO_NOTE` once in
  `rdf_persistence_generation/uml/`; the stage-2 golden report's `no-note` lines unchanged.
- [x] 2.4 Unit, the ported conventions ([PD-13](design.md#pd-13), [PD-15](design.md#pd-15),
  [D-1](design.md#d-1), [D-3](design.md#d-3), C-1..C-12), after 2.2. In
  `test_uml_conventions.py`, one row per finding of design.md's classification:
  `unprefixed-name`, `unused-enumeration`, `drawn-toolkit-parent` (and none for a drawn
  `rp:RoleDefinition` that classifies Objects), `tenant-required-pointer`, `boundary-disagrees`,
  `composition-named`; the `boundary-disagrees` row replaces the deleted two-roots test (A-23); a
  test that `CONVENTION_KINDS` equals exactly the eleven of PD-13 (`boundary_disagrees`,
  `composition_named`, `aggregates_diagram`, `composition_diagram`, `unprefixed_name`,
  `unused_enumeration`, `drawn_toolkit_parent`, `tenant_required_pointer`, `no_note`,
  `unspecified_multiplicity`, `implicit_meaning`; `deprecated_root` and `toolkit_slot_kept` not
  among them); and `test_the_reference_collection_pattern_passes_the_check`: the conventions page's
  abstract collection whose role stays `has_part` (`toolkit-slot-kept`) gives no convention line
  (A-14). Accept: all pass.
- [x] 2.5 Unit, each C-x fails the check (Q9), after 2.4. `test_uml_cli.py`
  `test_each_convention_fails_the_check`, parametrised over the eleven rows of the outline
  "each convention fails the check" in [the spec](specs/rp-uml-import/spec.md) and
  [`conventions_check.feature`](features/conventions_check.feature), on
  a clean `.qea` seeded once per row. Accept: each row exits 1 naming its element; the clean
  model exits 0.
- [x] 2.6 Feature, after 2.5: the remaining scenarios of
  [`features/conventions_check.feature`](features/conventions_check.feature)
  appended verbatim to `uml_import.feature`, steps in `test_uml_import.py`. Accept: pass.
- [x] 2.7 Lead: `make check-all`; review; PR.

## 3. Stage 3: guide, conventions page, rules, changelog

- [x] 3.1 Docs, conventions page ([PD-16](design.md#pd-16), P-0014): `reference/uml-conventions.adoc`: "A root"
  rewritten (derived roots, «root» deprecated), `[#boundary]` → `[#composition]` (composition
  beside its association, the diamond end, depth, abstract parts), "«own graph»", "Pointers target
  roots", "Realising an object's class", "Diagrams" (aggregates and association diagrams), each
  with a PlantUML snippet and the LinkML it becomes; "What fails" table updated from design.md's
  error matrix; the conventions list (one row per convention kind, problem or line). Accept:
  `make check-docs`; no boundary-geometry sentence left; no consumer term.
- [x] 3.2 Docs, guide ([PD-16](design.md#pd-16), [PD-6a](design.md#pd-6a),
  [PD-14](design.md#pd-14), DEC-12): `howto/uml-to-linkml.adoc`: a section "Aggregates,
  transactions and queries" (the three terms; "the model decides aggregates, use cases decide
  transactions, screens decide queries"; transactions and queries are never drawn), "The deletion
  test", "Two kinds of diagram" (hide the associations on the aggregates diagram and the
  compositions on the others; EA shows every connector whose ends are present), step "Check the
  model" (`rp-uml2linkml --check` in CI; it does not run the whole-model check; reader problems
  come alone first), "Redrawing a boundary model" (PD-6a's precondition; diff the schemas), report
  lines `root`, `deprecated-root`, `boundary-disagrees`; links
  to the rules (3.4) and to the conventions page; `read_qea` named as the public reader for a
  model's own checks. Accept: `make check-docs`.
- [x] 3.3 Docs, `questions.adoc`: "Which classes are aggregate roots?", "How do I draw a part?",
  "How do I check a UML model in CI?", "Where are the modelling rules?", each linking its section.
  Accept: `make check-docs`.
- [x] 3.4 Rules (DEC-12), via the rulebook script by the lead (`rules.py`, scope
  `activity:modelling`, `private: false`, source quoting the consumer note it comes from). Content:

  | New id | From | Type, strength | When | Do | Because |
  |---|---|---|---|---|---|
  | P-0025 | consumer P-0007 | preference, default | asked to make a model more elegant | propose fewer concepts and links that still satisfy every requirement | a smaller crisp model, never at a requirement's cost |
  | P-0026 | consumer P-0008 | preference, default | a class links to a controlled list in UML | draw a dependency from the class to the enumeration, named by the property | the SEMIC style guide connects classes to controlled lists this way |
  | P-0027 | consumer P-0009 | constraint, default | deciding where an application stores content | store what is or can be RDF in the triple store as data; only non-RDF content as files | results and models stay queryable |
  | P-0028 | consumer P-0011 | constraint, default | drawing a model the toolkit converts | draw the domain classes; bring toolkit classes in by defaults and tagged values | the model focuses on the domain |
  | P-0029 | consumer P-0012 | constraint, hard | modelling | state each fact once: no association repeating another in reverse, no attribute repeating a toolkit slot | consistent, non-redundant |
  | P-0030 | consumer P-0013 | constraint, hard | a model is turned into LinkML | show the diagrams generated from the LinkML for inspection and in the docs | what is inspected is what is generated |
  | P-0031 | consumer P-0014 | constraint, hard | the model changes | adjust the architecture docs (model page, glossary, decisions) in the same change | the docs follow the model |
  | P-0032 | consumer P-0016 | preference, default | modelling access and workflows | draw them in UML on the toolkit's concepts (subclass, instances, state machine), never only hand-written LinkML | one source for the whole model |
  | P-0033 | consumer P-0017 | preference, default | organising a UML model | small thematic packages, one per converted module, re-shuffled when one mixes themes | maintenance |
  | P-0034 | consumer P-0026 | constraint, hard | modelling with an external vocabulary's terms | check each term and its namespace against the published specification first | mixed vocabulary versions go unnoticed |
  | P-0035 | consumer P-0027 | constraint, hard | a change to the `.qea` is planned | start from the latest `.qea` on any open branch; one branch changes it at a time | the file is binary and cannot be merged |
  | P-0036 | consumer developer guide | constraint, hard | a model artefact is needed | generate it from the UML model; never edit a generated file (CI regenerates and compares) | the model is the one source |
  | P-0037 | consumer developer guide | preference, default | the model changes | let a test break; if none does, add one | an untested model change goes unnoticed |
  | P-0038 | consumer developer guide | constraint, hard | the converter or generator produces the wrong thing | fix it in rdf-persistence, never patch it in the application | one fix serves every consumer |
  | P-0039 | consumer developer guide | constraint, default | converting a `.qea` | close or reload EA first | EA holds unsaved state |
  | P-0040 | #437 B, consumer S8-15 | constraint, hard | deciding whether X is a part of W | draw a composition only when X cannot exist without W and goes down with it; else a pointer to W's root | the deletion test decides an aggregate |

  Not adopted: the consumer's P-0010, P-0018, C-13; its "no hand-written models" is this
  repository's P-0007. The guide links the notes. Accept: `rules.py` validates the store; the ids
  follow P-0024 (re-checked at the time: the next free id is used if others landed).
- [x] 3.5 Changelog: `CHANGELOG.md` **BREAKING** entry with design.md's migration steps. Accept:
  the entry names `--check`, the composite-association refusal, derived roots and the steps.
- [x] 3.6 Lead: `make check-docs`, `make check-all`; review (docs lens); PR; the consumer told it
  can retire its copies (RISK-3).

## Roadmap

- [x] 1.0 · [x] 1.1 · [x] 1.2 · [x] 1.3 · [x] 1.4 · [x] 1.5 · [x] 1.8 · [x] 1.6 · [x] 1.7 ·
  [x] 1.9 · [x] 1.10 · [x] 1.11 · [x] 1.12 · [x] 2.1 · [x] 2.2 · [x] 2.3 · [x] 2.4 · [x] 2.5 ·
  [x] 2.6 · [x] 2.7 · [x] 3.1 · [x] 3.2 · [x] 3.3 · [x] 3.4 · [x] 3.5 · [x] 3.6
  (1.0 is the lead's reading of Sparx's docs and gates nothing ([D-4](design.md#d-4)); the
  developer's EA probe is the `@manual` scenario run in 1.12 before any release; 1.2 and 1.3 in
  parallel; 1.5 and 1.8 need only 1.2;
  1.6 needs 1.4 and 1.5; 2.3 in parallel with 2.2; stage 3's docs tasks in parallel. Every task
  passes its own task gate: nothing is removed before its last reader goes, A-11.)

## Verification

Per stage `make check-all`, stage 1 also `make test-containers` and `make check-generated`;
`openspec validate aggregate-composition --strict`; the clarity gate logged in
`evidence/clarity-gate.md`; every spec scenario shown in `evidence/acceptance.md`.
