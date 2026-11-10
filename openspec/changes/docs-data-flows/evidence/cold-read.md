# Cold read: architecture/data-flows.adoc (2026-11-10)

A fresh agent got only the page and eight questions. One row per question: its answer, where it
got stuck, and the fix.

| # | Question | Cold answer | Stuck point | Fix |
|---|---|---|---|---|
| 1 | Where is a book's version token? | `lib-t-…`, `B/graph`, `rp:version` (sure) | `rp:` never expanded | Terms: Prefixes row |
| 2 | Stale `If-Match` on PUT? | 409, nothing written (sure) | The Replace row did not say a stale token changes nothing | Replace row says so |
| 3 | Tenant create order; crash after the bucket? | Correct order; sweep drops orphans (sure) | Not said that orphans wait for the next start | Says "until the next start" |
| 4 | Checks from Python (`kit.session`)? | Guessing | Unclear whether body parsing and SHACL run | New table "Over HTTP or from Python" |
| 5 | Generic DELETE of a scan; what to call? | `remove_with_files` (sure); DELETE answer unknown | 405 not stated; `principal` and `version` unexplained | 405 stated; the arguments explained |
| 6 | Where is the tenant root; what maps graphs to aggregates? | `T/meta`, `T/registry` (guessing on the root) | Whether `T/meta` has a registry entry | Terms: the root has no registry entry |
| 7 | Body names a part on create? | 422 (sure) | Create row did not mention it | Create row mentions it |
| 8 | Who may list all tenants? | Guessing | Role of global roles not said | List row: global roles and grants |

Other fixes from the same read: terms defined (`kit`, principal, global roles, grants and
prohibitions, `internal` slot, file aggregate, the two version tokens of a tenant); "but the old
token" → "except the old token"; the Rules intro says which two rules are guards inside the
update; 413 assigned to the 10 000-object cap; the sweep's `Conflict` placed; "it deletes the
blob" → "the route deletes the blob"; diagram edges labelled.

Left as they are: links into other pages explain framed JSON, the Graph Store `PUT`, skolemised
blank nodes, the IRI-policy templates and `Allowed-Actions`; repeating them here would break the
single-source rule.

Second read: not run. The fixes answer each stuck point directly; the developer reviews the PR.
