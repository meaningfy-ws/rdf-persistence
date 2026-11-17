## ADDED Requirements

### Requirement: The token verifier follows the provider's signing algorithm

The token verifier SHALL accept every asymmetric signing algorithm the deployment allows, by
default RS256, RS384, RS512, PS256, PS384, PS512, ES256, ES384, ES512 and EdDSA, and SHALL verify a
token only with a key bound to the token's algorithm. It SHALL refuse to be built when the allowed
algorithms are empty, name `none` or any HMAC (HS*) algorithm, or name an algorithm its verification
library does not implement. It SHALL tolerate a configurable clock skew, by default 30 seconds, on
the token's expiry and not-before times.

#### Scenario: the provider rotates to another asymmetric key type
- **GIVEN** a deployment with the default allowed algorithms
- **WHEN** a request carries a valid token signed with ES384
- **THEN** the request is accepted

#### Scenario: a key published without its algorithm
- **GIVEN** the provider publishes an RSA key that names no algorithm
- **WHEN** a request carries a valid token signed with that key and PS256
- **THEN** the request is accepted

#### Scenario: a token whose algorithm is not its key's
- **GIVEN** the provider publishes an RSA key that names RS256
- **WHEN** a request carries a token with that key's id and the algorithm PS256
- **THEN** the answer is 401 and no handler runs

#### Scenario: a shared-secret algorithm in the configuration
- **GIVEN** a deployment that lists HS512 among its allowed algorithms
- **WHEN** the service is built
- **THEN** building fails, naming HS512

#### Scenario: an algorithm the library does not implement yet
- **GIVEN** a deployment that lists ML-DSA-65, which the verification library does not implement
- **WHEN** the service is built
- **THEN** building fails, naming ML-DSA-65; once a toolkit release pins a library version that implements it, the same configuration builds

#### Scenario: a small clock skew
- **GIVEN** the default clock skew
- **WHEN** a request carries a token that expired 10 seconds ago by the service's clock
- **THEN** the request is accepted, and a token that expired a minute ago is refused with 401
