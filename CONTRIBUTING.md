# Contributing to RDF Persistence

Thank you for contributing. This guide gives the workflow and the rules a change follows, and links
to the developer manual for the details:
[Working on the library](docs/modules/ROOT/pages/develop/index.adoc),
[Working on the generator](docs/modules/ROOT/pages/develop/generator.adoc) and the
[testing checklist](docs/modules/ROOT/pages/develop/testing.adoc). Set up your machine first with
[INSTALL.md](INSTALL.md).

## Workflow

1. Work is planned before it is coded, in the OpenSpec spine under `openspec/changes/<id>/`
   (the EPIC is `proposal.md`; the PLAN is `design.md` + `tasks.md`). Commits cite the change
   (`Refs: <change-id> <task>`).
2. Create a branch off `develop` following the naming convention (see
   [git workflow](#commits-and-pull-requests)).
3. Implement the change with tests (TDD/BDD — see [Testing](#testing-expectations)).
4. Run `make check-all` locally and ensure it is green (`make test-containers` too if you touched
   adapters or containers).
5. Open a pull request against `develop`.

Agents follow the same workflow with a fixed team of roles; see
[Working with agents](docs/modules/ROOT/pages/develop/agents.adoc).

## LinkML is the single source

Every model artefact (classes, enums, shapes, JSON-LD context and frames, TypeScript types, API and
JSON schemas, diagrams) is generated from the LinkML schemas. To change one, change the schema and
run `make generate`; never edit a file under a `generated/` folder. Where a stock generator falls
short, extend it in `rdf_persistence_generation/`, with its own test. Data goes through the
generated models, not bare dicts. See
[Working on the library](docs/modules/ROOT/pages/develop/index.adoc) and
[Working on the generator](docs/modules/ROOT/pages/develop/generator.adoc).

## Architecture constraints

Layers import downward only, `entrypoints | adapters → services → domain`; the ports live in
`services`, their implementations in `adapters`, and `adapters` and `entrypoints` never import each
other. The generator, `rdf_persistence_generation/`, is a sibling top-level package that the
library never imports. Consumers import only from
`rdf_persistence` (and `rdf_persistence.testkit` in tests). `make check-architecture` enforces this
with import-linter; the full layer map, with what each layer holds and exports, is in the
[architecture overview](docs/modules/ROOT/pages/architecture/index.adoc#public-api).

## Testing expectations

Write the tests first, in their tier (`unit`, `feature`, `integration`, `e2e`); the folder stamps
the marker, so add no per-file `pytestmark`. While you work, run `make test-changed`; before the PR,
`make check-all`. The [testing checklist](docs/modules/ROOT/pages/develop/testing.adoc) is what
every test follows, and [Make targets](docs/modules/ROOT/pages/develop/index.adoc#make-targets)
lists the lanes and their coverage floors.

## Commits and pull requests

Follow the Meaningfy git conventions — see the **`meaningfy-git-workflow`** skill for the
authoritative rules. In short:

- **Conventional Commits**, imperative mood, no trailing punctuation
  (e.g. `feat(api): add request timeout setting`).
- One conceptually atomic change per commit; do not mix unrelated changes.
- PRs target `develop`. Confirm with maintainers whether a change should be a
  **stacked PR** (based on a previous feature branch) or a **direct PR**.
- CI must be green; `make check-all` mirrors the CI gate.

## Documentation

User-facing changes need docs. Documentation lives under `docs/modules/ROOT/pages/`
(Antora/AsciiDoc); see the **`technical-writing`** skill for prose conventions. A new page adds the
question it answers to [Common questions](docs/modules/ROOT/pages/questions.adoc). `make check-docs`
checks that every link resolves and every page is in the nav; `make build-docs` builds the site.
