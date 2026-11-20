# Acceptance: listing-contains-filter

SMALL appetite: the demo is offered and may be skipped. It was run, at the developer's request to
close every open item, on 2026-11-20 by the lead, through the HTTP API of the toy service (the
in-memory store), on the branch head after the rebase.

## What was shown

Shelf: Dune (fiction, Herbert), Children of Dune (nonfiction, Herbert), Emma (fiction, Austen),
Ulysses (fiction, Joyce and Herbert).

| Request | Answer |
|---|---|
| `GET books?label~=DUNE` | 200, Dune and Children of Dune, total 2 |
| `GET books?label~=dune&genre=fiction` | 200, Dune, total 1 |
| `GET books?authors~=e` | 200, all four books, each once, total 4 (Ulysses holds two matching authors) |
| `GET books?authors~=e&offset=3` | 200, Ulysses, total 4 (no duplicate row shifts the page) |
| `GET books?label~=u&sort=label&limit=1&offset=1` | 200, Dune, total 3 |
| `GET books?published~=19` | 400 `bad-query` (a date is not text) |
| `GET books?label~=` | 400 `bad-query` (empty text) |
| `GET books?label~="} ; DROP ALL ; #` | 200, nothing, total 0 (the text stays a literal) |
| `GET books?offset=9223372036854775758` | 400 `bad-query` (D-9) |
| `session.find(Book, label=Contains(text="DUNE"))` | 2 IRIs |

On Fuseki, the same behaviour is covered by `make test-containers` (IT-1, IT-2, the D-7 and D-10
tests).

## Verdict

Accepted by the developer on 2026-11-20 ("I accept, sign off"), together with the sign-off of the
two scenarios added by D-13 ("an offset beyond the bound", "a substring of a slot that holds no
text").
