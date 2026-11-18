# Docs owed: generator-package

Docs are owed: the EPIC changes the architecture (a second top-level package), the installation
and upgrade path (the freshness plugin line, regenerate once) and the developer checks (a third
test lane). Task 2.5 updated the pages the PLAN names; the stage 2 review (D-19) found more.
The docs stage after stage 4 covers these, plus whatever stages 3 and 4 add.

| Page | What is owed | From |
|---|---|---|
| `howto/adopt.adoc` (~412) | The one `rdf-persistence` wheel ships the generator; the freshness plugin needs no `generate` extra (only `rp-generate` does) | D-19 W3 |
| `AGENTS.md:45`, `CONTRIBUTING.md:46` | The layout: `rdf_persistence_generation` is a sibling package the library never imports (`library-never-imports-the-generator`) | D-19 W4 |
| `develop/index.adoc` commands table (~60–66) | `make test` runs three lanes; a `make test-generator` row; `make refresh-map` re-keys moved tests (`BASE=`) | D-19 W5, D-17 |
| `architecture/index.adoc:209`, `questions.adoc:216` | The freshness plugin lives in `rdf_persistence_generation.testkit.freshness` | D-19 W6 |
| `architecture/generation.adoc`, `develop/testing.adoc` | Stage 3: `python_package` / `public_package` (F-4); stage 4: the generator's feature, integration and e2e tiers, Node in the lane | tasks 3.1, 4.4 |
