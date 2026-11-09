## MODIFIED Requirements

### Requirement: Instances of aggregate roots and owned classes are described

Every aggregate root and every owned class SHALL include the `Described` mixin, so its instances
carry an IRI, a label (`skos:prefLabel`) and MAY carry a description (`dcterms:description`). An
owned class MAY opt out of the label with the annotation `rp_unlabelled: true`. Every generated
artefact SHALL treat the description as optional, on roots and on their `is_a` subclasses alike.

#### Scenario: an instance without a label is refused
- **WHEN** a `Book` instance without a label is validated against the generated shapes
- **THEN** validation fails and names the missing `skos:prefLabel`

#### Scenario: an owned value class opts out
- **WHEN** the owned class `Chapter` is annotated `rp_unlabelled: true`
- **THEN** a chapter without a label validates

#### Scenario: a root and its subclass need no description
- **GIVEN** an abstract class mixing in `AggregateRoot` and `Described`, and a served subclass of it by `is_a`
- **WHEN** `rp-generate` runs and both generated classes are built with only an id and a label
- **THEN** both validate, and the JSON Schema of each lists only `id` and `label` as required
