Feature: A change made in one deployment reaches the observers of another
  As a team that runs a second deployment beside the library
  I want the second deployment to hear of each change the first one commits
  So that it can react to it, and never hears of its own changes twice

  Scenario: Another deployment's commit
    Given two deployments share one broker and one library store
    And the second deployment has an observer of replacements
    When the first deployment replaces a book
    Then the second deployment's observer receives the replacement once
    And the first deployment's own observer received it once
