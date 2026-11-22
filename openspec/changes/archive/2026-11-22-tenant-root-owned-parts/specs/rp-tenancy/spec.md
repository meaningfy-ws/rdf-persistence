## ADDED Requirements

### Requirement: A new tenant's root may own parts

When a tenant is created, the service SHALL mint the IRI of each owned part of its root, nested
parts included, from the IRI policy's part template, as an ordinary create does. The body SHALL
leave every part's `id` out, and a part that names one SHALL be refused as an invalid body with
nothing created.

#### Scenario: a root with a part is created
- **GIVEN** the toy library's tenant root, which may own a charter
- **WHEN** a tenant is created whose root holds a charter without an `id`
- **THEN** the tenant is created and its root's charter has an IRI the part template minted

#### Scenario: a part IRI from the body is refused
- **WHEN** a tenant is created whose root's charter names its own `id`
- **THEN** the request is refused as an invalid body and no tenant is created
