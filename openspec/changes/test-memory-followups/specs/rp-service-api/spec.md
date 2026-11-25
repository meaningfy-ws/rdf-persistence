## ADDED Requirements

### Requirement: A service no longer referenced is freed

A service built by `install_service` and no longer referenced by the caller SHALL be freed by
garbage collection once the caches of linkml-runtime's `SchemaView` and of FastAPI's dependency
models are cleared; no cache of the Python `typing` module SHALL hold its kit.

#### Scenario: three services dropped
- **GIVEN** three services built from the toy schema and dropped
- **WHEN** the `SchemaView` and FastAPI caches are cleared and garbage is collected
- **THEN** none of their kits is still in memory

### Requirement: Services built from one schema file share one parse

`install_service` SHALL take its schema view from a process-wide cache keyed by the schema file's
resolved path and modification time, so services built from one unchanged file in one process
share one parsed view. A changed file SHALL give a new view. Building and using a service SHALL
NOT modify the view. The views the generator loads SHALL NOT come from this cache.

#### Scenario: two services from one file
- **WHEN** two services are built from the toy schema in one process
- **THEN** both kits hold the same view object

#### Scenario: the file changes
- **GIVEN** a service built from a schema file
- **WHEN** the file is rewritten and another service is built from it
- **THEN** the second kit holds a new view

#### Scenario: a service in use
- **GIVEN** a service built from a cached view
- **WHEN** it creates, reads, lists and deletes an aggregate
- **THEN** the view's modification count and its schema are unchanged

#### Scenario: the generator's view
- **WHEN** the generator loads the toy schema
- **THEN** it gets a view that no service shares
