# Draft for the developer's sign-off. Task 1.10 appends these scenarios, with their steps, to
# tests/generator/feature/uml_import.feature.

Feature: Roots derived from the compositions
  What is no one's part is a root. The report shows every root, so a class that became one by
  omission is visible; a model that still draws «root» must agree with the compositions.

  # spec: rp-uml-import / what is not a root
  Scenario Outline: A class that is not a root
    Given a library package with <class>
    When the package is converted
    Then that class is not an aggregate root

    Examples:
      | class                                                  |
      | a chapter that is the part of a book                   |
      | an abstract publication with no root below it          |
      | an authority stereotyped "loaded graph"                |
      | a drawn toolkit role definition                        |
      | the library stereotyped "tenant root"                  |
      | a plain class in a package tagged "module_kind=access" |

  # spec: rp-uml-import / the roots are reported
  Scenario: The report lists every root with its parts
    Given a shelf that holds books with chapters, and a reader that is no one's part
    When the package is converted
    Then the report has a root line for the reader with no parts
    And a root line for the shelf with the parts "Book, Chapter"

  # spec: rp-uml-import / a «root» that disagrees
  Scenario Outline: A drawn «root» that disagrees with the compositions fails
    Given a library package that draws «root» on the shelf
    And <disagreement>
    When the package is converted
    Then the run fails naming <named>

    Examples:
      | disagreement                                   | named                              |
      | the reader is no one's part and not drawn «root» | the reader as a root not drawn «root» |
      | the chapter, a part of the book, is drawn «root» | the chapter and the book            |
      | the abstract publication is drawn «root»       | the publication                     |

  # spec: rp-uml-import / «root» and compositions that agree
  Scenario: A model drawn the old way and with compositions converts the same
    Given the library model drawn with «root» and a boundary, converted before compositions existed
    And each association its boundary owned is the only one between its two classes
    And the same model with a composition beside each owned association
    When it is converted
    Then the schema files are byte-identical to the earlier conversion
    And the report adds the root lines and one deprecated-root line
