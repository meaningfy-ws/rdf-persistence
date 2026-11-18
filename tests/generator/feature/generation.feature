Feature: The generator turns the schemas of a library into its artefacts
  As a team that builds a model-driven RDF application
  I want one command to generate everything from my schemas, and to refuse a schema that breaks the rules
  So that my classes, shapes, context, frames, types and diagrams always agree with the schemas

  # spec: rp-generation / freshly generated code is served (the generation it starts from)
  @slow
  Scenario: The generator writes every artefact of the toy library
    Given a copy of the toy library
    When the library is generated
    Then generation succeeds
    And there is a Python module for each schema module
    And there are the shapes, the context and the frames
    And there are the TypeScript types and the diagrams
    And there is a manifest that lists the generated files

  @slow
  Scenario: Generating twice gives the same files
    Given a copy of the toy library
    When the library is generated
    And the library is generated again into a second copy
    Then both copies hold byte-identical files

  @slow
  Scenario: A schema changed without regenerating is reported as stale
    Given a copy of the toy library that has been generated
    When a slot is added to the books schema
    And the freshness of the generated files is checked
    Then the check fails
    And it names the books schema
    And it names the command that regenerates

  Scenario: A class without a description is refused and nothing is written
    Given a copy of the toy library
    When the description of the Note class is removed from the books schema
    And the library is generated
    Then generation fails
    And the problem names the class "Note" and the missing "description"
    And no file has been written

  Scenario: A class may not set a slot that the toolkit fills
    Given a copy of the toy library
    When the ShelveBooks class gives a usage to the slot the toolkit fills
    And the library is generated
    Then generation fails
    And the problem is tagged "toolkit_filled" and names the class "ShelveBooks" and the slot "started_at_time"
    And no file has been written
