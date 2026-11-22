# Q&A record: review-floors (secondary; never groomed)

Planned on 2026-11-22 by a planner subagent, which cannot ask the owner. The owner's scope (given
by the lead): behaviour-preserving tidy-ups first; classify every seed; each behaviour-changing
item split out as a no-go with its follow-up home and raised here with a recommendation.

Each question below has a recommendation, and the PLAN assumes it (the **Default** line). An answer
other than the default changes only the line of the PLAN named.

## Open questions

**OPEN-1: Where do the small behaviour fixes go?** 252-a (`_types_of` of an untyped root returns
`[]`), 252-d (`Aggregates.remove(readable)` keyword-only), 252-g3 (the `InUse` message's number),
189-n (the theme failure names the derived kind, which the `rp-generation` requirement already
says it SHALL), 189-o (the `, ` separator), 192-a (E-2 checks that the owning target's closure has
the module).
Recommendation: one SMALL follow-up EPIC, `floor-behaviour-fixes`, right after this one; each
needs a test of the new outcome and, for 252-a and 252-d, a line in the release notes (252-d is
**BREAKING** for a positional caller). 189-n is a defect against the spec, so it leads that EPIC.
Default: out of this EPIC; the issues keep these items (task 4.1).

**OPEN-2: The query-changing optimisations (252-b, 252-c, 235-n C-1).**
Recommendation: no EPIC now; they stay in their issues until a profile under load shows their
cost. 252-b needs the predicate "this class or a descendant refuses deletion" (a wrong one leaks
referrer names); 252-c's `ASK` must exclude referrers the commit removes.
Default: out (DEC-2).

**OPEN-3: The nesting guards (235-k, the D-5 race; T-4, T-5, T-6).**
Recommendation: a later EPIC on the nesting guards (an absence guard in `GuardContext`, the
`FILTER NOT EXISTS` fragment, and the three strict xfails turned into passing tests); #235 stays
open holding them.
Default: out; the three `xfail(strict=True)` stay as tripwires.

**OPEN-4: A public way to wait for a stream follower (214-f).**
Recommendation: its own SMALL EPIC (`testkit-follower-wait`): a public `EventHub.followers(tenant)`
read plus a testkit `until_following(...)`, the toolkit's own `listening`/`drained` moved to it and
the how-to's "your fixture" made writable; #214 stays open until then.
Default: out; this EPIC documents only today's outcomes (214-g).

**OPEN-5: The toolkit's TypeScript re-emitted by every target (189-v).**
Recommendation: a new issue split from #189 and its own EPIC on the generator's TypeScript (a key
naming where the toolkit's modules live, or emitting only the modules a target's classes use);
it changes the files `rp-generate` writes.
Default: out; split into a new issue at task 4.1.

**OPEN-6: The generator's structure (192-c theme-target flag and the partial artefacts, 192-d
`--project` and the per-target re-reads, 192-g's resolved-path comparison).**
Recommendation: a later EPIC on the generator's structure; #192 stays open holding them.
Default: out; this EPIC takes 192-e, f, g (names only) and h, which do not depend on them.

**OPEN-7: #215 S4's runtime half (set `rp_lifespan_started` before the start-up steps).**
Recommendation: do not change the code; the docs note (a test holding several streams enters the
lifespan itself) is enough, as the toolkit's own tests do; close #215 after stage 3.
Default: docs only (task 3.6); #215 closed at task 4.1.

**OPEN-8: #125's load items and the Redis broker stop (125-h1 to h5, 125-i3).**
Recommendation: #125 stays open as triaged on 2026-11-16 ("when a real load or a consumer needs
them"); add 125-i3 there with its reason (a restarted container gets a new port).
Default: out; 125-h6 and 125-j recorded as done in the task 4.1 comment.

**OPEN-9: Two classification calls and the risk question (R-0002).**
(a) The PLAN treats moving the declaration of `more_count` (252-e) and rewording the `in-use` slug
description (252-h3) as preserving, although both regenerate artefacts. Probed: the move adds one
term, `"more_count": {"@id": "moreCount"}`, to `collaboration/services/generated/context.jsonld`
(additive, same IRI, nothing loads that context for `InUseProblem`) and changes three manifests'
hashes; the slug text reaches the reference docs and two TypeScript goldens (design.md PD-1,
PD-16). (b) It moves `enum_meanings` and `TENANT_STATE_IRIS`
out of `rdf_persistence.schema.services.vocabulary` (not in `public-surface.json`).
(c) What could go wrong around this EPIC that the PLAN does not see: is any consumer (MWBv2)
importing `enum_meanings`, `TENANT_STATE_IRIS`, or a generated module by the slot's old place; is
another EPIC due to touch the referrer guard, the write guard or the generator's `steps.py` in the
same weeks?
Recommendation: (a) and (b) as planned; for (c), the PLAN re-checks its rows at each stage start
(RISK-6) and accepts RISK-4.
Default: as planned; on a "no" to (a), 252-e and 252-h3 move to OPEN-1's EPIC; on a "no" to (b),
192-h keeps the names in place and only the docstring changes.

## Question round parked (2026-11-22)

The owner parked the question round: the OPEN items above are unanswered. The PLAN stands
under the recommended answers; nothing is decided until the owner answers.
