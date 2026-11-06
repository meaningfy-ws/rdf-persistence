# Development Environment Setup

This guide sets up a full development environment for **RDF Persistence**. For a plain install,
see the [README](README.md#installation).

## Prerequisites

| Tool | Version | Why |
|------|---------|-----|
| Python | >= 3.12 | Runtime |
| [uv](https://docs.astral.sh/uv/) | 0.10+ | Dependency & environment management |
| `make` | any | Task runner / dev UX |
| Node.js | 18+ | Building the Antora docs site (optional) |
| Docker + Compose | recent | Running the local stack (optional) |

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
make check-all      # lint, type-check, architecture, tests
```

A green run means your environment matches CI.

## 4. (Optional) Run the local stack with Docker

If the project ships infra under `infra/`:

```bash
cp infra/.env.example infra/.env        # then fill in any required values
make up                                 # start the stack
make logs                               # follow logs
make down                               # stop the stack
```

> The Docker ignore file lives at `infra/docker/Dockerfile.dockerignore` (Docker auto-discovers
> `<dockerfile>.dockerignore`), not at the repository root.

## 5. (Optional) Build the docs locally

```bash
make install-antora # first time only
make preview-docs   # serve at http://localhost:8081
```

## Troubleshooting

- **Wrong Python interpreter** — always invoke tools through uv (`uv run …`) or `make`,
  never a global `python`/`pytest`.
- **`CLAUDE.md` looks almost empty** — it is a thin pointer that imports `AGENTS.md` (`@AGENTS.md`).
  Edit `AGENTS.md`; keep both as regular files, never a symlink.
