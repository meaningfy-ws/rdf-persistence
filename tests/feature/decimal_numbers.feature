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

  # spec: rp-generation / a number or a string written to a double slot
  Scenario Outline: A double written as a number or as text stays a double
    When Ada writes a measure whose double value is <value>, in <format>
    Then the write is accepted
    And the measure's double value is stored as a double

    Examples:
      | value     | format     |
      | 3         | plain JSON |
      | 3.0       | plain JSON |
      | the text 3 | plain JSON |
      | 3         | JSON-LD    |
      | the text 3 | JSON-LD    |

  # spec: rp-generation / a boolean written to a double slot
  Scenario Outline: A yes-or-no value is not a double
    When Ada writes a measure whose double value is true, in <format>
    Then the answer is 422 with a problem response naming the double value

    Examples:
      | format     |
      | plain JSON |
      | JSON-LD    |
