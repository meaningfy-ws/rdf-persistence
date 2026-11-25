# Acceptance: generator-module-cycles

**Verdict:** accepted by the developer, 2026-11-25, after the demo below.

**What was shown** (the lead ran it on `develop` after #358 and #368, with the integration tests'
model builder and the real CLIs):

1. Two UML packages whose classes refer to each other (`Book` in `books`, `Shelf` in `shelves`):
   `rp-uml2linkml` exit 0, `app_books.yaml` and `app_shelves.yaml` each importing the other, no
   report line; `rp-generate` exit 0; the package `__init__.py` binds `Shelf` and `Book` with
   `setattr` and rebuilds both classes; `app_books.py` imports `Shelf` under `if _TYPE_CHECKING:`;
   importing `app_shelves` then `app_books` builds a `Book` with its shelf and a `Shelf` with its
   featured book.
2. Classes inheriting both ways between the two packages: the conversion succeeds; `rp-generate`
   exits 1 at the `python` step naming `app_books`, `app_shelves`, `app_books.Book` and
   `app_shelves.Shelf`, with the two fixes; no generated folder is written.

RISK-1 (the consumer's model) was checked before the merge of stage 2: design.md D-7.
