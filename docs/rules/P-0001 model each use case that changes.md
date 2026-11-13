---
kind: rule
id: P-0001
type: constraint
strength: hard
status: active
scope:
  - activity:modelling
when: modelling a domain whose application reacts to or requests changes
do: model each use case that changes state as an optional LinkML Activity subclass (data only, preferably specialising a standard toolkit command) in a sibling module <domain>_activities.yaml that imports the static module; the static module never imports it; model no event classes (the events are the toolkit's fixed PROV set)
because: commands and events are contracts generated like every other model artefact, PROV-O already models them, and the import direction keeps the stored model free of process concerns
source: "2026-11-13: 'we must model also actions/events side by side with the model ... just the linkml, and then this must be a rule'; 'events fixed prov set ... i agree with what you said above, go ahead'"
added: 2026-11-13
approved: 2026-11-13
last_confirmed: 2026-11-13
private: false
---
