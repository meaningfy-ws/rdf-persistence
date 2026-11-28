---
kind: rule
id: P-0042
type: constraint
strength: hard
status: active
scope:
  - activity:delivery
when: a release is cut (release-please tags vX.Y.Z on develop)
do: bring main forward to the release tag automatically, in the release workflow, so main is always parked on the last release
because: main must always show the last release, never lag develop
source: "2026-11-28: 'when a release is cut we must bring main forward automatically, so that it is always parked on the last release'"
added: 2026-11-28
approved: 2026-11-28
last_confirmed: 2026-11-28
private: false
---
