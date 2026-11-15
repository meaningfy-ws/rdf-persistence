<!-- Capability: rp-generation. Change: message-bus (design.md PD-20, PD-21, D-11 e). -->

## MODIFIED Requirements

### Requirement: A technical module may hold shapes that are never stored

The ownership rule SHALL NOT apply to classes of a module annotated `module_kind: technical`; they
SHALL be generated in Python and TypeScript. A class of a domain or access module that is neither a
root nor owned SHALL still be refused, except a class that descends from `Activity`, which is a
command or a record of the provenance graph and SHALL be exempt.

#### Scenario: an API shape in a technical module
- **GIVEN** a technical module with a class that is neither a root nor owned
- **WHEN** `rp-generate` runs
- **THEN** it succeeds and generates the class in Python and TypeScript

#### Scenario: the same class in a domain module
- **GIVEN** a domain module with a class that is neither a root nor owned
- **WHEN** `rp-generate` runs
- **THEN** it fails with an ownership problem naming the class

#### Scenario: a command in a domain module
- **GIVEN** a domain module with `ShelveBooks`, a class that descends from `Activity` and is neither a root nor owned
- **WHEN** `rp-generate` runs
- **THEN** it succeeds and reports no ownership problem for `ShelveBooks`

## ADDED Requirements

### Requirement: A stored class does not point at a consumer activity

A slot of a stored class SHALL NOT range over a consumer activity class that is not an aggregate
root; `rp-generate` SHALL refuse it with an `activity_direction` problem naming the class and the
slot. A slot MAY range over a toolkit activity class such as `Activity` or `Transition`, and an
activity class MAY point at stored classes.

#### Scenario: a book that points at a command
- **GIVEN** `Book`, a stored class, with a slot whose range is `ShelveBooks`
- **WHEN** `rp-generate` runs
- **THEN** it fails with an `activity_direction` problem naming `Book` and the slot

#### Scenario: a command that points at a book
- **GIVEN** `ShelveBooks` with the slot `used_resource` over `Book`
- **WHEN** `rp-generate` runs
- **THEN** it succeeds and reports no `activity_direction` problem

### Requirement: A consumer does not redefine what the toolkit fills

A consumer class SHALL NOT redefine a toolkit-filled slot by `slot_usage`, `ifabsent` or an
attribute, SHALL NOT declare a slot whose expanded `slot_uri` is that of a toolkit-filled slot, and
SHALL NOT make a slot annotated `payload` required; `rp-generate` SHALL refuse each with a
`toolkit_filled` problem naming the class.

#### Scenario: a command that sets the start time
- **GIVEN** `ShelveBooks` with a `slot_usage` on `started_at_time`
- **WHEN** `rp-generate` runs
- **THEN** it fails with a `toolkit_filled` problem naming `ShelveBooks`

#### Scenario: a slot that aliases a toolkit-filled slot
- **GIVEN** `ShelveBooks` with a slot of its own whose `slot_uri` is that of `to_state`
- **WHEN** `rp-generate` runs
- **THEN** it fails with a `toolkit_filled` problem naming `ShelveBooks`

#### Scenario: a required payload slot
- **GIVEN** `ShelveBooks` with a `payload` slot that is required
- **WHEN** `rp-generate` runs
- **THEN** it fails with a `toolkit_filled` problem naming `ShelveBooks`

#### Scenario: the toy as it is
- **GIVEN** `ShelveBooks` with `used_resource` and its own `shelf_note`, and `Book`
- **WHEN** `rp-generate` runs
- **THEN** it succeeds and reports no `toolkit_filled` problem
