Feature: The service accepts the signing algorithms its identity provider uses
  As a team that runs the library service behind an identity provider
  I want the service to follow the provider's signing algorithm
  So that a provider changing its keys does not lock people out, and a weak setting cannot be chosen

  # spec: rp-identity / the provider rotates to another asymmetric key type
  Scenario: The provider rotates to another asymmetric key type
    Given a deployment with the default allowed algorithms
    When a request carries a valid token signed with ES384
    Then the request is accepted

  # spec: rp-identity / a key published without its algorithm
  Scenario: A key published without its algorithm
    Given the provider publishes an RSA key that names no algorithm
    When a request carries a valid token signed with that key and PS256
    Then the request is accepted

  # spec: rp-identity / a token whose algorithm is not its key's
  Scenario: A token whose algorithm is not its key's
    Given the provider publishes an RSA key that names RS256
    When a request carries a token with that key's id and the algorithm PS256
    Then the answer is 401 and no handler runs

  # spec: rp-identity / a shared-secret algorithm in the configuration
  Scenario: A shared-secret algorithm in the configuration
    Given a deployment that lists HS512 among its allowed algorithms
    When the service is built
    Then building fails, naming HS512

  # spec: rp-identity / an algorithm the library does not implement yet
  Scenario: An algorithm the library does not implement yet
    Given a deployment that lists ML-DSA-65, which the verification library does not implement
    When the service is built
    Then building fails, naming ML-DSA-65

  # spec: rp-identity / a small clock skew
  Scenario: A small clock skew
    Given the default clock skew
    When a request carries a token that expired 10 seconds ago by the service's clock
    Then the request is accepted
    When a request carries a token that expired a minute ago by the service's clock
    Then the answer is 401 and no handler runs
