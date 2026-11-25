## ADDED Requirements

### Requirement: Two slots do not share one IRI

`rp-generate` SHALL refuse a target whose import closure, toolkit included, has two slots or class
attributes with different names on one expanded IRI, one of them declared in the target's own
modules (rule `slot_iri`). A slot or attribute with `identifier: true` SHALL be left out of the
comparison. The problem SHALL name every slot on that IRI with its module, and the IRI.

#### Scenario: an application slot on the toolkit's membership predicate
- **GIVEN** an application module that defines `parts` on `dcterms:hasPart`, while the toolkit's `has_part` is on `dcterms:hasPart`
- **WHEN** the developer regenerates
- **THEN** generation fails with `[slot_iri]` naming `parts`, `has_part` and `http://purl.org/dc/terms/hasPart`, and nothing is written

#### Scenario: a business identifier beside the identifier slot
- **GIVEN** a class with the toolkit's `id` (`identifier: true`) and a slot `identifier`, both on `dcterms:identifier`
- **WHEN** the developer regenerates
- **THEN** generation succeeds as before

#### Scenario: a default IRI and an attribute on another slot's IRI
- **GIVEN** a slot with no `slot_uri` whose default IRI (the module's default prefix and its name) is another slot's `slot_uri`, or a class attribute on another slot's `slot_uri`
- **WHEN** the developer regenerates
- **THEN** generation fails with `[slot_iri]` naming both
