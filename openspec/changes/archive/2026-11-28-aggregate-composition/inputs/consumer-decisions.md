<!-- Secondary input, never groomed: the consumer's decisions S8-14..S8-17 (its ui-model-review.md, commit 7a51e99), quoted 2026-11-28. Consumer terms appear here only, never in the package, tests or architecture pages. -->

**Aggregates and modelling conventions (decided 2026-11-28, after round 27; filed as
meaningfy-ws/rdf-persistence#437, with #435):**

- **S8-14 Validation results.** All machine-made results (coverage, SPARQL, SHACL) are loaded graphs
  of the test data run, each its own named graph, written when it is ready and deleted with the run;
  the test data run keeps a small typed summary. A SHACL report and its results stay one graph.
- **S8-15 Composition, not boundaries.** The deletion test decides an aggregate (one named graph, one
  version token, one atomic write, one API resource). A UML composition, drawn beside the association
  that carries the property, means "stored together, consistent at every moment"; compositions form a
  tree; a composition stereotyped **«own graph»** makes a part separately stored but deleted with its
  whole. Pointers target roots only. Boundaries become annotations; until the converter ships this,
  a layout change keeps every class inside its boundary.
- **S8-16 Roots derived.** «root» is dropped; a concrete domain class that is no one's part is a root;
  «tenant root» stays. Diagrams: `<module> · aggregates` (classes and compositions only) beside
  `<module>` (associations only).
- **S8-17 One home for the conventions.** The modelling conventions and MWB2's modelling rules (P-0007,
  P-0008, P-0009, P-0011..P-0014, P-0016, P-0017, P-0026, P-0027) and the conventions check move to
  rdf-persistence (its guide and rulebook); MWB2 retires its copies once they are there. Aggregate,
  transaction and query are defined there: the model decides aggregates, use cases decide
  transactions, screens decide queries; transactions are never drawn.
