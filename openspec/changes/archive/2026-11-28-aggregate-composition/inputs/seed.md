<!-- Secondary input, never groomed: GitHub issue #437 (meaningfy-ws/rdf-persistence), fetched 2026-11-28, state OPEN. The EPIC (../proposal.md) supersedes it. -->

# #437 Modelling conventions: composition, derived roots, «own graph» parts; adopt MWB2's modelling rules and conventions check

## Summary

Make rdf-persistence the **one home of the modelling conventions** for a UML (EA) model that `rp-uml2linkml` converts: the aggregate conventions decided in MWB2's model review of 2026-11-27/28 (composition instead of boundary geometry, derived roots, «own graph» parts), plus every modelling rule MWB2 holds today, so MWB2 can retire its copies. Three parts: (A) converter changes, (B) the conventions and the modelling rules adopted into rdf-persistence's guide and rulebook, (C) the conventions check moved here.

## Context

Consumer: MWB2 (rdf-persistence v0.15.0), EA round 27 (MWB2 PR #155), decisions S8-14..S8-17 of `openspec/changes/domain-model-v2/analysis/draft-7/ui-model-review.md` (MWB2, branch `docs/domain-model-ui-refresh`).

The converter learns which classes are owned parts from **boundary geometry**: a boundary enclosing one «root» makes every association between its enclosed members owned (`uml/links.py` `_boundary_pairs`). One layout pass in EA silently:
- narrowed `Aggregate: mwb:ValidationRun`, so `prov:Usage` stopped being a part (`owned`/`inlined_as_list` dropped from the generated slot);
- moved `Aggregate: mwb:ConceptualMappingCollection` off its class (an empty boundary).

Of MWB2's 27 boundaries, 23 enclose one class and only restate «root». Depth (part of a part) cannot be drawn. And any connector other than Association, Dependency and Generalization is a `no_rule` problem (`uml/qea.py` `LINK_KINDS`), so composition cannot be drawn at all today.

## A. Converter

1. **Composition = stored together, consistent at every moment.** A UML composition (EA: Aggregation, strong) from a whole to a part: the part is in the whole's named graph, under its version token, written in the same atomic write, deleted with it. Compositions nest (`TriplesMap ◆ PredicateObjectMap ◆ ObjectMap ◆ LanguageMap`). Unnamed: the association beside it carries the property (role, multiplicity, note) and still becomes the slot; the composition marks that slot owned/inlined.
2. **A composition needs its association.** Every composition is drawn beside an association in the same direction (whole → part); a composition without one is a problem.
3. **Compositions form a tree:** no cycle, a part has exactly one whole, every part is reachable from exactly one root. A violation is a problem.
4. **Roots are derived; «root» is dropped.** A concrete domain class that is no composition's part, not of a `--not-generated` stereotype and not a drawn toolkit class is an aggregate root. «tenant root» stays explicit (not derivable). The conversion report lists every derived root with its parts (so a class that became a root by omission is visible). During a transition «root» may be accepted and checked for agreement.
5. **«own graph» composition.** A composition stereotyped «own graph» makes the part a separately stored part of its whole: its own named graph and version token, written on its own (later, by whoever produces it), but it cannot exist without its whole and is **deleted with it**. The part may be a generated class or a class of a `--not-generated` stereotype (MWB2's «loaded graph»: raw RDF registered to the root, as `Session.load_graph` does today). Example (MWB2 validation):
   ```
   ValidationRun ◆«own graph»→ TestDataRun                (each worker writes its own)
   TestDataRun   ◆«own graph»→ CoverageReport «loaded graph»
   TestDataRun   ◆«own graph»→ SPARQLReport   «loaded graph»
   TestDataRun   ◆«own graph»→ sh:ValidationReport «loaded graph»
   sh:ValidationReport ◆→ sh:ValidationResult            (inline: one graph, as pySHACL writes it)
   ```
   Deleting the run deletes all of it; this replaces consumer-side cascades (MWB2's AG-6 exception).
6. **Pointers target roots only.** An association from outside an aggregate ranges over its root (or an abstract class whose concrete subclasses are roots), never over another aggregate's part (MWB2 check C-10 today).
7. **Boundaries are annotations.** Their geometry is no longer read. During the transition, a boundary that disagrees with the compositions is reported.
8. **Realisation from an Object to its classifier** is accepted: #435 (must-have for MWB2).

## B. Conventions and rules adopted here (guide `howto/uml-to-linkml.adoc` and the rulebook `docs/rules/`)

**Terms (glossary):** *aggregate* (what must stay consistent on every write: one named graph, one version token, one atomic write, one API resource with its parts inlined); *transaction* (one or several aggregates written together, `session.transaction()`); *query* (what is read together). **The model decides aggregates, use cases decide transactions, screens decide queries**; transactions and queries are never drawn in the class model, and a use case never widens an aggregate.

**The deletion test:** X is a part of W exactly when X cannot exist without W and goes down with it; anything else is a pointer, guarded by `rp_on_referenced_delete`.

**Diagrams:** aggregate diagrams `<module> · aggregates` show classes and compositions only; association diagrams `<module>` show associations only, no compositions.

**MWB2's modelling rules, to be adopted (each quoted from MWB2 `docs/rules/`, with its owner source):**

| MWB2 id | Strength | When / do | Because |
|---|---|---|---|
| P-0007 | default | asked for a more elegant model / propose fewer concepts and links that still satisfy every requirement | a smaller crisp model, never at the cost of a requirement |
| P-0008 | default | a class links to a controlled list (enumeration) / draw a dependency from the class to the enumeration, named by the property, not an attribute typed by it | the SEMIC style guide connects classes to controlled lists this way |
| P-0009 | default | deciding where content is stored / store anything that is or can be RDF in the triple store as data; keep only non-RDF content as files | results and models must be queryable as data |
| P-0011 | default | drawing the domain model in a UML source the toolkit converts / draw the domain classes only; bring the toolkit's classes in through the conversion (defaults, tagged values) | the model focuses on the domain; the toolkit integrates the rest |
| P-0012 | hard | modelling / state each fact once: no association repeating another in reverse, no attribute repeating a slot the toolkit gives | consistent and non-redundant |
| P-0013 | hard | a model is turned into LinkML / show the diagrams generated from the LinkML for inspection and in the documentation | what is inspected must be what is generated |
| P-0014 | hard | the model changes / adjust the architecture docs (model page, glossary, ADRs) in the same change | the docs follow the model |
| P-0016 | default | modelling access and workflows / draw them in EA on top of the toolkit's concepts (subclass, instances, state machine); never only hand-written LinkML or YAML | the whole model in one source that extends rdf-persistence |
| P-0017 | default | organising the EA model / small thematic packages, one per converted module, re-shuffled when a package mixes themes | maintenance |
| P-0026 | hard | modelling with terms of an external vocabulary / check every term and its namespace against the published specification first | MWB2's EA model mixed RML-Core and legacy RML names unnoticed |
| P-0027 | hard | a change to the EA model (`.qea`) is planned / start from the latest `.qea` on any open branch; one branch changes it at a time | the `.qea` is binary and cannot be merged |

Plus the rules in MWB2's developer guide (`develop/index.adoc`, "The model rules"), which hold for any consumer: the EA model is the source and everything is generated from it; generated files are never edited (CI regenerates and compares); no hand-written models; a changed model should break a test; a converter that produces the wrong thing is fixed in rdf-persistence, never patched in the consumer; close EA before converting.

Not adopted (MWB2-specific): P-0010 (autonomous decisions in MWB2 sessions), P-0018 (no schema migration while MWB2 has no production data), check C-13 (MWB2's v1 attributes).

## C. The conventions check moves here

MWB2's `tools/ea/qea_conventions.py` (read-only, stdlib, one Markdown row per convention, exit 1 on a failure) checks C-1..C-12: prefixed names; named, bounded roles; notes everywhere; abstract marking; enumerations used by a dependency; one module per package, acyclic imports; boundaries; no attribute duplicating a toolkit slot; a role IRI on one class kind only; pointers over roots; domain-only drawing; required pointers satisfiable at tenant creation. Move it into rdf-persistence beside the converter (as a command or a pre-conversion pass), extend it to A.1-A.7 and the diagram rule of B, and let consumers add their own checks (MWB2's C-13).

## Why it belongs in rdf-persistence

The converter owns which UML constructs a model may use and what they mean (#196); its guide is the only place the modelling conventions should live. A consumer cannot draw composition or «own graph» until the converter reads them, and keeping a second copy of the rules in each consumer lets them drift.

## Impact on the consumer

MWB2 keeps its boundaries (they carry meaning today) and its rules until this ships; then one model round draws `· aggregates` diagrams with compositions, drops «root», turns boundaries into annotations, moves validation results to «own graph» parts, and MWB2 retires P-0007..P-0017, P-0026, P-0027 and its conventions script in favour of rdf-persistence's.

