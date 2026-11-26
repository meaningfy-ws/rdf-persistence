# DEC-8 measurement (agent-test-control), per test-memory-followups PD-5

Range: Langfuse observations 2026-11-25T21:00Z to 2026-11-26T14:55:53Z. The upper bound is
`ba0737e76c8396a1`, the first Bash command naming `plan-test-memory-followups` in session ec3d87f9;
this EPIC's own work starts there and is left out.

**Window (as PD-5 defines it):** session `3ac19932` is the first epic session in range (first
`Subagent:` span `09d9fd53ed075a2b`, 21:12:10Z). It was active from about 21:07Z to 21:45Z, its
`check-all` included. In that time five other rdf-persistence sessions had spans: `6de686e6`,
`49f9e78d`, `7a038b98`, `fdacd944` and `6aa40a34`, so the "at least two others" condition holds.
The window has only one builder gate, so the table also gives the result over every
rdf-persistence epic session in range (`3ac19932`, `6de686e6`, and `ec3d87f9` up to the cut-off).

| Target | Measured value | Sessions and observation ids (a few) | Met or missed |
|---|---|---|---|
| (1) Builder task gate: median latency of gate commands containing `make test-changed`, under a `Subagent:` span, < 3 min | **Window:** 18.6 min (n=1). **All epic sessions:** median **6.0 min** (n=6: 4.7, 4.9, 5.2, 6.8, 10.5, 18.6 min) | 6de686e6 `a61e0393f18312cf` (18.6 min, background); ec3d87f9 `f33f23430b30fc5f` (4.7), `331aeec78377054e` (4.9), `994af0daa4e69f9b` (5.2), `7aa50e9efa05012b` (6.8), `00e2a975717a094c` (10.5) | **missed** |
| (2) `check-all` net time: latency minus the N of its `test queue: waited Ns` lines, < 15 min | **Window:** 7.2 and 8.4 min (n=2). **All epic sessions:** 6.9 to 8.9 min, max **8.9 min** (n=9 complete runs) | 3ac19932 `e00507e86bbf49e4` (2131 s − 1701 s = 7.2 min); 6de686e6 `0369c8380029a767` (2254 − 1752 = 8.4), `299217a0bbdb6ce1` (968 − 533 = 7.3), `2e1bd2a3d8123b3d` (2848 − 2368 = 8.0); ec3d87f9 `07dba64d8dc9eab0` (627 − 215 = 6.9), `a57479bcebaa6a44` (883 − 349 = 8.9), `7228a96ce24c7673` (485 − 0 = 8.1), `4012c0a7c101d00b` (570 − 132 = 7.3) | **met** |
| (3) Builder waiting share: gate-command latency (queue wait included) over the `Subagent:` span's latency, < 10 % for every builder | **Window:** one fixer; its share cannot be computed (the span `a93f56aa678f7955` closed 5 s after it started the gate in the background, and the gate ran 1115 s). **All epic sessions:** 84 %, 89 %, 43 %, 34 %, 74 % for the five builders and fixers that ran a gate | ec3d87f9 `fb5e9927533472cc` Build 1.1+1.2 (355/422 s = 84 %), `d341f2f2f83e8461` Build 1.3+1.4 (632/710 = 89 %), `0e425531fdf7af60` Build stage 2 (346/807 = 43 %), `66b90239b3c84a8b` Build stage 3 (354/1039 = 34 %), `d81278e45ea7d4b2` Fix F1-F8 (466/628 = 74 %) | **missed** |

## Method, caveats and counts

- **Discovery.** Langfuse records Claude Code sessions as `Conversational Turn` spans, whose
  metadata holds `cwd`. Of the 15 sessions in range, 7 have a `cwd` under rdf-persistence:
  3ac19932, 6de686e6, 49f9e78d, 7a038b98, fdacd944, 6aa40a34 and ec3d87f9. A further session,
  `9c603e22`, committed test-memory-followups planning at 21:00Z and is excluded. Only 3ac19932,
  6de686e6 and ec3d87f9 have `Subagent:` spans. A subagent's Bash observations have the
  `Subagent:` span as `parentObservationId`.
- **Gate commands.** I filtered `Tool: Bash` observations on input containing each of the four
  target names. The rdf-persistence subagents ran 6 test-changed gates and 8 check-quality-only
  gates, and no `make test-fast`. No reviewer span ran a gate.
- **Background runs.** Nearly every check-all, and 4 of the 6 builder test-changed gates, ran
  with `run_in_background`, so Langfuse records a latency under 1 s for them. I timed them
  consistently:
  - Foreground commands: the Langfuse latency.
  - Background commands: Langfuse start time to the completion time of the task's `.output`
    file. This agrees within 0.1 s with the command's own printed `real`/`time` where it
    printed one (b8squ132z 292.3 s, b4i5w6u1f 314.2 s).
  - check-all: the wall time the command printed (`real`, `wall`, or `check-all exit 0 Ns`).
- **Where the queue-wait figures come from.** Langfuse holds the `test queue: waited` lines for
  3ac19932 and for 6de686e6's first two runs. For the rest I read them from the local logs the
  runs wrote: `.worktrees/activity-iri-policy/temp/check-all*.log` and this session's
  `scratchpad/checkall-*.log`.
- **check-all counts.** Of 11 check-all commands in range, 9 completed and were measured.
  `4ed6993052bd79c8` was killed. `ffa83a5379fa3a77` exited 2 after 287 s, with test-unit failing.
- **Why the builder gates are slow.** Every builder `make test-changed` fell back to the full fast
  lane: about 10,100 tests in 4 min, with "Fast tests passed", and the reason "tests/queue.py:
  shared test infrastructure". The test-control-testkit stages edited exactly that shared test
  infrastructure. Two gates also failed (exit 2), so (1) and (3) partly reflect red runs. The
  18.6 min gate in 6de686e6 started at 21:14Z, when three check-all runs were queued.
- **Concurrency.** The only epic session with builders, ec3d87f9 from 09:40Z to 11:16Z, had no
  other rdf-persistence session running. Its queue waits (95 to 499 s) came from mapping-workbench-v2
  sessions (`v2-06-review`, `v2-07-cm`, `v2-04-e2e`). So the run that measures builders was not
  the "three concurrent rdf-persistence sessions" case PD-5 describes.
- **Waiting share.** A subagent span ends when the subagent returns. a93f56aa returned before its
  background gate finished, so its share cannot be computed. The W1-W3 fixer `6630acf17f793cbd`
  (41 s) ran no gate, which gives 0 %. Shares count check-quality-only runs as gate time,
  as PD-5's gate definition says.
