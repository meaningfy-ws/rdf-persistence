Feature: A service that keeps its data in step with its schema
  As a team that changes its model over time
  I want the service to know which version of the schema each library follows
  So that a library the service cannot bring up to date is kept away from readers, not served wrongly

  Scenario: A new library records the versions the service runs
    Given the library service runs the library schema at version 1
    When Ada creates a library
    Then the library records version 1 of the library schema
    And the library records version 1 of the toolkit's own schema

  Scenario: A library behind the schema is set aside while the others are served
    Given Ada's library holds a book
    And Bob's library holds a book
    And Ada's library follows a version of the schema that the service does not know
    When the service starts
    And Ada asks for the book of her library
    Then the answer is 503 with the problem "tenant-behind"
    When Bob asks for the book of his library
    Then the answer is 200
