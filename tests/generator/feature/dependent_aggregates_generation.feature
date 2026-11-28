Feature: The model says which aggregates depend on a whole
  A modeller marks a part stored on its own as dependent on its whole; the generator and the UML
  converter refuse a model in which that dependence is unclear.

  # 10. spec: rp-generation / A dependent class points at its whole with a required single slot
  Scenario Outline: A bad pointer to the whole is refused
    Given a schema in which "AuditResult" depends on "Audit" through "of_audit"
    And "of_audit" is <defect>
    When the developer generates the schema
    Then generation fails naming "AuditResult" and "of_audit"
    And no generated file changes

    Examples:
      | defect                                  |
      | optional                                |
      | multivalued                             |
      | ranging over a class that is not a root |
      | ranging over the tenant root            |
      | not a slot of "AuditResult"             |

  # 11. spec: rp-generation / a cycle of dependence
  Scenario: A cycle of dependence is refused
    Given a schema in which "AuditResult" depends on "AuditFinding" and "AuditFinding" depends on "AuditResult"
    When the developer generates the schema
    Then generation fails naming "AuditResult" and "AuditFinding"

  # 12. spec: rp-uml-import / An «own graph» composition to a generated part converts to a dependent root
  Scenario: The converter makes a generated «own graph» part a dependent root
    Given a UML model in which "Audit" is composed «own graph» of the generated class "AuditResult"
    And the association between them names the role "of_audit" on the audit's end, exactly one
    When the modeller converts the model
    Then "AuditResult" is a root that depends on "Audit" through "of_audit"
    And "of_audit" is required and holds one audit
    And "Audit" has no slot listing its results
    And the generator accepts the converted schema
