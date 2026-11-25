# Q&A record (secondary, never groomed)

## Round 1, 2026-11-25 (owner: Eugeniu Costetchi)

| # | Question (recommendation) | Answer | Becomes |
|---|---|---|---|
| 1 | Who owns what? (two linked changes: here first, then skillery's `project-setup` template and `test-strategy`, D-12 style) | Yes; open a skillery issue documenting in detail what must be done | DEC-1 |
| 2 | Scope of the queue? (one lock for all repositories on the machine) | "I like the lock" | DEC-2 |
| 3 | Workers under the lock? (`-n auto`, `PYTEST_N` overrides) | Yes, but 17 on this machine (20 cores) | DEC-3 |
| 4 | testmon behind a spike gate? | No gate: "I like testmon, let's do it" | DEC-4 |
| 5 | Who seeds the testmon data? (the lead, once per worktree at stage start, queued, no coverage) | Yes, ideally in a parallel sub-process | DEC-5 |
| 6 | How is "builders never run the full lanes" enforced? (docs and briefs here, a hook in skillery) | Do whatever is needed; the skillery issue well documented; meanwhile guards in `AGENTS.md` | DEC-6 |
| 7 | Where does the documentation for agents go? (`develop/testing.adoc` section, `develop/agents.adoc` briefs, `AGENTS.md` gate table, `questions.adoc` entry) | Yes | DEC-7 |
| 8 | Success measures (Langfuse, at least three sessions at once: builder task gate p50 ≤ 3 min; `check-all` ≤ 15 min excluding queue wait; no builder over 10 % of its wall time waiting on gates) | Yes | DEC-8 |
| 9 | Risks: what outside could change, who is hurt and how badly, what we do, what we accept (R-0002) | Yes, derive them from the context | RISK-1 to RISK-5 (design.md) |
| 10 | Appetite (MEDIUM here, SMALL for the skillery follow-up) | Not contested: as recommended | Appetite |

## Round 2, 2026-11-25 (owner), after the memory investigation (`inputs/memory.md`)

| # | Question (recommendation) | Answer | Becomes |
|---|---|---|---|
| 13 | The consumer application has the same leak through the toolkit's `install_service`: ship the release in the public testkit with an opt-in pytest plugin (recommended), or keep it private? | "yes, put it in the testkit / rdf-persistence project; and then we will see what we do for other projects" | DEC-10 |
| 12 | With the second measurement: clear the caches after every test (not only per module)? Reuse one schema load per process? | "finish shaping, plan and proceed with implementation immediately, with subagents": caches cleared after every test (PD-9); schema reuse needs a library change (the kit loads and modifies its own view), so it is a follow-up change, with the upstream report (DEC-9) | PD-9, DEC-9 |
| 11 | Fold mechanisms 1 (release caches at module boundaries) and 2 (worker count bounded by free memory) into this change; lazy import-time objects and fewer SchemaViews as a separate change | "yes include 1 and 2; is enough": no further memory change for now | DEC-9 |
