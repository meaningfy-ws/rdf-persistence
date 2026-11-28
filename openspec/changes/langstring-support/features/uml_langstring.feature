# Scenarios of the change langstring-support, stage 2 (DEC-9), for the owner's sign-off. Task 2.4
# runs them in tests/generator/feature/; each names the spec delta it proves.

Feature: A language string drawn in the UML model
  As a modeller who draws the domain in Enterprise Architect
  I want an attribute typed as a language string to convert to the toolkit's range
  So that the generated service keeps the languages my model asks for

  # spec: rp-uml-import / a language string
  Scenario: An attribute typed as a language string converts
    Given a model whose class has an attribute "title" typed rdf:langString
    When the model is converted and generated
    Then "title" ranges over the toolkit's language string
    And the generation accepts it

  # spec: rp-uml-import / a plain literal
  Scenario: An attribute typed as a plain literal is refused
    Given a model whose class has an attribute "title" typed rdf:PlainLiteral
    When the model is converted
    Then the conversion fails naming "title" and the toolkit's language string
    And nothing is written
