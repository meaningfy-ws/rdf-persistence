# rp-release Specification

## Purpose
TBD - created by archiving change release-pipeline. Update Purpose after archive.
## Requirements
### Requirement: Releases are proposed from Conventional Commits and merged by a human

Release-please SHALL, after a releasable commit (`feat`, `fix`, `perf`, `revert`, or any commit
marked breaking) lands on `develop`, open or update one release PR into `develop` that bumps the version
by the rule below. Merging that PR SHALL tag `vX.Y.Z` on its merge commit and create the GitHub
Release. Commits of other types alone SHALL open no release PR. Before 1.0.0, a breaking change
SHALL bump the MINOR and a `feat` SHALL bump the MINOR; a `fix` SHALL bump the PATCH.

#### Scenario: a fix after a release
- **GIVEN** the last release is `v0.2.0` and a `fix:` commit lands on `develop`
- **WHEN** the release workflow runs
- **THEN** a release PR proposes `0.2.1`, and nothing is tagged until it is merged

#### Scenario: a breaking change before 1.0.0
- **GIVEN** the last release is `v0.1.0` and a `feat(router)!:` commit lands on `develop`
- **WHEN** the release workflow runs
- **THEN** the release PR proposes `0.2.0`, not `1.0.0`

#### Scenario: only docs and chores since the release
- **GIVEN** only `docs:`, `test:`, `ci:` and `chore:` commits and merge commits landed since the last tag
- **WHEN** the release workflow runs
- **THEN** no release PR is opened and nothing is tagged

### Requirement: The version lives in one file and the release matches the tag

The package version SHALL be written in `pyproject.toml` alone (and mirrored by release-please into
`uv.lock`); `rdf_persistence.__version__` SHALL read it from the installed metadata. A release SHALL
build the wheel and sdist with `uv build`, refuse to publish them unless the wheel's version equals
the tag and `import rdf_persistence` works in a clean environment without the `generate` extra, and
attach them to the GitHub Release.

#### Scenario: a release carries its wheel
- **GIVEN** the release PR for `0.2.0` is merged
- **WHEN** the release workflow finishes
- **THEN** the GitHub Release `v0.2.0` holds `rdf_persistence-0.2.0-py3-none-any.whl` and the sdist,
  and `pyproject.toml` on the tagged commit reads `version = "0.2.0"`

### Requirement: `main` holds the last release

After a release is tagged and its build is green, `main` SHALL be fast-forwarded to the tagged
commit with the documented release step, and SHALL be left unchanged when that is not a
fast-forward (the step never force-pushes).

#### Scenario: main follows the tag
- **GIVEN** `main` is at `v0.1.0` and the release PR for `0.2.0` is merged into `develop`
- **WHEN** the release workflow has finished green and the documented step
  `git push origin "v0.2.0^{commit}:refs/heads/main"` is run
- **THEN** `main` points at the commit tagged `v0.2.0`

#### Scenario: main moved by someone else
- **GIVEN** `main` holds a commit that is not an ancestor of the commit tagged `v0.2.0`
- **WHEN** the documented step is run
- **THEN** the push is refused and `main` is unchanged

