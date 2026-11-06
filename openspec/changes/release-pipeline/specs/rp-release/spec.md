## ADDED Requirements

### Requirement: Releases are proposed from Conventional Commits and merged by a human

After a releasable commit lands on the release branch, release-please SHALL open or update one
release PR that bumps the version by the SemVer rule the commits imply and drafts the changelog
entry, and merging that PR SHALL tag `vX.Y.Z` and create the GitHub Release.

#### Scenario: a fix after a release
- **GIVEN** the last release is `v0.1.0` and a `fix:` commit lands on the release branch
- **WHEN** the release workflow runs
- **THEN** a release PR proposes `0.1.1` with a changelog entry naming the fix, and nothing is tagged until it is merged

### Requirement: A tagged release is published to PyPI without tokens

A merged release PR SHALL build the package once, publish it to TestPyPI, and only if that succeeds
publish the same files to PyPI through Trusted Publishing, with no API token stored in the repository.

#### Scenario: a release reaches PyPI
- **GIVEN** a merged release PR for `0.1.1`
- **WHEN** the publish jobs finish
- **THEN** `rdf-persistence==0.1.1` installs from PyPI, its version equals the tag, and the repository's secrets hold no PyPI token
