---
kind: rule
id: P-0016
type: procedure
strength: default
status: active
scope:
  - activity:delivery
when: delivering an EPIC with more than one stage
do: carry on through every stage, the docs stage and the archive until the epic ends, but end the session at each stage merge; the next session starts from the hand-over note
because: the developer wants the epic finished end to end, and a fresh session per stage keeps each one lean (skillery 3.22.0)
source: "2026-11-22 'The epic continues to its end, but each stage merge ends the session; the next starts from the hand-over note.' (#281, accepted)"
added: 2026-11-21
approved: 2026-11-21
last_confirmed: 2026-11-21
private: false
---
