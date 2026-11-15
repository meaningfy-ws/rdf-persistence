# Docs owed: message-bus

> Derives from: EPIC `message-bus` (proposal.md, "As built").

Decided by the lead, 2026-11-15: **docs were owed and are now written.** Each stage wrote the pages
its behaviour changed, and the new how-to was tested by a cold reader. The docs stage found one page
behind and brought it up to date in the archive PR.

| Page | Written in | What it says |
|---|---|---|
| `howto/event-driven.adoc` (new) | stages 3, 4 (cold-read) | Commands, handlers, observers, `bootstrap`, `kit.bus`, modelling use-case activities (P-0001), testing with `RecordingObserver`, limits |
| `howto/workflow.adoc`, `questions.adoc` | stage 2 | Transition records are kept on delete; where the record of who changed what is kept |
| `howto/adopt.adoc` | stages 1, 3 | The provenance template and an upgrading note; a link to the event-driven how-to |
| `architecture/index.adoc`, `architecture/data-flows.adoc` | stages 2 to 4 | The commit's four parts with the activity; the provenance graph; the message bus building block; a command through the bus |
| `architecture/generation.adoc` | the archive PR (docs stage) | The activity classes and their modules, the annotations `toolkit_filled` and `payload`, the rules `ACTIVITY_DIRECTION` and `TOOLKIT_FILLED`, frames for activity classes, the toolkit schema at version "2" |
| `develop/index.adoc` | stage 2 | The cost of the activity on Fuseki |

Nothing else is owed.
