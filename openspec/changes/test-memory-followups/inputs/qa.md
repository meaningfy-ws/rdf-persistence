# Q&A record (secondary, never groomed)

## Round 1, 2026-11-25 — open for the developer (shaped on defaults; the developer asked for speed)

| # | Question (recommendation) | Answer | Becomes |
|---|---|---|---|
| Q1 | Where does the schema reuse live? (Recommended: a process-wide cache for the service kit only, keyed by resolved path and modification time, beside an unchanged `load_schema`; alternatives: cache inside `load_schema`, which the generator would share and modify; or `install_service` accepting a `SchemaView`) | open | DEC-2 |
| Q2 | May DEC-1 change the dependency style of `auth.py` and `sse.py` to the default-argument form `router.py` already uses? (Recommended: yes) | open | DEC-1 |
| Q3 | DEC-8's measurement waits for the paused sessions to run on the merged code: keep it in this EPIC as its last task, not blocking the PR of the fixes? (Recommended: yes) | open | DEC-4 |
| Q4 | Risks (R-0002): what outside could change (a FastAPI or linkml release, #4284 fixed upstream), who is hurt if a shared view is modified (every test sharing it), what we accept | derived from context, open for review | RISK-1 to RISK-3 |
| Q5 | Appetite SMALL | open | Appetite |
