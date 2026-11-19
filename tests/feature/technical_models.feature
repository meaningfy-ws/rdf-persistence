Feature: Technical models are kept apart from the domain
  As a team that builds on the toolkit
  I want the toolkit's own technical models generated apart from the domain models
  So that a domain model never depends on a setting, a wire record or a query template, and my
  settings, my generated defaults and my schemas behave as the toolkit says

  # spec: rp-generation / a domain model imports a technical one
  Scenario: A generated domain model may not import a technical model
    Given a copy of the toolkit where a generated domain module imports a technical model
    When the architecture is checked
    Then the check fails
    And it names the domain module and the technical module

  # spec: rp-generation / a hand-written domain module imports a technical one
  Scenario: The IRI layout of the domain may not import the service settings
    Given a copy of the toolkit where the IRI layout module of the domain layer imports the service settings
    When the architecture is checked
    Then the check fails
    And it names the IRI layout module and the service settings module

  # spec: rp-generation / the schemas a consumer imports
  Scenario: A consumer imports the domain schemas and no technical schema
    Given a consumer schema that imports "rdf_persistence/model/rp_core"
    When the schema is loaded
    Then it resolves as before
    But a consumer schema that imports "rdf_persistence/model/technical/api/rp_api_settings" is refused

  # spec: rp-generation / a domain module in a technical target
  Scenario: A technical target refuses a domain module
    Given a copy of the toy library whose target declares the kind "technical"
    When the models are generated
    Then generation fails naming the "books" module
    And no output file has changed

  # spec: rp-generation / a target without a kind
  Scenario: A target without a kind generates as before
    Given a copy of the toy library whose target declares no kind
    When the models are generated
    Then generation succeeds
    And it writes the same files as before

  # spec: rp-generation / a raw string in a SPARQL term field
  Scenario: A plain string is refused in a SPARQL term field
    Given a generated term model whose fields hold SPARQL terms
    When it is built with a plain string
    Then it is refused before any query text is made
    But it is accepted with a term made from an IRI

  # spec: rp-generation / a group defaults to its own defaults
  Scenario: A group defaults to its own defaults
    Given a class with a "group" slot that defaults to an instance of its class
    And the class of the group gives a default to every one of its slots
    When two objects of the class are built with no value for the group
    Then each holds a group with its defaults
    And the two groups are distinct

  # spec: rp-generation / a slot that cannot default to an instance
  Scenario Outline: A slot that cannot default to an instance stops generation
    Given a slot that defaults to an instance but <fault>
    When the models are generated
    Then generation fails naming the slot "group"
    And no output file has changed

    Examples:
      | fault                                                  |
      | ranges over a type                                     |
      | ranges over a class with a required slot without default |
      | ranges over a class declared after its holder          |
      | takes many values                                      |

  # spec: rp-generation / a list default
  Scenario: A list default is a list of its own for each object
    Given a slot that takes many values and defaults to "RS256, ES256"
    When two objects are built with no value for the slot
    Then each holds the list "RS256", "ES256"
    And the two lists are distinct

  # spec: rp-generation / a list default in another form
  Scenario: A list default in another form stops generation
    Given a slot that takes many values and whose default is the number 3
    When the models are generated
    Then generation fails naming the slot "names"

  # spec: rp-package-boundaries / a service imports an adapter
  Scenario: A service may not import an adapter
    Given a copy of the toolkit where a service module imports an adapter module
    When the architecture is checked
    Then the check fails
    And it names the service module and the adapter module

  # spec: rp-package-boundaries / a service imports a wire model
  Scenario: A service may not import a wire model
    Given a copy of the toolkit where a service module imports a wire model
    When the architecture is checked
    Then the check fails
    And it names the service module and the wire model module

  # spec: rp-package-boundaries / a domain module imports a technical model
  Scenario: A domain module may not import a generated technical model
    Given a copy of the toolkit where a domain module imports the generated settings
    When the architecture is checked
    Then the check fails
    And it names the domain module and the settings module

  # spec: rp-settings / the defaults
  Scenario Outline: Without settings, every value is the one the toolkit used before
    When a consumer builds its adapters and the service kit without settings
    Then the <group> value "<slot>" is <value>
    And the HTTP client of the store and of the token verifier waits 5 seconds to connect and 30 to read

    Examples:
      | group     | slot                         | value |
      | http      | connect_timeout_seconds      | 5.0   |
      | http      | read_timeout_seconds         | 30.0  |
      | http      | max_attempts                 | 3     |
      | jwks      | ttl_seconds                  | 600.0 |
      | directory | page_size                    | 100   |
      | events    | hub_queue_size               | 1000  |
      | sse       | keep_alive_seconds           | 15.0  |
      | limits    | max_document_nodes           | 10000 |

  # spec: rp-settings / a timeout set by the consumer
  Scenario: A read timeout set by the consumer reaches the store and the token verifier
    Given settings with an HTTP read timeout of 60 seconds
    When the consumer builds its store and token verifier with its HTTP group
    Then both use a read timeout of 60 seconds

  # spec: rp-settings / a shared-secret algorithm in the settings
  Scenario: A shared-secret algorithm is refused in the settings
    When a JWKS settings group lists "HS256" among its allowed algorithms
    Then the settings are refused
    And no token verifier is built

  # spec: rp-settings / an asymmetric algorithm the installed library lacks
  Scenario: An algorithm the installed JWT library lacks fails at start-up
    Given a JWKS settings group that lists "ML-DSA-44" among its allowed algorithms
    When the settings are built
    Then the settings are accepted
    But building the token verifier from them fails naming "ML-DSA-44"

  # spec: rp-settings / a value from the environment
  Scenario: A value from the environment sets one setting and leaves the others
    Given the environment variable "RP_HTTP__READ_TIMEOUT_SECONDS" is "60"
    When the consumer reads the toolkit settings from the environment
    Then the HTTP read timeout is 60 seconds
    And every other value is its default

  # spec: rp-settings / importing the toolkit
  Scenario: Importing the toolkit reads no environment variable
    Given the environment variable "RP_HTTP__READ_TIMEOUT_SECONDS" is "abc"
    When the toolkit is imported
    Then the import succeeds
    And nothing has read the variable
