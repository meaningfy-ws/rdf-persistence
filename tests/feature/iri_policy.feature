Feature: A service under its own IRI policy
  As a team that has to mint IRIs of a fixed shape
  I want the service to serve my resources under my policy
  So that every IRI, id in a path and Location header agrees with it

  Background:
    Given the library service runs under the example policy

  # spec: none
  Scenario: A tenant and a book with a chapter live and die under the policy
    When Ada creates a library
    Then the library IRI is under "library/" and ends in a 7-character id
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

  # spec: rp-iri-policy / a path id of the wrong form
  Scenario Outline: A path id of the wrong form is not found
    When Ada reads "<path>"
    Then the answer is 404

    Examples:
      | path                       |
      | /libraries/P4X8K2M         |
      | /libraries/p4x8k2          |
      | /libraries/p4x8k2m/books/X |

  # spec: rp-iri-policy / Without a policy, IRIs are today's (issue #197, acceptance 1)
  Scenario: Without an activity template, an activity is a urn:uuid
    Given Ada has a library with a book
    When Ada moves the book to its next state with a comment
    Then the move's activity IRI is "urn:uuid:" followed by a UUID
    And the book's transitions name that activity

  # spec: rp-iri-policy / transitions and comments still find their activity (issue #197, acceptance 2)
  Scenario: Under an activity template, every activity lives under its tenant
    Given the library service runs under the example policy with activity template "{tenant}/activity/{id}"
    And Ada has a library with a book
    When Ada moves the book to its next state with a comment
    And Ada posts a comment on the book
    And Ada replaces the book with a new label
    Then each of the three activity IRIs is the library IRI, "/activity/" and a UUID
    And the book's transitions name the move's activity
    And the comment's thread names the comment's activity
    And the library's provenance holds the three activities and no "urn:uuid:" IRI

  # spec: rp-iri-policy / a changed activity template (issue #197, acceptance 3)
  Scenario: A restart under another activity template is refused
    Given the library service has started once with no activity template
    When it is restarted with activity template "{tenant}/activity/{id}"
    Then start-up fails naming "activity_template"
    And no IRI has been minted
