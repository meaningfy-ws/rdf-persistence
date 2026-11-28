Feature: A person's queue of work is one listing of the books
  As a team that builds on the library service
  I want to list the books a person is one of the assignees of
  So that each person finds their work with the listing every client already has

  # spec: rp-workflow / A person's queue is one listing
  Scenario Outline: My work: the books assigned to a person
    Given Ada's library holds the books b1, b2 and b3
    And Pia and Pol may read the library
    And Ada assigns b1 to Pia and Pol
    And Ada assigns b2 to Pol
    When Ada lists the books assigned to <person>
    Then the listing holds <books>
    And its total is <total>

    Examples:
      | person | books  | total |
      | Pol    | b1, b2 | 2     |
      | Pia    | b1     | 1     |
      | Quinn  | none   | 0     |

  # spec: rp-workflow / Losing read access releases an assignment
  Scenario Outline: Losing read access releases an assignment
    Given Ada's library holds the books b1
    And Pia and Pol may read the library
    And Pia holds <own grant> on b1
    And Ada assigns b1 to Pia and Pol
    When Ada replaces the grants without Pia's reading of the library
    Then b1 is assigned to <assignees>
    And its last assignment, by Ada, released <released>

    Examples:
      | own grant | assignees | released |
      | no grant  | Pol       | Pia      |
      | a grant   | Pia, Pol  | no one   |
