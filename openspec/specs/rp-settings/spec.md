# rp-settings Specification

## Purpose
The toolkit's deployment values (timeouts, cache times, limits, the JWKS, events and SSE
durations) as generated settings groups with today's values as defaults, each bounded, passed
from the consumer's composition root into the constructors, and read from the environment only
on request (`settings_from_env`, the `settings` extra).

## Requirements

### Requirement: Deployment values are generated settings with today's defaults

The toolkit's deployment and tuning values SHALL be slots of settings models generated from
LinkML, grouped by area and held together by `ToolkitSettings`: HTTP timeouts and attempts, the
JWKS cache, the directory page size, the event bus, relay and hub, server-sent events, and the size
limits. Every slot SHALL default to the value the toolkit used before. Each adapter,
service and the service kit SHALL take its group as a constructor argument from the consumer's
composition root. Protocol constants SHALL stay next to their use.

#### Scenario: the defaults
- **WHEN** a consumer builds its adapters and the service kit without settings
- **THEN** every timeout, interval and limit is the one the toolkit used before

#### Scenario: a timeout set by the consumer
- **GIVEN** `ToolkitSettings` with an HTTP read timeout of 60 seconds
- **WHEN** the consumer builds its store and token verifier with its `http` group
- **THEN** both use a read timeout of 60 seconds

#### Scenario: a shared-secret algorithm in the settings
- **WHEN** a JWKS settings group lists HS256 among its allowed algorithms
- **THEN** the settings are refused before any verifier is built

#### Scenario: an asymmetric algorithm the installed library lacks
- **GIVEN** a JWKS settings group that lists a post-quantum algorithm name the installed JWT library does not implement
- **WHEN** the settings are built and the token verifier is then built from them
- **THEN** the settings are accepted, and building the verifier fails at start-up naming the algorithm

### Requirement: Settings can be read from the environment on request

The toolkit SHALL offer `settings_from_env`, which builds any generated settings model from
environment variables named by a prefix (default `RP_`) and the slot path. It SHALL validate the
values once, through the generated model. The toolkit SHALL NOT read the environment, or load a
dotenv file, when it is imported.

#### Scenario: a value from the environment
- **GIVEN** the variable `RP_HTTP__READ_TIMEOUT_SECONDS=60`
- **WHEN** the consumer calls `settings_from_env(ToolkitSettings)`
- **THEN** the HTTP read timeout is 60 seconds and every other value is its default

#### Scenario: importing the toolkit
- **GIVEN** an environment variable with an invalid settings value
- **WHEN** `rdf_persistence` is imported
- **THEN** the import succeeds and nothing reads the variable
