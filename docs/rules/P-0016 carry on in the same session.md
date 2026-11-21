---
kind: rule
id: P-0016
type: procedure
strength: default
status: active
scope:
  - activity:delivery
when: delivering an EPIC with more than one stage
do: carry on in the same session through every stage, the docs stage and the archive instead of ending the session after each merge
because: the developer wants the epic finished end to end without restarting a session per stage
source: 2026-11-21 'continue until teh final completion of teh epic, through all the phases of the epic'; 'why dont you contonue in this session, proceed'
added: 2026-11-21
approved: 2026-11-21
last_confirmed: 2026-11-21
private: false
---
