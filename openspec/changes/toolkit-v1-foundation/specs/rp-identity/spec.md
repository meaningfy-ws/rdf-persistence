Capability: rp-identity. Source: EPIC `toolkit-v1-foundation`; architecture `access-control.adoc#identity`
(N-7, D-10).

## ADDED Requirements

### Requirement: Every request carries a valid token

The service kit SHALL accept a request only with a bearer token whose signature, issuer, audience
and expiry check against the provider's published keys (cached), whatever flow obtained it, and
SHALL answer 401 with a problem response otherwise. The toolkit SHALL offer no login endpoint.

#### Scenario: an expired token
- **WHEN** a request carries a token that expired a minute ago
- **THEN** the answer is 401 and no handler runs

#### Scenario: a service account
- **WHEN** a program sends a token obtained with a private-key JWT
- **THEN** the request is accepted like any other valid token

### Requirement: Accounts are administered through the identity port

The identity port SHALL find an account by exact email, list accounts, disable and re-enable an
account, and grant and remove a global role; the Zitadel adapter SHALL implement exactly these.

#### Scenario: disable an account
- **WHEN** an account is disabled through the port
- **THEN** the provider refuses its next sign-in
