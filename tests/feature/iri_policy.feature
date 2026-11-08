Feature: A service under its own IRI policy
  As a team that has to mint IRIs of a fixed shape
  I want the service to serve my resources under my policy
  So that every IRI, id in a path and Location header agrees with it

  Background:
    Given the library service runs under the project policy

  Scenario: A tenant and a book with a chapter live and die under the policy
    When Ada creates a library
    Then the library IRI is under "project/" and ends in a 7-character id
    And its Location path ends in that id
    When Ada adds a book with a chapter to it
    Then the book IRI is flat beside the library id under "book"
    And the chapter IRI is flat beside the library id under "chapter"
    And the book Location path ends in the book id
    And reading the book answers its IRI and its chapter
    And listing the books answers the book
    When Ada replaces the book with a new label
    Then reading the book answers the new label
    When Ada deletes the book
    Then reading the book answers 404

  Scenario Outline: A path id of the wrong form is not found
    When Ada reads "<path>"
    Then the answer is 404

    Examples:
      | path                       |
      | /libraries/P4X8K2M         |
      | /libraries/p4x8k2          |
      | /libraries/p4x8k2m/books/X |
