<!-- Capability: rp-access. Change: collaboration-and-reference-collections (GitHub issue #81, DEC-4). -->

## ADDED Requirements

### Requirement: Commenting is its own action

The access model SHALL include the action `annotate` (`odrl:annotate`), granted and prohibited
like the other actions, through role definitions or direct permissions. `annotate` SHALL NOT imply
`modify`, and `modify` SHALL NOT imply `annotate`. Role definitions that do not name `annotate`
SHALL keep their meaning.

#### Scenario: a reviewer role
- **GIVEN** a role definition `reviewer` at tenant level with actions `read` and `annotate`
- **WHEN** a principal granted `reviewer` comments on a book and then sends a modify on it
- **THEN** the comment is stored and the modify is refused
