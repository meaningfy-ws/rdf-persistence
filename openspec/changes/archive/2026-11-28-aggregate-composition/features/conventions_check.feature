# Draft for the developer's sign-off. Task 2.6 appends these scenarios, with their steps, to
# tests/generator/feature/uml_import.feature; task 1.10 the Realisation ones.

Feature: The conventions check and object realisations
  A modeller or CI checks a model before converting it; the check reads it as a conversion does,
  writes nothing and fails on any problem or convention.

  # spec: rp-uml-import / a check writes nothing
  Scenario: A check writes nothing
    Given a library model with one problem
    And an output folder holding an earlier conversion
    When the model is checked
    Then the problem is printed
    And the check fails
    And the output folder is unchanged

  # spec: rp-uml-import / a clean model
  Scenario: A clean model passes the check
    Given a library model with no problem and no convention line
    When the model is checked without an output folder
    Then the check passes and prints nothing

  # spec: rp-uml-import / each convention fails the check
  Scenario Outline: Each convention fails the check
    Given a clean library model seeded with <breach>
    When the model is checked
    Then the check fails with <finding> naming the element

    Examples:
      | breach                                                | finding                         |
      | a class without a prefix                              | an unprefixed-name line         |
      | an association with no multiplicity                   | an unspecified-multiplicity line |
      | a class without a note                                | a no-note line                  |
      | a part drawn «root»                                   | a root_class problem            |
      | an enumeration no dependency uses                     | an unused-enumeration line      |
      | two packages that give one module name                | a package_module problem        |
      | a role owned by the book and used as a pointer by the reader | a boundary_owned problem |
      | a pointer into another aggregate's part               | a boundary_owned problem        |
      | a generalisation to a drawn toolkit class             | a drawn-toolkit-parent line     |
      | a required pointer from the tenant root to a root     | a tenant-required-pointer line  |
      | a boundary named for a class that is no root          | a boundary-disagrees line       |

  # spec: rp-uml-import / the reference collection pattern passes the check
  Scenario: The reference collection the conventions page prescribes passes the check
    Given a clean library model with an abstract collection whose part role stays the toolkit's
    And a shelf that narrows it to books
    When the model is checked
    Then the check passes

  # spec: rp-uml-import / an aggregates diagram holding an association
  Scenario: An aggregates diagram that shows an association
    Given a diagram "catalogue · aggregates" that shows the association "hasChapter"
    When the model is converted
    Then the conversion writes
    And the report has an aggregates-diagram line naming the diagram and the association
    And checking the model fails

  # spec: rp-uml-import / a composition on an association diagram
  Scenario: An association diagram that shows a composition
    Given a diagram "catalogue" that shows the composition from the book to the chapter
    When the model is checked
    Then the check fails with a composition-diagram line

  # spec: rp-uml-import / a role object that realises its class (#435)
  Scenario Outline: A role object and its Realisation
    Given a role object "librarian" <classifier> and a Realisation to <target>
    When the model is converted
    Then <outcome>

    Examples:
      | classifier                    | target                 | outcome                                                  |
      | classified by RoleDefinition  | RoleDefinition         | the roles file is the one written without the Realisation |
      | with no classifier            | RoleDefinition         | it is read as a role definition                          |
      | classified by RoleDefinition  | the book               | the run fails naming the object, RoleDefinition and Book |
