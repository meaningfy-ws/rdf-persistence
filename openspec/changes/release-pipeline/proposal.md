<!-- Parents: the meaningfy-release skill (versioning, changelog, release-please, PyPI Trusted
     Publishing); the archived toolkit-v1-foundation proposal (No-go "Publishing to a package index
     or versioned releases"); openspec/specs/rp-package-boundaries ("Consumers use the public API
     only", which makes "breaking" decidable). Seeds: inputs/seed.md. -->

# EPIC: Automate releases: SemVer, changelog, release-please and PyPI

> Candidate EPIC, shaped 2026-11-06 from the v1 future list. Not planned: the PLAN (design.md, tasks.md) waits for the developer's answers in inputs/seed.md.

**Golden-thread parent:** the `meaningfy-release` policy and capability `rp-package-boundaries`
(requirement "Consumers use the public API only", the surface SemVer protects). It lifts the v1
No-go "Publishing to a package index or versioned releases: consumers install `develop`".

## Appetite

**SMALL.** One capability, releasing, touched in a few places: the release workflow, the
release-please configuration, the version files, the changelog and the contributor docs. The
workflow already exists and is reused.

## Why

v0.1.0 is being tagged by hand. `.github/workflows/release.yaml`, projected from the Meaningfy
template, runs release-please (`release-type: python`) on every push to `develop`, then builds and
publishes to TestPyPI and PyPI through OIDC. It has never released: its logs show release-please
looking for releases on `main` (the repository's default branch) while it runs on `develop`; no
`release-please-config.json` or manifest exists; the version lives in both `VERSION` and
`pyproject.toml`; and the PyPI Trusted Publisher and the `release` environment are unconfirmed.

## Solution outline

After v0.1.0, every release is proposed by release-please from Conventional Commits as a release
PR that bumps the version and drafts the `CHANGELOG.md` entry. A human reviews and merges it; the
merge tags `vX.Y.Z`, creates the GitHub Release, and publishes the package to PyPI through Trusted
Publishing after a TestPyPI dry run. Consumers can pin a released version instead of installing
`develop`.

## Key decisions

- **DEC-1**: Semantic versioning: MAJOR for an incompatible change to the public API, MINOR for a
  compatible addition, PATCH for a compatible fix; pre-releases as `-rc.N`. The public API is the
  top-level `rdf_persistence` names and `rdf_persistence.testkit` (archived DEC-6;
  `rp-package-boundaries`). Source: `meaningfy-release` §1.
- **DEC-2**: release-please proposes, a human merges: no hand release and no release on every merge.
  Source: `meaningfy-release` §4.
- **DEC-3**: PyPI publishing uses Trusted Publishing (OIDC) with no API token, behind a TestPyPI
  gate, in a `release` GitHub environment. Source: `meaningfy-release` §5; `release.yaml`.
- **DEC-4**: `CHANGELOG.md` stays in Keep a Changelog form; the generated entry is a starting point a
  human edits for breaking changes and migration steps. Source: `meaningfy-release` §3; `CHANGELOG.md`.
- **DEC-5**: One bumper keeps the tag and the version files in step; nobody hand-edits both.
  Source: `meaningfy-release` §1.
- **DEC-6**: v0.1.0 is tagged by hand before this EPIC; the EPIC automates later releases. Source:
  the task brief of 2026-11-06.
- **DEC-7**: Commits and PRs carry no AI attribution. Source: AGENTS.md.

## Rabbit-holes

- **Branch model.** `develop` is the integration branch and `main` exists; release-please must
  target the branch releases are cut from, and GitFlow `release/X.Y.Z` branches may or may not apply.
- **Generated code in the wheel.** The package ships generated code (`domain/generated/`); the build
  must not need the generator, and the wheel must hold exactly what `make build` would.
- **0.x semantics.** Before 1.0.0, SemVer allows breaking changes in a MINOR; release-please's
  pre-major options decide how a `feat!` bumps.
- **A bad upload.** PyPI never accepts the same version twice: yank and ship a PATCH.

## No-gos

- Container images or deployment (`ci-cd-delivery` owns those; the toolkit is a library).
- Signing, provenance attestations or an SBOM (recommended, not required: `meaningfy-release` §6),
  unless the developer opts in.
- Publishing the TypeScript types or a client to npm (see `typescript-client`).
- Re-tagging or re-releasing v0.1.0.
- Changing the Conventional Commit rules (`meaningfy-git-workflow` owns them).

---

## What Changes

- `.github/workflows/release.yaml`: target branch and configuration fixed; build through uv if chosen.
- `release-please-config.json` and `.release-please-manifest.json` (starting at 0.1.0).
- `VERSION` and `pyproject.toml`: one source of the version, bumped by release-please.
- `CHANGELOG.md`: entries from release-please, edited by a human.
- `CONTRIBUTING.md` or `docs/modules/ROOT/pages/develop/index.adoc`: how a release is cut.
- `INSTALL.md`, `docs/modules/ROOT/pages/howto/adopt.adoc`: installing a released version.

## Capabilities

### New Capabilities

- `rp-release`: how a version is proposed, tagged and published.

### Modified Capabilities

None.

## Impact

- One-time setup outside the repository: PyPI and TestPyPI Trusted Publishers, the `release` environment.
- Consumers move from installing `develop` to pinning versions.
