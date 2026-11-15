# Acceptance: schema-migrations

**Verdict:** accepted by the developer on 2026-11-15 ("yes accept and archive").

**What was shown:** the final report of the epic session (session H): the three merged pull
requests (#109 the schema lock and migration files, #112 stamps and the runner at start-up, #113
restore across versions, the Fuseki proof and the docs), the challenge each stage passed, the
test status on the final head (259 container tests passed; CI all green; the local full run
passed every test it reached before the system stopped it for low memory), and the items left
open.

**Demo:** not run against a live service; the developer accepted on the report.

**Left open at acceptance:** an upstream report to rdflib for its row-hash collision (design
PD-26, RISK-12), not filed; issue #108 (a literal holding backslash-u), older than this EPIC; a
dump of the system and application databases (RISK-11).
