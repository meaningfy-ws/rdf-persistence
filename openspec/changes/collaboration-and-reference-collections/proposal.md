<!-- Parents: GitHub issues #78 (reverse references), #79 (reference collections), #80 (configurable
     workflow), #81 (discussion threads); openspec/specs/rp-aggregate-store, rp-access, rp-metamodel.
     Consumer need: inputs/consumer-needs.md. -->

# EPIC: Collaboration and reference collections

> Shaped 2026-11-12 from four consumer issues. Planned 2026-11-12: the PLAN is `design.md` +
> `tasks.md`.
>
> **Note 2026-11-13 (no change to this PLAN):** the later change `message-bus` adopts this EPIC's
> `TransitionRecord` (`is_a: Activity`) as its layer-2 command `Transition`, and comments and
> membership changes as layer-2 commands. Whether transition records are deleted with their
> resource (PD-15 here) or kept as audit (`message-bus` DEC-10) is decided in that PLAN.
>
> **Re-shaped 2026-11-12 (lead's cross-EPIC decisions, applied while deriving the PLAN):**
> (1) DEC-8 (the version token on the object-level read, `UnitOfWork.version(iri)`) moved to the
> change `atomic-commit` (issue #83, its DEC-5), which reworks `UnitOfWork` anyway; the delta
> `specs/rp-aggregate-store/spec.md` was deleted from this change. (2) This EPIC **depends on
> `atomic-commit`**, delivered first: every write that touches several aggregates (a cascade, a
> transition with its record and comment, a delete with the comments and records about it) is one
> `session.transaction()`; the rabbit-hole "Atomic cascade" is solved there. (3) Stage order is now
> reverse references, collections, discussion, workflow, because a transition with a comment posts
> it into the thread. (4) Boundaries with `fine-grained-access`, `aggregate-events`,
> `schema-migrations` and `cross-aggregate-unique-keys` are stated in the No-gos. (5) While
> planning: the new reads and writes are methods of an access-aware `Collaboration` the kit opens
> for an authorised caller, not of the graph-level `Session`, which checks no access (design.md
> PD-1); DEC-2 is refined in design.md PD-12 and PD-16 (every comment, reply or not, targets the
> aggregate and a reply names its parent with `rp:repliesTo`; the body is `oa:bodyValue`; the
> record class is `rp:TransitionRecord`, a `prov:Activity` in the generated OWL only, since the
mapper writes one type). (6) After gate 1 (2026-11-12, 8/10; design.md PD-24): the specs now
say a Prohibition of `modify` refuses a transition, a comment referrer needs its target readable,
a cascade refusal names only the members the caller may read, and an aggregate stored before its
class named a workflow has no state until its first transition.

**Golden-thread parent:** GitHub issues #78, #79, #80 and #81, and the capabilities
`rp-aggregate-store` (one named graph per aggregate, guarded commits), `rp-access` (the access
check) and `rp-metamodel` (the LinkML modules, PROV-O provenance, the ODRL subset).

## Appetite

**LARGE**, delivered in four stages, each ending with tests green and merged to `develop`:
(1) reverse references, (2) reference collections, (3) discussion, (4) workflow (discussion
before workflow: a transition with a comment posts it into the thread). Three new metamodel
modules, one new access action, new reads that cross aggregate graphs, and a configuration file
format. No new container, no new store. Depends on `atomic-commit`, delivered first (stage 1
needs it only to merge after it; stages 2 to 4 use its transaction).

## Why

The toolkit stores aggregates that own their parts and follows references forward only. A
collaborative application on it also needs to ask *who points at this resource*, to group
resources it does not own, to move a resource through review states with a record of who did
what, and to discuss a resource without the right to change it. Today each application would
invent status slots, membership slots, comment classes and cross-graph SPARQL; the last is the
toolkit's job and is forbidden to consumers. A consumer (inputs/consumer-needs.md) has shaped its
next model on these four capabilities.

## Solution outline

- **Reverse references.** `collab.referrers(iri)` lists the aggregates in the tenant whose
  stored slots refer to `iri`, each with its class and slot, filtered by the caller's read access;
  those the caller may not read are only counted.
- **Reference collections.** A metamodel class for a typed set of references to aggregates of the
  same tenant, by explicit list or by a stored rule (a class and slot equalities, the same shape as
  `session.find`). Collections may contain collections. Deleting a collection keeps its members;
  an explicit cascade deletes them only if the caller may delete every one. `collections_of(iri)`
  answers where a resource is used.
- **Workflow.** A workflow is defined in a YAML file (states, initial state, transitions with the
  roles allowed and whether a comment is required) and validated against a generated model. A
  schema annotation puts an aggregate class under a workflow. The toolkit owns the current state;
  only `collab.transition(...)` changes it, and each transition is recorded as a PROV-O activity.
- **Discussion.** A comment is a W3C Web Annotation on any aggregate: text, author, time,
  audience by role, an optional reply-to, and references to other resources. Posting needs the
  `annotate` action, not `modify`. `collab.thread(iri)` returns what the caller's roles may see.
  A transition with a comment posts it into the thread.
- The version token on the object-level read moved to `atomic-commit` (re-shape above).

```python
authorised = await kit.require(authorization, tenant_id, Action.READ)
async with kit.collaboration(authorised) as collab:        # access-aware, over one session
    uses = await collab.referrers(book_iri)                 # who points at this book
    shelf = Shelf(id=..., label="Poetry", member_class="Book", had_member=[book_iri])  # saved like any root
    await collab.transition(book_iri, "in_review", if_version=v, comment="ready")
    await collab.comment(book_iri, "check chapter 3", audience=["librarian"])
    thread = await collab.thread(book_iri)
```

## Key decisions

- **DEC-1**: Collections, workflow records and comments are LinkML classes in three new metamodel
  modules (`rp_collections`, `rp_workflow`, `rp_discussion`), generated like every other model
  artefact; the workflow file is validated by a generated model, not a dict. Source: D-13, PD-24,
  AGENTS.md. Rejected: hand-written Python types for any of them.
- **DEC-2**: Reuse existing vocabularies before minting `rp:` terms. Collections are
  `prov:Collection` with `prov:hadMember` (the toolkit already speaks PROV-O); transitions are
  `prov:Activity` records (`prov:wasAssociatedWith`, `prov:startedAtTime`, `prov:used` the
  aggregate); comments are `oa:Annotation` (`oa:hasTarget`, `oa:hasBody` a `oa:TextualBody`,
  `oa:motivatedBy oa:commenting` or `oa:replying`, a reply targets the comment it answers);
  references from a comment are `dcterms:references`; the current state is `adms:status`, its
  values `skos:Concept`s of a scheme minted per workflow. `rp:` terms only where nothing fits (the
  stored rule, the audience, the transition's from and to). Rejected: ActivityStreams (`as:Note`,
  `as:inReplyTo`; a social-network vocabulary, weaker on targets than Web Annotation); SIOC
  (forum-shaped, little maintained); schema.org `ActionStatusType` (a fixed list of statuses, not
  configurable); an `rp:`-only vocabulary.
- **DEC-3**: Comments and transition records are aggregates of their own, in the tenant database,
  never parts of the aggregate they are about. So commenting does not change the target's version,
  a plain write of the target cannot rewrite its history, and reverse references find them.
  Deleting an aggregate deletes the comments that target it and its transition records; comments
  that only *reference* it stay. Rejected: storing them in the target's graph (a replace would
  overwrite them, and every comment would bump the version).
- **DEC-4**: Commenting is the ODRL action `annotate` (`odrl:annotate`: add commentary without
  modifying the asset), added to the access model's `Action` enum and granted through role
  definitions like the other actions. Rejected: reusing `read` (anyone who reads could post) or
  `modify` (reviewers could then edit what they review).
- **DEC-5**: A stored membership rule has the shape of `session.find`: a class and slot
  equalities, evaluated on every read, over the aggregates of the tenant. Rejected: stored SPARQL
  (the toolkit never runs caller-built SPARQL) and a general expression language (no need yet).
- **DEC-6**: Who may make a transition is decided by the roles listed on it, resolved from the
  caller's grants on the tenant and on the aggregate, as the access check resolves them today. The
  transition is guarded by the aggregate's version token like any write. Rejected: a separate
  permission per transition in the ODRL records (a second place to say the same thing).
- **DEC-7**: Reverse references and collection queries read across aggregate graphs inside the
  toolkit and filter by the caller's read access; what the caller may not read is counted as
  hidden, never named. Rejected: unfiltered results (leaks the existence of hidden resources by
  IRI) and silent omission (the caller could not warn that hidden uses exist).
- **DEC-8**: moved to `atomic-commit` (its DEC-5) on 2026-11-12; see the re-shape note.

## Rabbit-holes

- **Atomic cascade.** Solved by `atomic-commit`: the cascade checks every member's permission,
  then removes the collection and its members in one transaction guarded by their version tokens,
  so a refusal deletes nothing. Its per-commit root limit (500) bounds a cascade.
- **Cycles in nested collections.** Allowed; a deep read visits each collection once.
- **Rule evaluation cost.** Rule-based membership is computed on read; `collections_of` must test
  every rule-based collection of the tenant. Fine for hundreds; no index or cache in this EPIC.
- **Editing a workflow file under live data.** An aggregate whose stored state the definition no
  longer lists stays readable, reports that state, and refuses every transition until the
  definition names a transition from it again; no automatic migration (that is
  `schema-migrations`).
- **Audience and fine-grained access.** The audience of a comment is a list of roles checked by
  this capability alone; it is not property-level access (change `fine-grained-access`).
- **Mentions.** A mention is a reference whose target is a principal; it notifies nobody.

## No-gos

- **Explicitly deferred by the developer (2026-11-12):** change history in the toolkit is too much
  for now; versioning is better left to the triple store (Fluree-like). So:
  - *Named, immutable states of a tenant*: not in this EPIC; a consumer records the version tokens
    of the aggregates a process used instead.
  - *A diff between two states*: not in this EPIC; a consumer compares recorded version tokens to
    list what changed.
  - *Outputs linked to a state and resolved at that state*: not in this EPIC; outputs are ordinary
    aggregates that store the version tokens they were computed on.
- No referential integrity: a delete is never refused because of referrers; `referrers` informs.
- No notifications, mention alerts or e-mail; events are the `aggregate-events` change.
- No property-level access: a comment's audience is not `fine-grained-access`, which must later
  cover the reads `referrers`, `members`, `collections_of` and `thread`.
- No migration of stored states when a workflow file changes (`schema-migrations`).
- No unique names for collections or any other aggregate (`cross-aggregate-unique-keys`).
- No editing of comments; no reactions, attachments or rich text beyond plain text.
- No workflow editor, no workflow stored as tenant data, no timers, parallel states, quorum
  approvals or automatic transitions.
- No new generic HTTP routes; consumers route these reads and writes with the kit, as for
  `loaded_graphs`.
- No consumer term, model or code.

---

## What Changes

- `rdf_persistence/model/`: new modules `rp_collections.yaml`, `rp_workflow.yaml`,
  `rp_discussion.yaml`; `rp_access.yaml` gains the `annotate` action; generated code regenerated.
- `rdf_persistence/services/collaboration.py` (new): `Collaboration` with `referrers`, `members`,
  `collections_of`, `delete_cascade`, `comment`, `thread`, `transition`, `transitions`; the kit
  opens it with `kit.collaboration(authorised)`.
- `rdf_persistence/services/session.py`: the write guards (workflow state, collection members)
  and, in a transaction's remove, the deletion of the comments targeting the aggregate and its
  transition records.
- `rdf_persistence/services/workflows.py` (new): loading and validating workflow files; a schema
  annotation (`workflow:`) checked by the generator and read by the kit.
- `tests/fixtures/library/`: the toy library gains reference slots between aggregates, a shelf as
  a reference collection, a review workflow for books and comments.
- `docs/modules/ROOT/pages/`: how-to pages for the four capabilities; `questions.adoc` entries.

## Capabilities

### New Capabilities

- `rp-reverse-references`: list the aggregates that refer to a resource, by slot, access-filtered.
- `rp-reference-collections`: typed collections of references, by list or rule, nested, with safe
  delete and cascade, and the collections a resource belongs to.
- `rp-workflow`: workflows from a file, a toolkit-owned state, checked transitions, history as
  provenance.
- `rp-discussion`: comments on any aggregate with audience, replies and references; commenting
  needs `annotate`.

### Modified Capabilities

- `rp-access`: the access model gains the `annotate` action.

## Impact

- Public API grows (`Collaboration`, `kit.collaboration`, new generated classes, a new action);
  nothing removed. Existing role definitions keep working; `annotate` is granted only where a
  definition names it.
- Deleting an aggregate now also deletes comments and transition records about it.
- Unblocks the consumer's review, discussion and grouping features (inputs/consumer-needs.md).
