## ADDED Requirements

<!-- Candidate delta: the EPIC (proposal.md) is shaped, the PLAN is not derived (shaped-not-planned,
     OPEN-1); the requirement may be refined when it is. Decisions: DEC-1, DEC-2, DEC-5. -->

### Requirement: A slot can hold language-tagged strings

The toolkit metamodel SHALL offer a language-string range. A slot with that range SHALL generate a
field holding text per language tag, a SHACL property with `sh:datatype rdf:langString`, a JSON-LD
term with a language container and a TypeScript language map. A slot ranged `string` SHALL keep
generating as it does today.

#### Scenario: the generated targets of a language-string slot
- **GIVEN** a model whose class `Book` has a slot `title` with the language-string range
- **WHEN** the model is generated
- **THEN** the SHACL shape of `Book` says `sh:datatype rdf:langString` for `title`, the JSON-LD
  context gives `title` a language container, and the Python and TypeScript fields hold a map from
  language tag to text

#### Scenario: an untagged value in a language-string field
- **GIVEN** the generated `Book`
- **WHEN** it is built with a `title` that has no language tag
- **THEN** it is refused naming the slot
