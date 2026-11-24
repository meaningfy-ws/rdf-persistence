## ADDED Requirements

### Requirement: A consumer's route reads If-Match through the public API

`expected_version` and `matched_version` SHALL be importable from `rdf_persistence` and SHALL apply
the generic routes' rules: one strong tag gives its version; a missing header is the 428 problem;
a weak tag, a list or `*` is refused as the generic routes refuse it.

#### Scenario: one strong tag
- **WHEN** a consumer calls `rdf_persistence.expected_version('"v1"')`
- **THEN** it gets `v1`

#### Scenario: no If-Match
- **WHEN** a consumer calls `rdf_persistence.expected_version(None)`
- **THEN** the generic routes' 428 problem is raised
