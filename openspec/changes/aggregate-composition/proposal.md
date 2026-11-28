<!-- Parents: GitHub issues #437 (inputs/seed.md) and #435 (inputs/seed-435.md); the living
     capability rp-uml-import; the consumer's decisions S8-14..S8-17 (inputs/consumer-decisions.md).
     Q&A: inputs/qa.md. Follow-up: the change dependent-aggregates. -->

# EPIC: Aggregates by composition, and one home for the modelling conventions

**Golden-thread parents:** issue #437 (aggregates drawn by composition; the modelling rules and the
conventions check adopted from the first consumer); issue #435 (a Realisation from an Object to
its classifier); `rp-uml-import` "A UML class model converts to toolkit-conformant LinkML" and "The
toolkit is reused, not redefined"; #196 (the converter owns which UML constructs a model may use).
**Serves:** the first consumer's decisions S8-14..S8-17 (D-12); it names this change id.

## Appetite

**LARGE.** Several related capabilities of the converter move together: how parts and roots are
read (composition replaces boundary geometry, roots are derived), what a model may draw («own
graph», Realisation), a check mode, and the modelling rules and conventions that move into this
repository's guide and rulebook from a consumer. One existing notation is refused (breaking).
Delivered in stages.

## Why

`rp-uml2linkml` learns which classes are owned parts from boundary geometry, so a layout pass in
EA can silently change what is stored together: a boundary that shrinks drops `owned` from a slot,
and a boundary that slides off its class owns nothing. Most boundaries only restate «root», depth
cannot be drawn, and EA's composition connector is refused outright. The rules a modeller must
follow live in the consumer (its rulebook and a model-specific script), so every new consumer would
copy them and the copies drift. The converter owns what UML means; its guide and check should be
the one place those conventions live.

## Solution outline

A model states its aggregates with **compositions** (EA Aggregation connectors, strong): a
composition from a whole to a part means "stored together, consistent at every moment". It is drawn
beside the association that carries the property (role, multiplicity, note), which still becomes
the slot; the composition makes that slot owned and inlined. Compositions form a tree, and the
**roots are derived**: a concrete domain class that is no composition's part, not of a
`--not-generated` stereotype and not a drawn toolkit class. «tenant root» stays explicit.
A composition stereotyped **«own graph»** makes its part separately stored but deleted with its
whole. In this change the part may only be of a `--not-generated` stereotype (a loaded graph,
which the library already registers to an aggregate and deletes with it). A generated part is
refused until `dependent-aggregates` ships. **Pointers target roots only.**
Boundaries become annotations, and their geometry is no longer read.

Every convention the consumer's script checks (its C-1..C-12), and the new ones, become converter
findings: a meaning convention is a problem, a presentation convention a report line. A new
`--check` mode reads the model, reports and writes nothing, and exits 1 on any finding, so CI can
gate a model before conversion. The terms (aggregate, transaction, query), the deletion test, the
two kinds of diagram and the conventions go into the UML guide with UML snippets. The consumer's
generic modelling rules become P- rules here. The consumer can then retire its copies.

## Key decisions

- **DEC-1**: two changes. This one is the converter, conventions, rules and check, with #435
  folded in. `dependent-aggregates` adds a generated «own graph» part at runtime and is delivered
  after this one. — Each is one coherent appetite; the runtime work touches the library, this one
  only the generator and docs. Rejected: one VERY LARGE change; #435 as its own TINY change (it
  touches the same connector table). (Q1)
- **DEC-2** *(amended 2026-11-28 by the lead after the clarity gate's G-5 and design D-5/D-6;
  logged in `inputs/qa.md`; the developer validates it)*: a composition is an EA connector of type
  Aggregation whose end column marks a composite (D-5; `SubType` is not read). The **diamond
  end** names the whole, never the drawing direction. Every composition has an association between
  the same two classes whose role on the part's end gives the slot. When several could, a role
  written on the composition names the one it marks owned. A composition with no candidate, or
  several and no role, is a problem. A shared aggregation is a problem. — The
  association keeps the property's role, multiplicity and note, and the aggregates diagram can
  show compositions alone. Rejected: reading the drawing direction (RISK-1). (Q8)
- **DEC-3**: the composite **association** (an association whose end is composite, read today by
  `_is_owned`) is **refused** with a problem that names the two-connector form. **BREAKING.**
  Rejected: accepting both forms; deprecating first. (Q3)
- **DEC-4** *(re-shaped 2026-11-28 by the lead, after the PLAN attack's A-1 and A-2; see
  `inputs/qa.md` "Re-shape"; the developer validates it)*: compositions form a tree **of
  instances**. Each part instance has exactly one whole, and every part is reached from a root.
  At class level a part class may have several whole classes (`GraphMap` under `SubjectMap` and
  under `PredicateObjectMap`), and a composition may recurse (`Section ◆ Section`); each instance
  still sits in one whole. A part class that no root reaches is a problem naming the classes. So
  is a class that is both a part and drawn «root», or a composition cycle that no root enters.
  Was: "a cycle, a part with two wholes, and a part that no root reaches are each a problem",
  which refuses legitimate recursive and shared part types, the first consumer's own model among
  them.
- **DEC-5**: roots are derived. A concrete class of a domain module that is no composition's part,
  not of a `--not-generated` stereotype, not a drawn toolkit class and not «tenant root» is an
  aggregate root, and the existing abstract-root rule still applies. The report lists every root
  with its parts (a `root` line), so a class that became a root by omission is visible. — A
  modeller states what is part of what; what remains is a root. Rejected: keeping «root» as the
  source.
- **DEC-6**: transition. When a model draws «root» at all, the drawn set must equal the derived
  set. Each class in one and not the other is a problem naming it, so a class that became a root
  by omission fails rather than slipping through. A model whose sets agree gets one
  `deprecated-root` report line. Boundary geometry is never read. A boundary whose members
  are not one root and its composition parts is a `boundary-disagrees` report line. A model drawn
  with «root» and boundaries whose meaning the compositions restate converts byte-identical. (Q5)
- **DEC-7**: «own graph» composition. Its part is stored separately, cannot exist without its
  whole and is deleted with it. In this change the part must be of a `--not-generated` stereotype:
  no slot type is generated for it, and the whole's slot ranges over `uri` with an annotation
  marking its values as the whole's loaded graphs. A generated part is a problem naming
  `dependent-aggregates`. A plain composition below an «own graph» part (a SHACL report and its
  results) stays inside the part's graph and is not converted when the part is not generated.
  (Q6)
- **DEC-8**: pointers target roots only. An association from outside an aggregate ranges over its
  root, or over an abstract class whose concrete subclasses are all roots, never over another
  aggregate's part (the consumer's C-10). A violation is a problem.
- **DEC-9**: #435. A Realisation from an Object to a class is accepted as the visible form of the
  Object's classifier and converts to nothing. A Realisation that names another class than the
  classifier is a problem. An Object with a Realisation and no classifier takes the target as its
  classifier.
- **DEC-10**: the check lives in the converter. Each convention is a finding. A convention that
  changes the generated LinkML when broken is a **meaning** convention and a problem (DEC-2..DEC-9,
  and those of the consumer's C-1..C-12 that are). Any other is a **presentation** convention and a
  report line in a conversion (notes, diagram contents, package themes). The design classifies each
  of C-1..C-12 by that test, and a C-x the converter already enforces stays as it is. Two are not
  ported: C-7 (boundaries), which DEC-6 replaces, and the "acyclic imports" half of C-6, because
  `rp-uml-import` supports packages that import each other. `rp-uml2linkml --check` runs the same reading, writes nothing and exits 1 on any
  problem or convention line, 0 otherwise. A consumer's own checks (its C-13) stay in the consumer;
  the qea reader they reuse is named in the guide as public. Rejected: a separate command; a
  mandatory pre-pass. (Q4, Q10)
- **DEC-11**: diagrams. A diagram named `<module> · aggregates` holds classes and compositions
  only; any other diagram of a converted package holds no composition. A breach is a convention
  line. Only diagram names and contents are read, never geometry.
- **DEC-12**: rules and conventions. The guide `howto/uml-to-linkml.adoc` gains the terms
  (aggregate, transaction, query, with "the model decides aggregates, use cases decide
  transactions, screens decide queries"), the deletion test, the two kinds of diagram and every
  convention, each with a UML snippet and the LinkML it becomes (P-0014). The consumer's generic
  rules (its P-0007, P-0008, P-0009, P-0011..P-0014, P-0016, P-0017, P-0026, P-0027 and the
  developer-guide model rules) become P- notes in `docs/rules/` through the rulebook, with new ids,
  scope `activity:modelling`, generic wording and the source quoted. The guide links the rules
  rather than restating them. Not adopted: the consumer's P-0010, P-0018 and C-13 (consumer
  specific). (Q7)
- **DEC-13**: three items of #343 (the converter's deferred restructure) are taken here because
  this change rewrites their code anyway.
  1. The boundary geometry leaves `qea.py` (DEC-6 stops reading it).
  2. The new passes (composition tree, root derivation, conventions) take their inputs as
     arguments and return their results, never filling `Context` in an order nothing enforces.
  3. The "no note" rule, written three times today, has one home in the conventions pass.

  The rest of #343 stays open. Rejected: all of #343, a restructure of its own beyond this
  appetite. (Developer, 2026-11-28.)

## Rabbit-holes

- **Diagram geometry.** Only diagram membership (which elements and connectors a diagram shows)
  is read. Never positions, sizes or overlaps.
- **Re-deriving `owned` beyond the tree.** Depth comes from the composition tree. No inference
  from multiplicities or names.
- **A generic plug-in API for consumer checks.** Out of scope. The consumer reuses the reader, and
  a hook waits for a second consumer that needs one.
- **Order.** This change ships before `dependent-aggregates`, which depends on DEC-7's annotation
  and refusal. The consumer redraws its model only after the release that carries this change
  (RISK-2).

## No-gos

- No runtime change in `rdf_persistence/`. A generated «own graph» part (a dependent aggregate)
  is `dependent-aggregates`.
- No migration tool that redraws a `.qea` (the converter reads it read-only, as today).
- No reading of boundary or diagram geometry.
- No consumer terms in the package, tests or architecture pages. The consumer's names appear only
  in `inputs/`.
- No porting of the consumer's C-13 or its P-0010 and P-0018.
- No transactions or queries drawn or converted. They stay use-case and screen decisions.

---

## What Changes

- The converter reads EA Aggregation (strong) connectors as compositions beside their associations;
  the slot is owned and inlined; nesting at any depth.
- **BREAKING**: a composite association end is refused; boundary geometry no longer makes slots
  owned; roots are derived (a «root» that disagrees is a problem).
- «own graph» composition to a `--not-generated` part; a generated part is refused.
- Pointers into another aggregate's part are refused.
- Realisation from an Object to its classifier is accepted (#435).
- `rp-uml2linkml --check`: every convention as a finding, nothing written, exit 1 on a finding.
- The conventions of the consumer's C-1..C-12 become converter findings.
- The guide gains terms, the deletion test, diagram kinds and conventions with snippets; the rulebook
  gains the adopted modelling rules (`activity:modelling`).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `rp-uml-import`: composition replaces boundaries; derived roots; «own graph»; pointers over
  roots; Realisation; `--check`; the convention findings.

## Impact

- Code: `rdf_persistence_generation/uml/` (`qea.py` connector kinds and diagram reading, `links.py`,
  `context.py`, `classes.py`, `cli.py`, a new module for the tree and the conventions), the
  generation model `rp_generation` (a new composition record, report kinds; corrected by the lead
  2026-11-28 from "new link kind", per PD-1), `tests/generator/`.
- Docs: `howto/uml-to-linkml.adoc`, `questions.adoc`, `docs/rules/` (new P- notes), the changelog
  migration note.
- Consumers: a model using composite associations or relying on boundaries must be redrawn; the
  release notes carry the steps. The first consumer then retires its P-0007..P-0017, P-0026, P-0027
  and its check script.
