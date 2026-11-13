---
kind: rule
id: P-0003
type: constraint
strength: hard
status: active
scope:
  - activity:coding
when: a rebase or merge conflicts in a generated file
do: "first read the diff on both sides and find the cause (which source change: schema, generator or template, each side made); carry every source change into the sources, then take develop's version of the generated file and run make generate"
instead_of: hand-merging the generated file, or regenerating blindly and losing one side's source change
because: generated files are never edited by hand; the information lives in the sources
source: "2026-11-13: 'On a conflict in a generated file, take develop's version and run make generate; never hand-merge one.' + 'also analyse the cause for the conflict, and see the diff, to avoid losing info'"
added: 2026-11-13
approved: 2026-11-13
last_confirmed: 2026-11-13
private: false
---
