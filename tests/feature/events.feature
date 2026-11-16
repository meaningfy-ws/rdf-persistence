Feature: Every change that happened reaches the event bus, once recorded and in order
  As a team that builds on the library service
  I want each recorded change published to the other services
  So that they react to every change, and to no change that did not happen

  # A committed change is pending publication atomically

  Scenario: A stale write records nothing
    Given a stored book and a session holding an old version of it
    When the session's replace is refused as stale
    Then no activity is pending for that replace

  Scenario: A restore publishes nothing again
    Given a tenant dump holding a pending activity
    When the dump is restored as a new tenant
    Then the restored activity is not pending

  # Events reach the bus at least once, in order per aggregate

  Scenario: A crash between commit and publish
    Given a book commit whose activity is pending
    When the service stops and starts again
    Then a subscriber receives that activity

  Scenario: Events of one aggregate arrive in order
    Given two replaces of one book, both pending
    When the relay publishes them
    Then the replace that generated the older version arrives first

  # Server-sent events respect access

  Scenario: A hidden aggregate
    Given a reader with a Prohibition of read on one book, following the tenant's events
    When that book and another are replaced
    Then the reader receives the other book's event only

  Scenario: Resuming a stream
    Given a reader whose stream ended after event A, and two later commits
    When the reader reconnects with Last-Event-ID A within 7 days
    Then the reader receives the two later events, each once, then live events
