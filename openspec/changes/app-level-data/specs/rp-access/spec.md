## ADDED Requirements

### Requirement: Application data is decided by global roles

The access check for application data SHALL decide an action from the caller's global roles in the
token that the rules allow and the role definitions at level `system` alone. Any permitted
action SHALL imply `read`. Anything not permitted SHALL be denied with `Forbidden`, never with
`NotFound`; tenant grants and prohibitions SHALL never be read for an action on application data.
A role at level `system` permits its actions in every tenant as well: there is no role level for
application data alone.

#### Scenario: a global role permits
- **GIVEN** role definitions where the global role `app-editor` permits `[read, modify]` at level `system`
- **WHEN** a caller whose token carries `app-editor` modifies an application aggregate
- **THEN** the change is allowed

#### Scenario: a tenant owner is not an application editor
- **GIVEN** a caller with the `owner` role on a tenant and no global role
- **WHEN** it modifies an application aggregate
- **THEN** the check answers `Forbidden` and nothing is written
