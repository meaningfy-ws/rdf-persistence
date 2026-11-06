<!-- SECONDARY INPUT: preserved, never groomed. The EPIC (../proposal.md) is the shaped truth. -->

# Seed: the release pipeline

## Seed text

From the task brief of 2026-11-06 (leader's brief to the shaping agent):

> `release-pipeline` (SMALL): semantic versioning, a changelog, release-please, and PyPI publishing
> with Trusted Publishing. v0.1.0 is being tagged by hand now; this EPIC automates later releases.

From the archived `toolkit-v1-foundation/proposal.md`, No-gos:

> Publishing to a package index or versioned releases: consumers install `develop`.

Policy: the `meaningfy-release` skill (SemVer, Keep a Changelog, release-please release PRs, PyPI
Trusted Publishing with a TestPyPI gate, yank instead of delete).

## What the repository holds today (checked 2026-11-06)

- `.github/workflows/release.yaml`: on push to `develop`, `googleapis/release-please-action@v4`
  with `release-type: python`; on a release, `pipx run build`, TestPyPI then PyPI through
  `pypa/gh-action-pypi-publish` with `id-token: write` in environment `release`.
- The last runs (`gh run list --workflow release.yaml`) succeed in about 10 s and release nothing:
  the log reads "Looking for latest release on branch: main", "Could not find releases", "Missing 1
  paths: .", "No version for path .". The repository's default branch is `main`; the workflow runs
  on `develop` without a `target-branch`.
- No `release-please-config.json`, no `.release-please-manifest.json`.
- `VERSION` holds `0.1.0`; `pyproject.toml` holds `version = "0.1.0"` with a comment that `VERSION`
  is the single source and the field must be kept in sync by hand.
- `CHANGELOG.md`: Keep a Changelog, `[Unreleased]` and `[0.1.0] - 2026-11-06`.
- `SECURITY.md` exists. Build backend: `uv_build` (`[tool.uv.build-backend]`, `module-root = ""`).
- **Not confirmed:** whether the PyPI and TestPyPI Trusted Publishers and the `release` environment
  are configured, and whether the name `rdf-persistence` is free on PyPI.

## Open questions for the developer

1. **Which branch are releases cut from?**
   - (a) `develop` (set `target-branch: develop`): simplest; `main` then has no role.
   - (b) `main`, with `develop` merged into it to release (GitFlow, `meaningfy-release` §2): the
     workflow must run on `main`; one more merge per release.
   - (c) GitFlow `release/X.Y.Z` branches cut from `develop`: stabilisation commits possible; the
     most ceremony for a small library.
2. **Where does the version live?** (a) `pyproject.toml` only, `VERSION` deleted: release-please's
   python strategy bumps it; the "single source" comment changes. (b) Keep both and configure
   release-please's `extra-files` to bump `VERSION`. (c) `VERSION` only, with a dynamic version in
   `pyproject.toml`: depends on the build backend's support.
3. **Before 1.0.0, how do breaking changes bump?** `bump-minor-pre-major: true` (a `feat!` gives
   0.2.0) or a MAJOR (1.0.0) at the first break? And when is 1.0.0 declared?
4. **How is the wheel built?** `pipx run build` as today, or `uv build` (the repository's tool,
   AGENTS.md: "Run Python tooling through uv")? Does the release job run `make check-all` or the
   container tests first, or rely on CI of the merged PR?
5. **Who approves a publish?** Required reviewers on the `release` environment (four-eyes at publish
   time), or the release PR review only?
6. **Consumers' install path.** Do consumers move to PyPI versions at once, or keep installing
   `develop` until 1.0.0? This lifts a v1 No-go; the developer confirms it.
7. **Supply-chain extras.** Opt in now to PyPI attestations (free with Trusted Publishing) or leave
   all of `meaningfy-release` §6 for later?
8. **Pre-releases.** Are `-rc.N` releases published to PyPI, or only finals?

## Test scenarios the EPIC must prove

- A `fix:` commit after v0.1.0 makes release-please open a release PR for 0.1.1 with a changelog entry.
- A `feat:` commit makes it propose 0.2.0; a `feat!:` follows the rule chosen in Q-3.
- Commits of type `docs:`, `chore:`, `test:` alone open no release PR (or appear only under the
  chosen sections).
- Merging the release PR tags `vX.Y.Z`, creates the GitHub Release, and the version in the wheel,
  `pyproject.toml` (and `VERSION`, if kept) equals the tag.
- The TestPyPI job runs before PyPI; a TestPyPI failure stops the PyPI job.
- The PyPI upload uses OIDC; no PyPI token exists in the repository's secrets.
- The published wheel installs in a clean environment and `import rdf_persistence` works without the
  generator extras.
