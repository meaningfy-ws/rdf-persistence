# RDF Persistence

> Serialisation and triple store persistence for RDF data (incl. transactions).

<!-- Badges: replace the placeholders once CI and coverage are wired. -->
[![CI](https://img.shields.io/github/actions/workflow/status/meaningfy-ws/rdf-persistence/ci.yaml?branch=develop)](https://github.com/meaningfy-ws/rdf-persistence/actions)
[![Coverage](https://img.shields.io/badge/coverage-pending-lightgrey)](docs/modules/ROOT/pages/develop/testing.adoc)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

## Overview

rdf-persistence is a toolkit for model-driven RDF applications: a library, a code generator and a
service kit. You write your domain once as a LinkML model; `rp-generate` turns it into Python
classes, SHACL shapes, a JSON-LD context and frames, TypeScript types and diagrams. The library
stores the resulting aggregates in a triple store, one named graph each, with all-or-nothing
commits, a database per tenant, files, access control and events, and serves them over a FastAPI
service.

The library (`rdf_persistence`) and the generator (`rdf_persistence_generation`) ship in one wheel.

## Installation

An application adds `rdf-persistence` to its dependencies from the `develop` branch; see
[Install and lay out the application](docs/modules/ROOT/pages/user-manual/install.adoc).

To work on the toolkit itself you need Python 3.12 or later, [uv](https://docs.astral.sh/uv/) and
`make`:

```bash
git clone https://github.com/meaningfy-ws/rdf-persistence.git
cd rdf-persistence
make install        # uv sync --all-extras
```

[INSTALL.md](INSTALL.md) sets up the rest of a development machine (pre-commit, Docker, the docs
toolchain).

## Documentation

The documentation is an [Antora](https://antora.org) site built from the AsciiDoc pages under
`docs/modules/ROOT/pages/`:

```bash
make install-antora # first time only (needs Node.js)
make build-docs     # writes the site to docs/build/site/
make preview-docs   # builds, then serves it at http://localhost:8081
```

Until you build it, read the pages on GitHub:

| You want to | Start at |
|-------------|----------|
| know what it is and where to go | [Introduction](docs/modules/ROOT/pages/index.adoc), [Common questions](docs/modules/ROOT/pages/questions.adoc) |
| try it in ten minutes | [Getting started](docs/modules/ROOT/pages/tutorials/getting-started.adoc) |
| build an application, step by step | [User manual](docs/modules/ROOT/pages/user-manual/index.adoc) |
| use one feature | [How-to guides](docs/modules/ROOT/pages/howto/index.adoc) |
| understand the design | [Architecture overview](docs/modules/ROOT/pages/architecture/index.adoc), [Use cases](docs/modules/ROOT/pages/requirements/use-cases.adoc), [Capabilities](docs/modules/ROOT/pages/requirements/capabilities.adoc), [Decision records](docs/modules/ROOT/pages/adr/index.adoc) |
| look up a name or an option | [Reference](docs/modules/ROOT/pages/reference/index.adoc) |
| change the toolkit | [Working on the library](docs/modules/ROOT/pages/develop/index.adoc), [Working on the generator](docs/modules/ROOT/pages/develop/generator.adoc) |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the workflow and the rules a change follows, and
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for community expectations. Agents, and the people working
with them, follow [Working with agents](docs/modules/ROOT/pages/develop/agents.adoc).

> **Note on agent-instruction files:** `AGENTS.md` is the **single, canonical** agent-instruction
> file; `CLAUDE.md` is a thin pointer that imports it (`@AGENTS.md`) for Claude Code. Both are
> regular files — never replace either with a symlink or a copy of the other.

## License

Distributed under the Apache 2.0 License. See [LICENSE](LICENSE).
