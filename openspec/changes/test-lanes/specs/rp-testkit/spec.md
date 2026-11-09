## ADDED Requirements

### Requirement: A test signer can start from a given key

`TokenSigner` SHALL accept an optional keyword `key` (an RSA private key) and sign with it under its
first key id. Without `key`, it SHALL generate a fresh key, as before. `rotate` SHALL always generate
a fresh key. `rdf_persistence.testkit` SHALL export `new_key()`, which generates such a key, so a
consumer can share one without importing a private module.

#### Scenario: two signers from one key
- **GIVEN** one RSA key and two `TokenSigner(key=that_key)`
- **WHEN** each issues a token
- **THEN** each signer's JWKS verifies the other's token

#### Scenario: no key given
- **GIVEN** two `TokenSigner()` with no key
- **WHEN** the first issues a token
- **THEN** the second's JWKS does not verify it

#### Scenario: rotation after a given key
- **GIVEN** a `TokenSigner(key=k)`
- **WHEN** it rotates to a new key id
- **THEN** the new key is not `k`, and `k` stays in its JWKS
