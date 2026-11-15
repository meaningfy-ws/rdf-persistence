Feature: A tenant's data may live on another store
  As a team that serves clients from more than one database server
  I want each library to live on the server it was created on
  So that a client's data stays on its own server, however many servers the service uses

  Scenario: Two libraries on two servers keep their books apart
    Given the service is wired to the main server and to the server "client-a"
    And Ada's library is created on the main server
    And Bob's library is created on "client-a"
    When a book is written to each library
    Then each book is stored only on its own library's server
    And each book reads back from its own library

  Scenario: A library recorded before servers had names opens on the main server
    Given the service is wired to the main server and to the server "client-a"
    And Ada's library was recorded before servers had names
    When Ada's library is read by a service that has just started
    Then the library opens on the main server

  Scenario: A deleted library is removed from its own server
    Given the service is wired to the main server and to the server "client-a"
    And Ada's library is created on the main server
    And Bob's library is created on "client-a"
    When Bob's library is deleted
    Then Bob's library is gone from "client-a"
    And nothing is removed from the main server

  Scenario: A leftover on another server is removed at start-up
    Given the service is wired to the main server and to the server "client-a"
    And Bob's library is created on "client-a" and holds a book
    And "client-a" holds a library that no one owns
    When the service starts
    Then the library that no one owns is removed from "client-a"
    And Bob's library is still on "client-a" with its book

  Scenario: A server that is no longer wired stops the start-up
    Given Bob's library was created on "client-b" while the service was wired to it
    And "client-a" holds a library that no one owns
    And the service is now wired to the main server and to the server "client-a"
    When the service starts
    Then the start-up is refused, naming "client-b"
    And the library that no one owns is still on "client-a"

  Scenario: A library is copied to another server by dump and restore
    Given the service is wired to the main server and to the server "client-a"
    And Bob's library is created on "client-a" and holds a book
    When Bob's library is dumped and the dump is restored on the main server
    Then a new library with a new address lives on the main server
    And the book reads back from the new library
