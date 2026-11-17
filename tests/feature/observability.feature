Feature: What the toolkit does can be followed in traces and logs, without a tenant's data in them
  As the team that runs a library service
  I want each store call, commit and sweep to leave a trace and a plain log record
  So that I can see what the service is doing and where it fails, and no library's data leaves it

  # Not projected here, each is a unit test named by its test case in the spec's tables:
  #   "no provider installed" (TC-14, tests/unit/services/test_telemetry.py): it needs an interpreter
  #     in which no provider was ever installed, and this lane's conftest installs one;
  #   "the package loads no SDK" (TC-17, tests/unit/test_packaging.py): a fresh interpreter;
  #   "a traced event" (TC-28, tests/integration/adapters/test_redis_events.py): it needs a Redis
  #     broker, so it runs in the container lane.

  # Traces: store calls and the toolkit's own work

  # spec: rp-observability / a commit's store call
  Scenario: A commit's store call is a child of the commit
    Given a running library service with a tenant
    When a book is committed in the tenant
    Then an update of the store names the store's system and the tenant's database
    And that update is a child of the commit

  # spec: rp-observability / a failing store call
  Scenario: A store that does not answer fails the read and marks its span
    Given a running library service with a tenant holding a book
    And a store that does not answer
    When the book is read
    Then the read fails because the store is unavailable
    And the query of the store is marked as failed with the error's class

  # spec: rp-observability / tenant data stays out of spans
  Scenario: A book's text never appears in a trace
    Given a running library service with a tenant
    When a book titled "secret-tenant-text" is committed in the tenant
    Then no trace attribute contains "secret-tenant-text"

  # spec: rp-observability / one request, one trace
  Scenario: A commit, its store calls and its observer are one trace
    Given a running library service with a tenant
    And an observer of every activity
    When a book is committed in the tenant
    Then the commit, a store call and the observer's work share one trace

  # spec: rp-observability / a relay round
  Scenario: A relay round holds one span per tenant
    Given a running library service with two tenants that each hold a book
    When the relay runs one round
    Then one relay round holds one database span for each tenant
    And each database span names its tenant

  # Logs: constant messages, conventional attributes, no tenant data

  # spec: rp-observability / an orphan database dropped
  Scenario: A database no tenant owns is dropped and logged once
    Given a library service with a tenant, and an orphan database "lib-t-zzzz" on the store "client-a"
    When the service starts and sweeps
    Then one info record says "dropping an orphan database"
    And that record names the step, the database "lib-t-zzzz" and the store "client-a" as attributes

  # spec: rp-observability / a tenant's migration fails
  Scenario: A tenant whose migration fails is named in one error record
    Given a library service with a tenant whose migration request fails
    When the service starts and migrates the tenants
    Then one error record names the tenant, the schema and the migration as attributes
    And that record carries the failure

  # spec: rp-observability / an invalid incoming event
  Scenario: An event whose body is invalid is logged without its values
    Given a library service that receives events
    When it receives an event whose body is invalid and contains "secret-tenant-text"
    Then one warning record carries the kind of failure and the field at fault
    And "secret-tenant-text" appears nowhere in that record

  # spec: rp-observability / the message limit reached through an incoming event
  Scenario: An incoming event that exceeds the message limit is reported once
    Given a library service that receives events, with a message limit of 3
    And a replacement of a book that Ada made
    And an observer that answers each replacement with a command that sends itself again
    When the service receives that replacement
    Then exactly one error record reports it, with the limit 3
