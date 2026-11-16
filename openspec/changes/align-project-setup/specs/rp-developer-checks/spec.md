## ADDED Requirements

### Requirement: The coverage floor covers the adapters

The unit and feature coverage floors SHALL measure every module of `rdf_persistence` except the
generated code and the modules that need a running container (`adapters/redis_events.py` and
`testkit/containers/`), which `make test-containers` exercises.

#### Scenario: an untested adapter
- **GIVEN** a new adapter module that no unit test imports
- **WHEN** `make test-unit` runs
- **THEN** the module counts at 0 % towards the 80 % floor

### Requirement: The lint selection is the Meaningfy template's

`make lint` SHALL run Ruff with the project-setup template's selection, including `S113`, `DTZ`,
`BLE001`, `TID251`, `PLR2004`, `PLR0912`, `PLR0913`, `PLR0915` and `PT018`; every suppression
SHALL name its code and its reason.

#### Scenario: a composite assertion
- **GIVEN** a test with `assert a and b`
- **WHEN** `make lint` runs
- **THEN** it fails with `PT018` naming the file and line
