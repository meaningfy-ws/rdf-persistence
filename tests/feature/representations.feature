Feature: A book in the RDF serialisation a client asks for
  As a team that builds on the library service
  I want to read a book in the RDF format my tools speak
  So that every format tells me the same thing about the book

  Background:
    Given Ada's library holds a book

  # spec: rp-service-api / the same book in every RDF serialisation
  Scenario Outline: The same book in every RDF serialisation
    When Ada reads the book as <representation>
    Then the book is served as <representation>
    And it describes the same triples as the book read as plain JSON

    Examples:
      | representation |
      | JSON-LD        |
      | Turtle         |
      | N-Triples      |
      | N-Quads        |
      | TriG           |
      | RDF/XML        |

  # spec: rp-service-api / N-Quads name the aggregate's graph
  Scenario Outline: A book as a dataset is shown in its own graph
    When Ada reads the book as <representation>
    Then every statement is in the book's graph
    And none of them is about that graph

    Examples:
      | representation |
      | N-Quads        |
      | TriG           |

  # spec: rp-service-api / a listing in N-Quads
  Scenario: A listing cannot be served as N-Quads
    When Ada lists the books as N-Quads
    Then the answer is 406 with a problem response
