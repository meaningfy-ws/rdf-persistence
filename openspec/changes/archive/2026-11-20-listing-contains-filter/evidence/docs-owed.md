# Docs owed: listing-contains-filter

The change adds user-facing behaviour (a listing filter, a `find` value, an `offset` bound). Every
page it owes ships in its own PR (#216), so no separate docs stage is needed:

| Page | What it says now |
|---|---|
| `architecture/api.adoc#serving` | listings take `<slot>~=<text>`; the OpenAPI shows `<slot>~` per text slot |
| `architecture/index.adoc` | the router lists with equality and contains filters |
| `reference/http-api.adoc#listings` | the `<slot>~=<text>` row; `offset` up to 2^53 − 1 |
| `user-manual/files.adoc` | `find` takes `Contains(text=…)` |
| `partials/reference/public-api.adoc` (generated) | `Contains` in the public API |

No how-to or tutorial page changed, so no cold reader is owed.
