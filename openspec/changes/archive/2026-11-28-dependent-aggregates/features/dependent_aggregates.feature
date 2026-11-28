# To be signed off by the developer (evidence/clarity-gate.md). Task 2.9 copies these scenarios
# verbatim to tests/feature/dependent_aggregates.feature, with their steps.

Feature: Dependent aggregates are stored on their own and deleted with their whole
  An audit's results are written by several workers, each at its own time. A result is stored on
  its own, but never outlives its audit.

  Background:
    Given Ada has a library with an audit "A1"

  # 1. spec: rp-aggregate-store / A dependent part is written only while its whole exists
  Scenario: A result written after its audit was deleted is refused
    Given Ada has deleted the audit "A1"
    When a worker writes a result for the audit "A1"
    Then the worker is told the audit "A1" is not found
    And no result of the audit "A1" is stored

  # 2. spec: rp-aggregate-store / Deleting a whole deletes its dependent parts
  Scenario: Deleting an audit removes its results, their findings and their files
    Given the audit "A1" has results "R1" and "R2"
    And the result "R1" has a finding "F1" and a loaded report file
    When Ada deletes the audit "A1"
    Then the audit "A1", the results "R1" and "R2", the finding "F1" and the report file are gone
    And one change is recorded with a deletion for each of the four

  # 3. spec: rp-service-api / A whole's delete removes its dependent parts
  Scenario: Deleting an audit needs only the right to delete the audit
    Given the audit "A1" has a result "R1"
    And Bob may delete the audit "A1" and holds no right on its results
    When Bob deletes the audit "A1"
    Then the deletion succeeds
    And the result "R1" is gone

  # 4. spec: rp-aggregate-store / above the limit
  Scenario: An audit with more results than one change may hold is not deleted
    Given one change may hold at most 3 aggregates
    And the audit "A1" has results "R1", "R2" and "R3"
    When Ada deletes the audit "A1"
    Then Ada is told the change is too large, with the limit 3
    And the audit "A1" and its three results remain

  # 5. spec: rp-aggregate-store / a refusing part referred to from outside
  Scenario: A finding another audit cites keeps its audit from being deleted
    Given the audit "A1" has a result "R1" with a finding "F1"
    And findings may not be deleted while referred to
    And the audit "A2" cites the finding "F1"
    When Ada deletes the audit "A1"
    Then Ada is told the deletion is refused because the finding is in use by the audit "A2"
    And the audit "A1", the result "R1" and the finding "F1" remain

  # 6. spec: rp-aggregate-store / the pointer is fixed
  Scenario: A result cannot be moved to another audit
    Given the audit "A1" has a result "R1"
    And Ada has an audit "A2"
    When Ada replaces the result "R1" so that it belongs to the audit "A2"
    Then Ada is told of a conflict on the result's audit
    And the result "R1" still belongs to the audit "A1"

  # 7. spec: rp-aggregate-store / parallel parts
  Scenario: Two workers write their results at the same time
    When two workers each write a result for the audit "A1" at the same time
    Then both results are stored
    And the audit "A1" has not changed

  # 8. spec: rp-aggregate-store / a part written during the delete
  Scenario: A result written after the deletion looked for results makes the deletion retry
    Given Ada's deletion of the audit "A1" has looked for its results and is held before it is sent
    When a worker writes a result "R3" for the audit "A1"
    And Ada's deletion is sent
    Then Ada is told of a conflict on the audit "A1"
    And the audit "A1" and the result "R3" remain

  # 9. spec: rp-aggregate-store / the whole is deleted while the part is being written
  Scenario: A result checked before its audit was deleted is still refused
    Given a worker's result "R3" for the audit "A1" has found the audit and is held before it is sent
    When Ada deletes the audit "A1"
    And the worker's result is sent
    Then the worker is told the audit "A1" is not found
    And no result "R3" is stored
