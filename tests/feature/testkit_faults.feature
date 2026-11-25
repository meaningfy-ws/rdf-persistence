Feature: A test aims a fault at one request and holds concurrent writes
  As a team that tests a service built on the library
  I want a fault to reach the request I aim it at, and two writers to meet at one version
  So that my fault and conflict tests give the same answer on every run

  # A fault test can keep the relay out

  # spec: rp-testkit / the request takes the armed fault
  Scenario: The request takes the armed fault
    Given a service over the fake store with its relay running
    When inside a paused relay a commit leaves an activity pending, the store is told to fail and a book is posted, twenty times
    Then every post is answered 503 unavailable and, after the block, each pending activity is relayed

  # A test can hold concurrent writes

  # spec: rp-testkit / two writers at one version
  Scenario: Two writers at one version
    Given a service over the fake store with its relay running
    When two requests replace the same book at the same version at once, the relay paused and the store's update held
    Then one is answered 200 and the other 409 conflict, and the stored book is the winner's
