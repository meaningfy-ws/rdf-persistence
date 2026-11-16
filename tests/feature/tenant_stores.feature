Feature: A tenant's data may live on another store
  As a team that serves clients from more than one database server
  I want each library to live on the server it was created on
  So that a client's data stays on its own server, however many servers the service uses

  Background:
    Given the service is wired to the main server and to the server "client-a"

  # spec: rp-tenancy / two tenants on two stores
  Scenario: Two libraries on two servers keep their books apart
    Given Ada's library is created on the main server
    And Bob's library is created on "client-a"
    When a book is written to each library
    Then each book is stored only on its own library's server
    And each book reads back from its own library

  # spec: rp-tenancy / an existing record
  Scenario: A library recorded before servers had names opens on the main server
    Given Ada's library was recorded before servers had names
    When Ada's library is read by a service that has just started
    Then the library opens on the main server

  # spec: rp-tenancy / deletion on the tenant's store
  Scenario: A deleted library is removed from its own server
    Given Ada's library is created on the main server
    And Bob's library is created on "client-a"
    When Bob's library is deleted
    Then Bob's library is gone from "client-a"
    And nothing is removed from the main server

  # spec: rp-tenancy / an orphan on another store
  Scenario: A leftover on another server is removed at start-up
    Given Bob's library is created on "client-a" and holds a book
    And "client-a" holds a library that no one owns
    When the service starts
    Then the library that no one owns is removed from "client-a"
    And Bob's library is still on "client-a"
    And Bob's book is still in it

  # spec: rp-tenancy / a store that is no longer wired
  Scenario: A server that is no longer wired stops the start-up
    Given Bob's library was created on "client-b" while the service was wired to it
    And "client-a" holds a library that no one owns
    And the service is now wired to the main server and to the server "client-a"
    When the service starts
    Then the start-up is refused, naming "client-b"
    And the library that no one owns is still on "client-a"

  # spec: rp-tenancy / a copy on another store
  Scenario: A library is copied to another server by dump and restore
    Given Bob's library is created on "client-a" and holds a book
    When Bob's library is dumped and the dump is restored on the main server
    Then a new library with a new address exists
    And the new library lives on the main server
    And the book reads back from the new library
