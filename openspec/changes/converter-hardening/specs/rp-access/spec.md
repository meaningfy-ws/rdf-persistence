## ADDED Requirements

### Requirement: The role definitions file is read as UTF-8 and refused whole when it cannot be

`load_role_definitions` SHALL read the role definitions file as UTF-8 whatever the host's locale.
A file that cannot be read, holds bytes that are not UTF-8, is not YAML, is nested too deeply, gives
a key twice in one entry, or is not a list of valid definitions SHALL be refused with
`InvalidRoleDefinition` naming the file, never with another exception.

#### Scenario: a non-ASCII role
- **GIVEN** a UTF-8 roles file defining the role `rédacteur`, read on a host whose locale encoding is
  not UTF-8
- **WHEN** it is loaded
- **THEN** the definition's role is `rédacteur`

#### Scenario: bytes that are not UTF-8
- **GIVEN** a roles file holding the byte `0xff`
- **WHEN** it is loaded
- **THEN** it is refused with `InvalidRoleDefinition` naming the file

#### Scenario: a key given twice
- **GIVEN** a roles file whose entry gives `role` twice
- **WHEN** it is loaded
- **THEN** it is refused with `InvalidRoleDefinition` naming the file
