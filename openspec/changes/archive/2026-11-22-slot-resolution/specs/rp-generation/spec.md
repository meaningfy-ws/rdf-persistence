## ADDED Requirements

### Requirement: The identifier slot is never a property

The identifier slot of a class (`identifier: true`) SHALL be the node's IRI and never a statement:
no generated shape SHALL hold a property shape for it, and no slot SHALL be resolved from a
predicate to it. A slot of the application on the identifier's `slot_uri` SHALL keep its own range.

#### Scenario: a business identifier on the identifier's property
- **GIVEN** a class with the toolkit's `id` and a slot `identifier` on `dcterms:identifier`, range `string`
- **WHEN** a body gives `identifier` the value `tpl-1`
- **THEN** the shapes accept the literal, and the stored object reads back with its IRI and `tpl-1`

#### Scenario: the node of an identified class
- **WHEN** the shapes are generated
- **THEN** each identified class's shape requires an IRI node and has no property shape that asks `dcterms:identifier` for an IRI

### Requirement: A slot name resolves to the application's slot over an internal toolkit slot

Where a slot of the application has the name of a toolkit slot under another `slot_uri`, and no
toolkit class carries that toolkit slot, every reader of the schema (the runtime, the shapes, the
JSON-LD context, the component schemas) SHALL resolve the name to the application's slot, whatever
the order of the imports. The toolkit's own metamodel SHALL keep its slot.

#### Scenario: a module's own version
- **GIVEN** a module that defines `version` on `dcat:version` and imports the toolkit
- **WHEN** the root imports the module before the toolkit, or after it
- **THEN** the view and the merged schema both resolve `version` to `dcat:version`, and a value given to it is stored and read back

### Requirement: An application slot does not take the name of a carried toolkit slot

`rp-generate` SHALL refuse a slot of the application that takes the name of a toolkit slot that a
toolkit class carries, under another `slot_uri` (rule `toolkit_slot_name`). The problem SHALL name
both slots, their IRIs and the carrying toolkit classes.

#### Scenario: an application slot named graph
- **GIVEN** an application module that defines `graph` on `lib:graph`, while the toolkit's registry entry carries `graph`
- **WHEN** the developer regenerates
- **THEN** generation fails with `[toolkit_slot_name] graph:` naming both definitions
