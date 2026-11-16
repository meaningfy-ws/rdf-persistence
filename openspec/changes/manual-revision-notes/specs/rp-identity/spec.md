## ADDED Requirements

<!-- Candidate delta, from inputs/improvements.md A-3 and A-4. The EPIC is not shaped yet; the
     other candidate changes will add their deltas when they are. -->

### Requirement: The token verifier follows the provider's signing algorithm

The token verifier SHALL accept every asymmetric signing algorithm the deployment allows, by
default RS256, RS384, RS512, PS256, PS384, PS512, ES256, ES384, ES512 and EdDSA. It SHALL refuse
`none` and every HMAC (HS*) algorithm even when a deployment lists them. It SHALL tolerate a
configurable clock skew, by default 30 seconds, on the token's expiry and not-before times.

#### Scenario: the provider rotates to another asymmetric key type
- **GIVEN** a deployment with the default allowed algorithms
- **WHEN** a request carries a valid token signed with ES384
- **THEN** the request is accepted

#### Scenario: a shared-secret token
- **GIVEN** a deployment that lists HS512 among its allowed algorithms
- **WHEN** a request carries a token signed with HS512
- **THEN** the answer is 401 and no handler runs

#### Scenario: a small clock skew
- **GIVEN** the default clock skew
- **WHEN** a request carries a token that expired 10 seconds ago by the service's clock
- **THEN** the request is accepted, and a token that expired a minute ago is refused
