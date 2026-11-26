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

A service kit (built by `install_service` or by constructing `ServiceKit`) SHALL take its schema
view from a process-wide cache keyed by the schema file's resolved path and content, so services
built from one unchanged file in one process share one parsed view until the cache is next
emptied. The cache SHALL hold at most
eight views and SHALL be emptied by the testkit's `release_memory`. A file with other content
SHALL give a new view; a missing or unreadable file SHALL raise as `load_schema` does. Building
and using a service SHALL NOT modify the view or any module it imports. The views the generator
loads SHALL NOT come from this cache.

#### Scenario: two services from one file
- **WHEN** two services are built from the toy schema in one process
- **THEN** both kits hold the same view object

#### Scenario: the file changes
- **GIVEN** a service built from a schema file
- **WHEN** the file is rewritten with other content at once and another service is built from it
- **THEN** the second kit holds a new view

#### Scenario: many schema files
- **WHEN** services are built from nine different schema files in one process
- **THEN** the cache holds eight views, and a service from the first file loads it again

#### Scenario: a service in use
- **GIVEN** a service built from a cached view
- **WHEN** it runs its start-up migrations, creates, reads, lists, replaces and deletes an
  aggregate, runs a workflow transition,
  archives and restores a tenant, and serves one event
- **THEN** the view's modification count, every module it holds and its induced slots are
  unchanged

#### Scenario: the generator's view
- **WHEN** the generator loads the toy schema
- **THEN** it gets a view that no service shares
