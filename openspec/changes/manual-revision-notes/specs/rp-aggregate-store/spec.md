## MODIFIED Requirements

### Requirement: RDF files load into a graph of their own

Graph loading SHALL parse a Turtle, RDF/XML, N-Triples or JSON-LD file, refuse it with the parser's
message if it does not parse, and otherwise put it into a new named graph owned by an aggregate.
Each format SHALL be named by its media type in the model. A JSON-LD file SHALL be read the way a
JSON-LD body is: a context that is not inline SHALL be refused without being fetched, and a file
whose content names a graph, or holds a relative IRI it gives no base for, SHALL be refused rather
than loaded in part.

#### Scenario: a broken file
- **WHEN** a Turtle file with a syntax error is loaded
- **THEN** loading fails with the parser's message and no graph is created

#### Scenario: a JSON-LD file that names a graph
- **WHEN** a JSON-LD file whose content sits in a graph with its own `@id` is loaded
- **THEN** loading fails saying a loaded file holds one graph, and no graph is created

#### Scenario: a JSON-LD file with a relative IRI
- **WHEN** a JSON-LD file whose node has the `@id` `book1` and no `@base` is loaded
- **THEN** loading fails saying the document must use absolute IRIs, and no graph is created

#### Scenario: a JSON-LD file with a remote context
- **WHEN** a JSON-LD file whose `@context` is a URL is loaded
- **THEN** loading fails, nothing is fetched, and no graph is created
