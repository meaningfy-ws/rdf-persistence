## ADDED Requirements

### Requirement: A subclass that narrows an inherited slot generates code that type-checks

When a class redeclares an inherited slot, through `slot_usage` or `attributes`, so that the
generated field's type is not a subtype of an ancestor's field type (multivalued where an ancestor
is single-valued or the reverse, optional where an ancestor is required, or a range that is neither
the ancestor's range nor under it), `rp-generate` SHALL mark that field's line with
`# type: ignore[assignment]` and keep the field's own type. A field whose type is a subtype of
every ancestor's SHALL carry no mark. A unique-key check a class inherits SHALL accept the slot
it checks holding a list, one value or none. The generated package SHALL pass mypy with
`mypy-generated.ini`.

#### Scenario: an inherited list narrowed to one value
- **GIVEN** an abstract class with an optional multivalued slot `p`, and a subclass whose `slot_usage` sets `p` to `required: true`, `multivalued: false` and a narrower range
- **WHEN** the developer generates and runs mypy with `mypy-generated.ini` over the package
- **THEN** the subclass's field `p` is a single required value, its line ends with `# type: ignore[assignment]`, and mypy reports no error

#### Scenario: an inherited unique key over a list narrowed to one value
- **GIVEN** a class with a multivalued inlined slot whose range declares a unique key, and a subclass that narrows that slot to one required value
- **WHEN** the developer generates and builds an instance of the subclass with one value
- **THEN** the instance validates, a parent instance with two values repeating the key is still refused, and mypy reports no error

#### Scenario: a compatible override carries no mark
- **GIVEN** a subclass that narrows an inherited single-valued slot to a range under the inherited range, keeping its multiplicity and requiredness
- **WHEN** the developer generates
- **THEN** the subclass's field line carries no `# type: ignore`, and mypy reports no error
