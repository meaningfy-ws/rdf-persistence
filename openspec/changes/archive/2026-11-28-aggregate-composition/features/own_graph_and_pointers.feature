# Draft for the developer's sign-off. Task 1.10 appends these scenarios, with their steps, to
# tests/generator/feature/uml_import.feature.

Feature: Parts in their own graph, and pointers to roots
  A loaded graph can belong to an aggregate and go with it; anything outside an aggregate points
  at its root, never into its parts.

  # spec: rp-uml-import / loaded reports of a shelf count
  Scenario: A shelf count keeps its loaded reports in their own graphs
    Given a shelf count with "own graph" compositions to a count report and a shape report
    And both reports are stereotyped "loaded graph"
    And the shape report holds its shape results by a plain composition
    When the package is converted
    Then the slots "count_report" and "shape_report" range over URIs and are marked as loaded graphs
    And neither slot is owned
    And the shape result is not generated and the report names it
    And the shelf count is an aggregate root

  # spec: rp-uml-import / a generated part in its own graph
  # Replaced on 2026-11-28 by the change dependent-aggregates (scenario 12 of its generation
  # feature): a generated «own graph» part converts to a dependent root; the refusal is gone.

  # spec: rp-uml-import / refused compositions (DEC-7)
  Scenario: A loaded graph cannot be an inline part
    Given a shelf count with a plain composition to a count report stereotyped "loaded graph"
    When the package is converted
    Then the run fails naming the composition and "own graph"

  # spec: rp-uml-import / a pointer into another aggregate's part
  Scenario Outline: A pointer must target a root
    Given a shelf that holds books
    And a reader whose association "borrows" points at <target>
    When the package is converted
    Then <outcome>

    Examples:
      | target    | outcome                                              |
      | the book  | the run fails naming the reader's slot, the book and the shelf |
      | the shelf | the package converts                                 |
      | an access class | the package converts, the slot a reference as before |

  # spec: rp-uml-import / refused compositions (DEC-3)
  Scenario: The old composite association is refused
    Given a library package where the book owns its chapters through an association with a composite end
    When the package is converted
    Then the run fails naming the slot
    And the message says to draw a composition beside a plain association
