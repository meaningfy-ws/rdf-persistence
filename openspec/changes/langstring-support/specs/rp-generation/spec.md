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
- **WHEN** it is built with `titles` `["Dune"]`, `[Literal("Dune")]`,
  `[{"@value": "Dune", "@language": "not a tag!"}]` or `[{"@value": "Dune", "@language": "en\n"}]`
- **THEN** it is refused naming `titles`

### Requirement: A language-string slot keeps one range and stays out of unique keys

`rp-generate` SHALL refuse, naming the class and the slot, a `slot_usage` or an attribute that
changes a slot's range to or from `lang_string`, and a `lang_string` slot among a class's unique-key
slots.

#### Scenario: a range narrowed to a language string
- **GIVEN** a model whose class `Book` narrows the inherited `label`, ranged `string`, to
  `lang_string` in its `slot_usage`
- **WHEN** it is generated
- **THEN** `rp-generate` refuses it naming `Book` and `label`

#### Scenario: a language string in a unique key
- **GIVEN** a model whose class `Book` declares a unique key over `titles`, ranged `lang_string`
- **WHEN** it is generated
- **THEN** `rp-generate` refuses it naming `Book` and `titles`

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

#### Scenario: a number or a string written to a double slot
- **GIVEN** a plain-JSON write with `"dbl"` set to `3`, `3.0` or `"3"`, or a JSON-LD write with
  `"dbl"` set to `3` or `"3"`
- **WHEN** it is stored
- **THEN** the store holds `dbl` as an `xsd:double`, and the SHACL datatype check passes

#### Scenario: a boolean written to a double slot
- **GIVEN** a plain-JSON or JSON-LD write with `"dbl": true`
- **WHEN** it is written
- **THEN** it is refused as an invalid body naming `dbl`
