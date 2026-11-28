# Scenarios of the change langstring-support, stage 1 (DEC-8), for the owner's sign-off. Task 1.4
# runs them on a temporary schema; each names the spec delta it proves.

Feature: A measure's decimal numbers in one form
  As a team that builds on the library service
  I want a decimal number to have the same form in the answers and in the generated types
  So that a client never has to guess whether a number comes as text

  # spec: rp-generation / reading the three ranges
  Scenario Outline: Each kind of decimal number is shown in its agreed form
    Given a measure whose <kind> value is 1.5
    When Ada reads the measure as <representation>
    Then the <kind> value is shown as <form>
    And the generated type of the <kind> value is <form>

    Examples:
      | kind    | representation | form           |
      | decimal | plain JSON     | the text "1.5" |
      | float   | plain JSON     | the text "1.5" |
      | double  | plain JSON     | the number 1.5 |
      | decimal | JSON-LD        | the text "1.5" |
      | float   | JSON-LD        | the text "1.5" |
      | double  | JSON-LD        | the number 1.5 |

  # spec: rp-generation / a whole number written to a double slot
  Scenario: A whole number written as a double stays a double
    When Ada writes a measure whose double value is 3, in plain JSON
    Then the write is accepted
    And the measure's double value is stored as a double
