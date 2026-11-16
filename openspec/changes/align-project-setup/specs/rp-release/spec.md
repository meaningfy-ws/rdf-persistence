## MODIFIED Requirements

### Requirement: The version lives in one file and the release matches the tag

The package version SHALL be written in the root `VERSION` file alone; release-please SHALL mirror
it into `pyproject.toml` and `uv.lock`, and `make check-version` SHALL fail when `pyproject.toml`
differs from it. `rdf_persistence.__version__` SHALL read it from the installed metadata. A release
SHALL build the wheel and sdist with `uv build`, refuse to publish them unless the wheel's version
equals the tag and `import rdf_persistence` works in a clean environment without the `generate`
extra, and attach them to the GitHub Release.

#### Scenario: a release carries its wheel
- **GIVEN** the release PR for `0.2.0` is merged
- **WHEN** the release workflow finishes
- **THEN** the GitHub Release `v0.2.0` holds `rdf_persistence-0.2.0-py3-none-any.whl` and the sdist,
  and on the tagged commit `VERSION` reads `0.2.0` and `pyproject.toml` reads `version = "0.2.0"`

#### Scenario: the version drifts
- **GIVEN** `VERSION` reads `0.5.0` and `pyproject.toml` reads `version = "0.4.0"`
- **WHEN** `make check-version` runs
- **THEN** it fails naming the version in `VERSION`
