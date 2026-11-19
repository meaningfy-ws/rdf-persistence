# Development Environment Setup

This guide sets up a machine to work on **RDF Persistence** itself. To use the toolkit in an
application instead, see
[Install and lay out the application](docs/modules/ROOT/pages/user-manual/install.adoc). Once the
machine is ready, [Working on the library](docs/modules/ROOT/pages/develop/index.adoc) takes over:
the package layout, the Make targets, the checks and the release.

## Prerequisites

| Tool | Version | Why |
|------|---------|-----|
| Python | >= 3.12 | Runtime |
| [uv](https://docs.astral.sh/uv/) | 0.10+ | Dependency & environment management (`make install` installs it if missing) |
| `make` | any | Task runner |
| Docker + Compose | recent | The container tests, `make test-containers` (optional) |
| Node.js | 18+ | Building the Antora docs site and type-checking the generated TypeScript (optional) |

## 1. Clone and install

```bash
git clone https://github.com/meaningfy-ws/rdf-persistence.git
cd rdf-persistence
make install        # uv sync --all-extras (every dependency group, plus the generate and testkit extras)
```

`make install` does **not** run `uv lock`. Lock dependencies explicitly with `make lock` when
you change them.

## 2. Enable pre-commit hooks

The repo ships a pre-commit config (Ruff format + lint, and `rp-generate-check` on commits that touch
the model or generated code) so problems are caught before they reach CI:

```bash
uv run pre-commit install
uv run pre-commit run --all-files   # optional: check the whole tree once
```

## 3. Verify the environment

```bash
make check-all      # style, types, architecture, docs, freshness, tests
```

A green run means your environment matches CI. With Docker, `make test-containers` runs the
integration and e2e tests against Fuseki, Garage, Zitadel and Redis in containers.

## 4. (Optional) Build the docs locally

```bash
make install-antora # first time only
make build-docs     # writes the site to docs/build/site/
make preview-docs   # builds, then serves it at http://localhost:8081
```

## Troubleshooting

- **Wrong Python interpreter** — always invoke tools through uv (`uv run …`) or `make`,
  never a global `python`/`pytest`.
- **`CLAUDE.md` looks almost empty** — it is a thin pointer that imports `AGENTS.md` (`@AGENTS.md`).
  Edit `AGENTS.md`; keep both as regular files, never a symlink.
