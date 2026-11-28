# Scenarios of the change langstring-support, stage 2, for the owner's sign-off. Task 2.9 appends
# them to tests/feature/ with their steps. Each scenario names the spec delta it proves. The decimal
# numbers are in decimal_numbers.feature, the converter in uml_langstring.feature.

Feature: A book's titles in every language they were written in
  As a team that builds on the library service
  I want a book's titles to keep their languages
  So that no reader, writer or format loses which language a title is in

  Background:
    Given Ada's library holds a book titled "Dune" in "en" and "Dune" in "FR"

  # spec: rp-service-api / a read-modify-write keeps the tags
  Scenario: Changing another detail of the book keeps its titles' languages
    When Ada changes the book's subtitle through a session
    Then the book's titles are "Dune" in "en" and "Dune" in "FR"
    And the stored book is otherwise as it was

  # spec: rp-service-api / plain JSON of a language-string slot
  Scenario Outline: Every format shows each title with its language
    When Ada reads the book as <representation>
    Then each title is shown with its language, "en" and "FR" as written

    Examples:
      | representation |
      | plain JSON     |
      | JSON-LD        |
      | Turtle         |

  # spec: rp-service-api / a plain-JSON write of value objects
  Scenario: A title written with its language is stored with it
    When Ada replaces the book's titles with "Arrakis" in "en", in plain JSON
    Then the book's titles are "Arrakis" in "en"

  # spec: rp-service-api / a plain-JSON write of value objects
  Scenario: A title written without a language is refused
    When Ada replaces the book's titles with "Arrakis" with no language, in plain JSON
    Then the answer is 422 with a problem response
    And the book's titles are unchanged

  # spec: rp-service-api / a malformed language tag in a write
  Scenario Outline: A title with a malformed language is refused
    When Ada replaces the book's titles with "Arrakis" in "en" followed by a line break, in <format>
    Then the answer is 422 with a problem response naming the titles
    And the book's titles are unchanged

    Examples:
      | format     |
      | plain JSON |
      | JSON-LD    |

  # spec: rp-service-api / a tagged literal in a string slot
  Scenario Outline: A language on a detail that has none is refused, not dropped
    Given the stored book's subtitle holds "Arrakis" in "en"
    When the book is read <how>
    Then the read is refused naming the book's subtitle
    And the stored book is unchanged

    Examples:
      | how                        |
      | through a session          |
      | by a guard before a write  |

  # spec: rp-service-api / an untagged literal in a language-string slot
  Scenario: A title stored without a language is refused, not guessed
    Given the stored book's titles hold "Dune" with no language
    When the book is read through a session
    Then the read is refused naming the book's titles
    And the stored book is unchanged

  # spec: rp-service-api / a listing filter on a language-string slot
  Scenario Outline: Titles cannot be filtered on
    When Ada lists the books whose titles <operator> "Dune"
    Then the answer is 400 with a problem response naming the titles

    Examples:
      | operator |
      | equal    |
      | contain  |

  # spec: rp-generation / a range narrowed to a language string
  Scenario: A model may not turn an inherited plain text into a language string
    Given a model whose book narrows the inherited label to a language string
    When the model is generated
    Then the generation is refused naming the book and its label

  # spec: rp-generation / a language string in a unique key
  Scenario: Titles cannot make a book unique
    Given a model whose book is unique by its titles
    When the model is generated
    Then the generation is refused naming the book and its titles

  # spec: rp-generation / an untagged value in a language-string field
  Scenario Outline: A title needs a well-formed language
    When a developer builds a book whose title is <title>
    Then it is refused naming the titles

    Examples:
      | title                               |
      | "Dune" with no language             |
      | "Dune" typed as a number            |
      | "Dune" in the language "not a tag!" |
      | "Dune" in "en" with a line break    |
