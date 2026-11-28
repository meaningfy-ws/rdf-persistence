# Draft for the developer's sign-off. Task 1.10 appends these scenarios, with their steps, to
# tests/generator/feature/uml_import.feature (steps in tests/generator/feature/test_uml_import.py).

Feature: Aggregates drawn as compositions
  A modeller states what is part of what with compositions; the converter makes the parts owned
  and stored with their whole, whatever the layout of the diagram.

  # spec: rp-uml-import / a package with a root and a part
  Scenario: A book owns its chapters through a composition
    Given a library package where the book has an association "hasChapter" to its chapters
    And a composition from the book to the chapter beside it
    When the package is converted
    Then the slot "has_chapter" is owned and inlined as a list
    And the book is an aggregate root and the chapter is its part
    And the generator's lint and boundary checks accept the output

  # spec: rp-uml-import / the composition drawn either way
  Scenario: The direction a composition was drawn in does not matter
    Given the composition from the book to the chapter is drawn from the chapter to the book
    And its diamond is at the book
    When the package is converted
    Then the output is the same as when it is drawn from the book to the chapter

  # spec: rp-uml-import / the composition drawn either way (design.md RISK-9, D-4)
  # Run by hand by the developer before any release (task 1.12); evidence in evidence/ea-connectors.md.
  @manual
  Scenario: An EA-drawn composition reads the same either way
    Given a scratch model saved by Enterprise Architect with a book and a chapter and an association "hasChapter" between them
    And a composition drawn in EA from the book to the chapter
    And, in a copy, the same composition drawn from the chapter to the book with its diamond at the book
    And, in a third copy, a shared aggregation from the book to the chapter
    When each copy is converted
    Then the first two convert to the same schemas, with "has_chapter" owned by the book
    And the third fails naming the shared aggregation
    And the connector columns EA wrote are recorded in the evidence

  # spec: rp-uml-import / parts three deep
  Scenario: Parts nest three deep
    Given compositions from the shelf to the book, from the book to the chapter and from the chapter to the page
    When the package is converted
    Then the shelf is the only root of the four
    And the slots "holds", "has_chapter" and "has_page" are owned

  # spec: rp-uml-import / a boundary moved in a layout pass
  Scenario Outline: A layout change never changes what is stored together
    Given a converted library package with a boundary around the book and its chapters
    When the boundary is <moved> and the package is converted again
    Then the schemas are byte-identical to the first conversion

    Examples:
      | moved                           |
      | shrunk so the chapter is outside |
      | slid off every class            |
      | deleted                         |

  # spec: rp-uml-import / recursive and shared part classes
  Scenario: Sections hold subsections, and a note sits under two wholes
    Given compositions from the book to the section and from the section to the section
    And the note is a part of the book and of the chapter
    When the package is converted
    Then the conversion writes
    And the book is the only root among them

  # spec: rp-uml-import / two roles to one part class
  Scenario: Two owned roles and a reference to one part class
    Given the book has associations "frontMatter" and "body" to the section, each with a composition naming its role
    And an association "firstSection" from the book to the section with no composition
    When the package is converted
    Then the slots "front_matter" and "body" are owned
    And the slot "first_section" is a reference

  # spec: rp-uml-import / refused compositions
  Scenario Outline: A composition the converter cannot read fails the run
    Given a library package with <drawing>
    When the package is converted
    Then the run fails naming <named>
    And nothing is written

    Examples:
      | drawing                                                     | named                                 |
      | a composition from the book to the chapter and no association | the book, the chapter and the missing association |
      | two associations beside one composition that names no role  | both roles                            |
      | compositions from the chapter to the page and back, no root composing either | the cycle            |
      | a page whose whole no root reaches                          | the page                              |
      | a composition to a class outside the converted package      | the composition and the subtree       |
      | a shared aggregation from the book to the chapter           | the connector and the composition to draw |
      | an association whose end at the book is composite           | the slot and the two-connector form   |
