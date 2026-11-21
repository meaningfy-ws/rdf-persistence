<!-- Secondary input, never groomed: the owner's answers to the shaping round, 2026-11-21.
     proposal.md (DEC-1 to DEC-8) and design.md carry them. -->

# Q&A: uml-roles-and-workflows, 2026-11-21

Scope from the owner's brief: parts 2 (role definitions) and 3 (workflows) of #245; part 1
(`module_kind` per package) is fixed separately and left out. Stage 1 roles, stage 2 workflows.
The probe the round relied on is `probe.md`.

| Id | Question | Owner's answer |
|---|---|---|
| Q-1 | What is one workflow in UML? (The probed model has no StateMachine element; the states are grouped only by a Statechart diagram named like the class's `workflow` tag.) | One Statechart diagram is one workflow. |
| Q-2 | Where does the workflow's IRI `id` come from? | "option1 could be a backup plan, but the EA must give IRIs otherwise the model is wrong." |
| Q-3 | Must a transition's roles be drawn? | Strict: every role a transition names must be a drawn `rp:RoleDefinition` object, otherwise the run fails. |
| Q-4 | Risk: constructs the probe did not see (final, choice or junction nodes, guards, other Objects, a StateMachine element). | Fail the run naming the element (today's `no_rule`). |

## Planner's reading of Q-2 (owner may overrule)

The converter gives every other element its IRI from its EA name, `pfx:Local` expanded through the
prefixes file (`uml/naming.py`). So the EA model gives the workflow's IRI the same way: the
Statechart diagram is named `pfx:local` (for example `lib:loan`); the IRI is the expansion and
`workflow_name` is `local`, which the class's `workflow` tag names. The backup (option 1): a diagram
with a plain name gets `schema_base` + `workflows/<name>`, and the report says so with a line of
its own (`derived-iri`), flagging the model as incomplete rather than failing the run. Recorded as
DEC-4.
