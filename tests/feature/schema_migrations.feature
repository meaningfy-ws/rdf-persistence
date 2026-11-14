Feature: A service that keeps its data in step with its schema
  As a team that changes its model over time
  I want the service to know which version of the schema each library follows
  So that a library the service cannot bring up to date is kept away from readers, not served wrongly

  Scenario: A new library records the versions the service runs
    Given the library service runs the library schema at version 1
    When Ada creates a library
    Then the library records version 1 of the library schema
    And the library records version 2 of the toolkit's own schema

  Scenario: A reader cannot ask for a book of a library that is behind the schema
    Given Ada's library holds a book
    And Bob's library holds a book
    And Rita is a reader of both libraries
    And Ada's library follows a version of the schema that the service does not know
    And the service has started
    When Rita asks for the book of Ada's library
    Then the answer is 503
    And the problem is "tenant-behind"

  Scenario: A reader cannot list the books of a library that is behind the schema
    Given Ada's library holds a book
    And Bob's library holds a book
    And Rita is a reader of both libraries
    And Ada's library follows a version of the schema that the service does not know
    And the service has started
    When Rita lists the books of Ada's library
    Then the answer is 503
    And the problem is "tenant-behind"

  Scenario: A reader is still served by a library that is up to date
    Given Ada's library holds a book
    And Bob's library holds a book
    And Rita is a reader of both libraries
    And Ada's library follows a version of the schema that the service does not know
    And the service has started
    When Rita asks for the book of Bob's library
    Then the answer is 200
