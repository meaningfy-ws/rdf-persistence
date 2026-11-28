## ADDED Requirements

<!-- langstring-support. Decisions: DEC-1, DEC-2, DEC-5, DEC-8; PD-8 to PD-13 (design.md). -->

### Requirement: A slot can hold language-tagged strings

The toolkit metamodel SHALL offer a language-string range, `lang_string`. A slot with that range
SHALL generate a Python field holding rdflib `Literal`s that each carry a language tag, kept as
given (a list of them when the slot is multivalued); a SHACL property with
`sh:datatype rdf:langString`; a JSON-LD term that carries no `@type`; and a TypeScript type of JSON-LD
value objects `{ "@value": string; "@language": string }`. The field SHALL accept a tagged `Literal`
or a value object and SHALL refuse, naming the field, a value with no language tag or a malformed
one. A slot ranged `string` SHALL keep generating as it does today.

#### Scenario: the generated targets of a language-string slot
- **GIVEN** a model whose class `Book` has a multivalued slot `titles` with the language-string range
- **WHEN** the model is generated
- **THEN** the SHACL shape of `Book` says `sh:datatype rdf:langString` for `titles`, its JSON-LD
  term has no `@type`, the Python field holds `Literal("Dune", lang="en")`, and the TypeScript
  field holds `{"@value": "Dune", "@language": "en"}`

#### Scenario: a value object becomes a tagged literal
- **GIVEN** the generated `Book`
- **WHEN** it is built with `titles` `[{"@value": "Dune", "@language": "EN"}]` and dumped as JSON
- **THEN** the field holds `Literal("Dune", lang="EN")` and the JSON is the same value object

#### Scenario: an untagged value in a language-string field
- **GIVEN** the generated `Book`
- **WHEN** it is built with `titles` `["Dune"]`, `[Literal("Dune")]` or
  `[{"@value": "Dune", "@language": "not a tag!"}]`
- **THEN** it is refused naming `titles`

### Requirement: A decimal number has one form in JSON and TypeScript

A slot ranged `decimal` or `float` SHALL be read as a JSON string holding its lexical form, and its
TypeScript and OpenAPI types SHALL say string; a slot ranged `double` SHALL be read as a JSON number
under its own JSON name, and its TypeScript and OpenAPI types SHALL say number. A write SHALL keep
each slot's datatype whether the client sends a number or a string.

#### Scenario: reading the three ranges
- **GIVEN** a stored aggregate with `dec` `"1.5"^^xsd:decimal`, `flt` `"1.5"^^xsd:float` and `dbl`
  `"1.5"^^xsd:double`
- **WHEN** it is read as plain JSON and as JSON-LD
- **THEN** both show `"dec": "1.5"`, `"flt": "1.5"` and `"dbl": 1.5`, and the generated TypeScript
  says `dec: string`, `flt: string`, `dbl: number`

#### Scenario: a whole number written to a double slot
- **GIVEN** a plain-JSON write with `"dbl": 3`
- **WHEN** it is stored
- **THEN** the store holds `dbl` as an `xsd:double`, and the SHACL datatype check passes
