Feature: Data that belongs to the application, not to a tenant
  As a team whose service has data of its own, such as report templates
  I want the service to keep it in one place outside every tenant
  So that no tenant sees it and only the people the application trusts can change it

  Background:
    Given the library service has a tenant and an application database

  Scenario: An application aggregate is not in any tenant
    Given an application aggregate
    When the tenant's aggregates are listed and the application's aggregate is read through an application session
    Then the listing does not include it
    And the read returns it

  Scenario: Application writes are versioned
    Given an application aggregate at version v1
    When two application sessions replace it at v1
    Then the first succeeds
    And the second is refused as a conflict

  Scenario Outline: A class in the wrong space
    Given "<tenant class>" is a tenant class and "<application class>" an application class
    When a "<class>" is committed through <session>
    Then the session raises InvalidIri
    And nothing is written

    Examples:
      | tenant class | application class | class    | session                 |
      | Book         | Template          | Book     | an application session  |
      | Book         | Template          | Template | a tenant session        |

  Scenario: The sweep leaves the application database alone
    Given an application database with aggregates and no access record naming it
    When the start-up sweep runs
    Then the application database is unchanged
    And its aggregates are unchanged

  Scenario: A schema without application classes
    Given a schema with no class annotated "database: application"
    When the service starts
    Then no application database is created

  Scenario: A global role permits
    Given role definitions where the global role "app-editor" permits "read" and "modify" at level "system"
    When a caller whose token carries "app-editor" modifies an application aggregate
    Then the change is allowed

  Scenario: A tenant owner is not an application editor
    Given a caller with the "owner" role on a tenant and no global role
    When it modifies an application aggregate
    Then the check answers Forbidden
    And nothing is written
