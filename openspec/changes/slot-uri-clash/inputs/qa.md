# Q&A record: slot-uri-clash (secondary; never groomed)

Two rounds with the owner, 2026-11-25 (TINY: at most two). Every answer was the recommended one
unless marked.

## Round 1

| Question | Answer | → |
|---|---|---|
| Two slots on one IRI: refuse (hard check, exit 1) or warn? | refuse | DEC-1 |
| Which slot is exempt? | any slot with `identifier: true` (written as `@id`, never a predicate) | DEC-2 |
| Which slots are compared? | all slots and class attributes of the target's import closure, toolkit included, by expanded IRI | DEC-3 |
| Risk: a consumer model with a clash stops generating | accept, with a `CHANGELOG.md` *Changed* entry and a message that names both slots, the IRI and the fix | RISK-1 |

## Round 2

| Question | Answer | → |
|---|---|---|
| Which scenarios must the EPIC prove? | the #206 case refused; `id` beside `identifier` passes; a default-prefix clash and a class-attribute clash refused. Not chosen: "one slot refined by `slot_usage` is no clash" (the check counts slot names, so it holds by construction; no test owed) | spec delta, task 1.1 |
| Which targets does the check run on? | every target | DEC-4 |

## After the gate

| Question | Answer | → |
|---|---|---|
| Accept the PLAN at 8.85/10 with the five gaps fixed, or a third run? | accept | design.md D-2 |
| Sign off the three spec scenarios? | signed off | evidence/clarity-gate.md |
| CHANGELOG section: Changed (round 1) or BREAKING (house style)? | BREAKING | design.md D-1 |
