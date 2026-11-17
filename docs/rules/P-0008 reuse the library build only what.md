---
kind: rule
id: P-0008
type: preference
strength: default
status: active
scope:
  - activity:coding
when: a capability is needed that a mature, widely used library provides
do: reuse the library; build only what does not exist, and build it well
because: do not reinvent the wheel
source: 2026-11-16 'we want to make good implementations for things that do not exist, but we want to maximise reuse for things that exist (and are mature and used)'
added: 2026-11-17
approved: 2026-11-17
last_confirmed: 2026-11-17
private: false
---
