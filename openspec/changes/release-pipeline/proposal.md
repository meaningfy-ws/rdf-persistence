<!-- Parents: the meaningfy-release skill (versioning, changelog, release-please, PyPI Trusted
     Publishing); the archived toolkit-v1-foundation proposal (No-go "Publishing to a package index
     or versioned releases"); openspec/specs/rp-package-boundaries ("Consumers use the public API
     only", which makes "breaking" decidable). Seeds: inputs/seed.md. -->

# EPIC: Automate releases: SemVer, changelog, release-please and PyPI

> Shaped 2026-11-06 from the v1 future list; re-shaped and planned 2026-11-12 (see "Re-shaped
> 2026-11-12" below). PLAN: design.md, tasks.md.
>
> **Developer review 2026-11-13: all recommendations accepted** ("accept all recommendations"):
> PD-1 (`main` moved to the tag by hand), PD-4 (CHANGELOG by hand), PD-5 (PyPI jobs removed), PD-9
> (0.2.0 cut by the first run), and the lead may merge the 0.2.0 release PR on green CI.

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
PR into `develop` that bumps the version and drafts the release notes. A human brings the curated
`[Unreleased]` changelog under the new version, reviews and merges the PR; the merge tags `vX.Y.Z`,
creates the GitHub Release with the wheel and sdist attached; then one documented command
fast-forwards `main` to the tag.
Consumers keep installing `develop`; a tag is there for whoever wants to pin. PyPI comes later, as
its own change, when the developer opts in.

## Key decisions

- **DEC-1**: Semantic versioning: MAJOR for an incompatible change to the public API, MINOR for a
  compatible addition, PATCH for a compatible fix; pre-releases as `-rc.N`. The public API is the
  top-level `rdf_persistence` names and `rdf_persistence.testkit` (archived DEC-6;
  `rp-package-boundaries`). Source: `meaningfy-release` §1.
- **DEC-2**: release-please proposes, a human merges: no hand release and no release on every merge.
  Source: `meaningfy-release` §4.
- **DEC-3** (superseded 2026-11-12 by DEC-8): ~~PyPI publishing uses Trusted Publishing (OIDC) with
  no API token, behind a TestPyPI gate, in a `release` GitHub environment.~~ When PyPI comes, it
  comes this way. Source: `meaningfy-release` §5.
- **DEC-4** (sharpened 2026-11-12): `CHANGELOG.md` stays in Keep a Changelog form, curated by hand
  under `[Unreleased]` as each PR lands (today's practice); release-please drafts the release notes
  (release PR body, GitHub Release body), not the file. Source: `meaningfy-release` §3;
  `CHANGELOG.md`; PLAN PD-4.
- **DEC-8** (2026-11-12): no PyPI or TestPyPI publishing in this EPIC; the publish jobs are removed,
  not disabled. A release attaches its wheel and sdist to the GitHub Release. Source: the developer,
  2026-11-06 ("keep install from develop for now"); PLAN PD-5.
- **DEC-9** (2026-11-12): releases are cut from `develop` (release-please `target-branch: develop`);
  `main` is fast-forwarded to each release tag (by hand, one command; see Re-shaped), so it holds
  the last release. Source: leader's choice, PLAN PD-1.
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
- Publishing to PyPI or TestPyPI, the `release` environment and Trusted Publishers (DEC-8).
- `release/X.Y.Z` and `hotfix/X.Y.Z` branches: before 1.0.0 a fix ships forward from `develop`
  (PLAN PD-1, RISK-2).
- Pre-releases (`-rc.N`).
- Changing the Conventional Commit rules (`meaningfy-git-workflow` owns them).

---

## What Changes

- `.github/workflows/release.yaml`: release-please from the config files, `target-branch: develop`;
  build with `uv build`, check, attach to the Release; PyPI jobs removed. `main` is moved by the
  documented command, not by the workflow.
- `release-please-config.json` and `.release-please-manifest.json` (starting at 0.1.0).
- `VERSION` deleted; `pyproject.toml` is the one source; `rdf_persistence.__version__` reads the
  installed metadata; release-please mirrors the version into `uv.lock`.
- `CHANGELOG.md`: the release-process comment points to the docs.
- `docs/modules/ROOT/pages/develop/index.adoc` (+ a question in `questions.adoc`): how a release is cut.

## Capabilities

### New Capabilities

- `rp-release`: how a version is proposed, tagged and attached to a GitHub Release.

### Modified Capabilities

None.

## Impact

- No setup outside the repository: `GITHUB_TOKEN` may already create PRs and tags; `main` is
  unprotected and moved by a person, whose credential may push workflow changes.
- Consumers keep installing `develop`; tags `vX.Y.Z` and their wheels are there to pin.
- The pending 0.2.0 (PRs #71 #74 #75 #77, and the `feat(router)!` since v0.1.0) is the pipeline's
  first release.

## Re-shaped 2026-11-12

Logged when the PLAN was derived (the developer was away; every choice below is the leader's,
accepted by default per inputs/seed.md, and the developer may overrule it):

- PyPI dropped from the scope (DEC-3 superseded by DEC-8), following the developer's answer of
  2026-11-06. The spec requirement "A tagged release is published to PyPI without tokens" is
  replaced by "The version lives in one file and the release matches the tag".
- The branch question (Rabbit-hole "Branch model") decided: DEC-9.
- DEC-4 sharpened: release-please does not write `CHANGELOG.md`.
- New requirement "`main` holds the last release".
- After gate 1 (2026-11-12, 8/10; PLAN PD-12): `main` is fast-forwarded by a documented manual
  command, not by the workflow, because `GITHUB_TOKEN` cannot push commits that change
  `.github/workflows/*`; the requirement "`main` holds the last release" now names that step and
  gains the scenario "main moved by someone else". Automating it later needs a token only the
  developer can create (PLAN Open Questions).
