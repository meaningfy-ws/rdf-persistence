# Contributing to RDF Persistence

Thank you for contributing. This guide covers the workflow, the architectural constraints that keep
the codebase healthy, and the testing and review expectations.

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
short, extend it in `rdf_persistence/generation/`, with its own test. Data goes through the
generated models, not bare dicts. See
[Working on the toolkit](docs/modules/ROOT/pages/develop/index.adoc).

## Architecture constraints

This project uses a **cosmic-python layered architecture**, enforced by `import-linter`
(`make check-architecture`). Respect the dependency direction:

```
entrypoints | adapters  →  services  →  domain
```

- `domain/` holds the generated models, the base model, the errors and pure logic — it imports
  **nothing** from upper layers and no I/O, web or validation library.
- `services/` holds the use cases and the **ports** (`Store`, `FileStore`, `Identity`,
  `TokenVerifier`).
- `adapters/` implements the ports (Fuseki, S3, Zitadel, JWKS).
- `entrypoints/` (the service kit) parses input, calls services, formats output.
- `adapters` and `entrypoints` never import each other; the consumer's composition root wires them.
- `generation/` (build time) and `testkit/` (tests) may import any layer; no runtime layer imports
  them.
- Consumers import only from the top-level package `rdf_persistence` (and `rdf_persistence.testkit`
  in tests).

Avoid free strings for symbolic values — use generated enums. Keep observability (logging, tracing)
out of `domain`.

## Testing expectations

- **Write tests first.** Unit tests precede production code (RED-GREEN-REFACTOR).
- **Test by layer**: `tests/unit/` mirrors the code tree; `tests/feature/` holds Gherkin
  (`pytest-bdd`) scenarios written from acceptance criteria, mirroring business capabilities.
- **Coverage gate ≥ 80%** on the suite; keep new/critical code higher.
- Follow the [testing checklist](docs/modules/ROOT/pages/develop/testing.adoc).
- Markers (`unit`, `feature`, `e2e`, `integration`) are applied automatically by path — do not add
  per-file `pytestmark`.

```bash
make test           # full suite with coverage
make test-unit      # fast layer
```

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

User-facing changes need docs. Documentation lives under `docs/` (Antora/AsciiDoc); see the
**`technical-writing`** skill for prose conventions. Build locally with `make preview-docs`.
