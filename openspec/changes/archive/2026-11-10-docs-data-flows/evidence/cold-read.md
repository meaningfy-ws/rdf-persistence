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

Second read: below.

# Second cold read (2026-11-10, after the diagrams)

A new fresh agent got only the page and ten new questions, and checked each diagram against the
text. Seven answers sure, two guessing, one sure with a gap.

| # | Question | Stuck point | Fix |
|---|---|---|---|
| 1 | Path from browser to store | Create diagram skipped DocumentApi | Message names DocumentApi |
| 2 | Access record and its links | Diagram said it names the bucket; table only the database | Both say the bucket has the database's name |
| 3 | Two creates of one IRI | `alt` without `else`: 201 seemed to follow 409 | `alt` / `else stored` |
| 4 | An uncommitted loaded graph | "grace period" defined later | Terms: load marker, grace period |
| 5 | Crash during tenant delete | **Error in the page:** "the next DELETE" finishes it, yet the gate answers 404 for a deleting tenant | Only the next start-up sweep finishes it (checked in code: `finish_deletion` is called by `Tenancy.delete` and `sweep` only) |
| 6 | Replace without If-Match | Intro called the lock a guard inside the update | Intro: presence checked first, version match inside |
| 7 | Python write: SHACL, version | Pydantic vs SHACL unclear | Says what pydantic checks and what it does not |
| 8 | Failed commit after upload | Failure of the cleanup delete not said | Diagram: the blob becomes an orphan for the sweep |
| 9 | Tokens for rename and replace root | Read row named only Record-ETag; rename changes both | Read row names both; rename row says both change |
| 10 | Stale If-Match in the flowchart | Agrees with the table | Flowchart scoped to aggregate writes |

Also fixed: the files diagram now goes through the kit to the stores; "every route" became
"every generic route"; the sweep's `Conflict` has its own row (a Python call, not 404); a
"Creating" note says it is not a stored state; rename is two writes, not one guarded update, and
why it needs `modify`; "honourable" became "can be checked"; the dashed box is named; the tenant
root's loaded graphs and #73 explained.

Left as they are: terms explained on linked pages (skolemised blank nodes, Graph Store PUT, framed
JSON, `Allowed-Actions`, the `{deployment}` slug, `UnitOfWork`, the Store port), by the
single-source rule.

All ten diagrams render (mermaid CLI 12; the site loads mermaid 10). `make check-docs` passed;
`make build-docs` built with no warnings.
