"""What the lock tests share: the toy's IRIs, the edits that change it, and the lock before and after."""

from pathlib import Path

from rdf_persistence.schema.services.schema_structure import generation_view
from rdf_persistence_generation.generated.rp_generation import SchemaLock
from rdf_persistence_generation.lock import summarise

from .conftest import ROOT_SCHEMA, Breaker

BOOK = "http://purl.org/ontology/bibo/Book"
SHELF = "https://example.org/ns/library#Shelf"
ISBN = "http://purl.org/ontology/bibo/isbn"
XSD_STRING = "http://www.w3.org/2001/XMLSchema#string"

# (module, old, new) edits, each applied to the first match.
Edits = tuple[tuple[str, str, str], ...]

BOOK_SLOTS = "slots: [isbn, authors, published, genre, chapters, shelf, sequel_of, written_by]"
ISBN_DEF = "    slot_uri: bibo:isbn\n    range: string\n"
ISBN_REQUIRED: Edits = (("books.yaml", ISBN_DEF, ISBN_DEF + "    required: true\n"),)
DROP_SHELF: Edits = (("books.yaml", "slot_uri: lib:shelf\n", "slot_uri: lib:shelfMark\n"),)
NEW_PATH: Edits = (("books.yaml", "rp_path: books", "rp_path: volumes"),)


def lock_of(root: Path) -> SchemaLock:
    return summarise(generation_view(root), root.parent)


def locks_after(toy: Path, break_toy: Breaker, edits: Edits) -> tuple[SchemaLock, SchemaLock]:
    """The toy's lock before and after ``edits``."""
    before = lock_of(toy / ROOT_SCHEMA)
    for edit in edits:
        break_toy(*edit)
    return before, lock_of(toy / ROOT_SCHEMA)
