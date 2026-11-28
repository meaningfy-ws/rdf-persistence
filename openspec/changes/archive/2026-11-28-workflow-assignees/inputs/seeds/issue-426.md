# Assignee on entities under a workflow (one or more members)

Source: https://github.com/meaningfy-ws/rdf-persistence/issues/426 (copied verbatim 2026-11-27)

## Summary

An entity under a workflow (`UnderWorkflow`) cannot say who is to work on it next. The workflow gives states, transitions, the roles allowed to move and transition comments; the annotations give creator and contributor. Nothing names the person or people a piece of work is assigned to.

## Context

Consumer: MWB2 (rdf-persistence v0.15.0). Its conceptual-mapping list (MWB1 design, screens S-012 and S-013) has an "Assigned to" column and an assignee filter. MWB2's role queues (listings by workflow state for a role) and review batches (collections of entities moved together) route work to a role, never to a person. Decision S8-1 of MWB2's model review (2026-11-27): the assignee belongs to the toolkit, generic for every workflowed entity, not drawn in MWB2's model.

## Expected behaviour / proposed capability

- An optional, multivalued assignee on any `UnderWorkflow` entity: zero, one or more members of the entity's tenant.
- The workflow definition says whether it applies and who may assign (for example by role, like `transition_roles`), and whether a transition may set or clear it.
- Assigning and unassigning are recorded like other workflow changes (who, when), and the generic listing filters on it (`?assignee=<member>`), so a person's own queue is one listing.
- An assignee must be a member with access to the entity; removing a member's access leaves no dangling assignment, or the toolkit names what to do.

## Why it belongs in rdf-persistence

Assignment is part of the workflow, which the toolkit owns, and it applies to every workflowed type, not only MWB2's conceptual mappings. A consumer adding its own slot per class would repeat it in every model and could not tie it to the workflow's roles or history.

## Impact on the consumer

MWB2 offers the assignee column and filter on the CM list once this lands; until then it shows role queues only. Nothing is drawn in MWB2's model meanwhile.

