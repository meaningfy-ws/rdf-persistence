## ADDED Requirements

### Requirement: Setting grants checks their roles on every path

`Tenancy.set_grants` SHALL refuse a grant set that `AccessRules.validate_grants` refuses (an
undefined role, a role defined at another level, a foreign target, a non-IRI assignee) before the
consumer's grant validators run, and SHALL store nothing. The generic grants route SHALL give the
same refusal for the same input.

#### Scenario: an undefined role through the service
- **WHEN** a consumer calls `set_grants` with a grant naming a role no definition holds
- **THEN** `UnknownRole` is raised naming the role, and the access record and its version are unchanged

#### Scenario: a system role through the service
- **WHEN** a consumer calls `set_grants` with a grant naming a role defined only at system level
- **THEN** `UnknownRole` is raised and nothing is stored

#### Scenario: the same refusal on both paths
- **WHEN** the same grant set naming an undefined role is sent to `PUT …/grants`
- **THEN** the answer is the 422 `invalid-body` problem the service's refusal maps to

#### Scenario: a stored bad grant can be dropped
- **GIVEN** stored grants naming an undefined role
- **WHEN** `set_grants` is called with a set that no longer names it
- **THEN** the set is stored
