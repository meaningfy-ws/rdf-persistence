> Derives from: EPIC `collaboration-and-reference-collections` (proposal.md, issues #78 to #81).
> Implements DEC-1 to DEC-7 (DEC-8 moved to `atomic-commit`). Type: Implementation.
> Depends on: `atomic-commit` (issue #83), merged into `develop` before stage 1's PR.

## Context

Checked at `develop` `7f28333` (2026-11-12) and against the PLAN of `atomic-commit`.

- `Session` (`services/session.py`) reads and writes whole graphs of one tenant database for one
  principal and **checks no access**: the caller gates (`kit.require`, `kit.require_aggregate`,
  the generic router's `Gate`). It knows no schema; `find` uses an optional `Listings`.
- After `atomic-commit`, every write goes through `Session.transaction()`: `Transaction.add_graph`,
  `replace_graph`, `remove` run the pre-checks (`_graph`, `_check_commit`, `_stored`), collect a
  guard fragment and operation fragments (`guards: list[str]`, `operations: list[str]`, its PD-6)
  and send one marker-guarded update; `Session.add_graph/replace_graph/remove` and
  `UnitOfWork.commit()` are transactions; `Conflict.iris` names the culprits. The root limit
  (500, `CommitTooLarge`) is enforced by `UnitOfWork.commit` only (its PD-8), not by `Transaction`.
- Access (`services/access.py`): `AccessRules.require/may(caller: VerifiedCaller, access:
  CallerAccess, target_iri, action)`. Every action but `read` implies `read` (`_IMPLY_READ`); a
  matching Prohibition wins (`_prohibited`, private). `Authorised`
  (`model/service/rp_service.yaml`) carries `principal`, `caller_access`, `checked_target`, not
  the caller's `global_roles`.
- LinkML slots share one namespace across the imports closure: `rp_access.yaml` already has
  `target` (`odrl:target`), `rp_service.yaml` has `items`, `state` is `rp_tenancy`'s. A consumer
  that imports `rp.yaml` shares the namespace too, so new metamodel slots get qualified names.
- Every aggregate graph has an `rp:Aggregate` registry entry `?g rp:ownedBy ?root` in `T/registry`;
  the tenant root lives in `T/meta` with no entry. Aggregate graphs hold only what the mapper or
  the generic API (shape-validated) wrote, so every predicate in them is a slot's `slot_uri`.
- The listing (`services/listing.py`) turns `Filter(slot, value)` into typed `Condition`s;
  `match_patterns` renders them; `find(cls, **equals)` pages through `?root a $class` exactly.
- Annotations the toolkit reads are the enum `RpAnnotation` (`model/rp_core.yaml`), checked by
  `generation/checks/hard.py`; toolkit schemas are exempt from the class rules (PD-23 there).
  `served_roots` serves every concrete aggregate root with an `rp_path` outside the system
  database; `iri_types` takes every concrete root of the view, the metamodel's included. No check
  refuses two classes with one `rp_path` (checked: `hard.py`, `boundary.py`, `iris.py`).
- The kit builds its models with `generated_models_of(generated, rp_access, rp_core, rp_tenancy)`
  (`entrypoints/kit.py`). Role definitions come from a YAML file validated by the generated
  `RoleDefinition` (`load_role_definitions`), the pattern a workflow file follows.

## Goals / Non-Goals

**Goals:** the requirements of `specs/rp-reverse-references`, `rp-reference-collections`,
`rp-discussion`, `rp-workflow` and `rp-access` of this change, in four stages, one PR each:
(1) reverse references, (2) reference collections, (3) discussion, (4) workflow.

**Non-goals:** the EPIC's No-gos; paging of `referrers`, `members`, `thread`; deleting or editing
one comment; HTTP routes; a workflow or comments on the tenant root; anything `atomic-commit`
delivers.

## Decisions

### Shared (stage 1)

- **PD-1** (DEC-7, DEC-4): The new reads and writes are methods of **`Collaboration`**
  (`services/collaboration.py`), not of `Session`, which stays access-free and schema-free. A
  `Collaboration` holds a `Session`, the kit's `Mapper` and `GeneratedModels`, `Listings`,
  `AccessRules`, `Workflows` (stage 4), and the caller (`VerifiedCaller`, `CallerAccess`). The kit
  opens it: `kit.collaboration(authorised: Authorised) -> AbstractAsyncContextManager[Collaboration]`,
  over `tenancy.tenant_session(authorised.caller_access.tenant, Principal(id=authorised.principal))`.
  `Authorised` gains `global_roles` (the existing `rp_service` slot), filled by
  `Gate.aggregate_access` and `kit.require` from the `VerifiedCaller`. The kit's models become
  `generated_models_of(generated, rp_access, rp_core, rp_tenancy, rp_collections, rp_discussion,
  rp_workflow)` (each module added in its stage). A schema that does not import a module: the
  kit and `referrers` work; a method that needs the module's classes (`members`,
  `collections_of`, `delete_cascade`; `comment`, `thread`; `transition`, `transitions`) raises
  `LookupError` naming the module; the write guards skip what the view lacks. Rejected: access
  arguments on `Session`; the EPIC sketch's `session.referrers` (re-shape note (5)).
- **PD-2** (DEC-1, models not dicts): result shapes are generated, in `rp_service.yaml`:
  `Referrer` (`referrer` uri, `referrer_class` string, `referrer_slot` string, all required),
  `ReferrerList` (`referrers` → `Referrer`, multivalued, inlined; `hidden_count` integer,
  required), `MemberList` (`member_iris` uri multivalued; `hidden_count`), and `AggregateHead`
  (`head_iri` uri, `head_types` uri multivalued, `head_version` string), the answer of
  `Session.heads` (PD-6).
- **PD-3** (DEC-7): `referrers(iri, *, class_name=None, slot=None) -> ReferrerList`.
  1. `iris.is_aggregate(tenant, iri)` else `InvalidIri`; `rules.require(caller, access, iri, READ)`.
  2. One `SELECT DISTINCT ?referrer ?class ?subject_class ?p` (template `READ_REFERRERS`):
     ```sparql
     SELECT DISTINCT ?referrer ?class ?subject_class ?p WHERE {
       GRAPH $registry { ?g $p_kind $aggregate ; $p_owned_by ?referrer }
       GRAPH ?g { ?s ?p $iri . ?referrer a ?class . OPTIONAL { ?s a ?subject_class } }
       FILTER (?s != ?g && ?p != rdf:type $narrow)
       FILTER NOT EXISTS { VALUES (?dt ?dl) { $dependents } FILTER (?p = ?dl && ?class = ?dt) }
     }
     ```
     `$narrow` is empty, or `&& ?class = $class && ?p = $p_slot` parts built with `term`.
     `$dependents` is the pair list of PD-15 (empty in stage 1, `(oa:Annotation oa:hasTarget)`
     from stage 3, `(rp:TransitionRecord prov:used)` from stage 4): a link is dropped only when
     the referrer has that type, so a consumer slot using `prov:used` still counts.
  3. Names: `?class` → the schema class whose `get_uri(expand=True)` equals it (a dict built once
     from the view); `?p` → the slot of `?subject_class` (or of `?class` when the subject is the
     root or untyped) among its induced slots with that `slot_uri`; unknown → the IRI text.
     `class_name` must name a class of the view, `slot` a slot of the view, else `BadQuery`.
  4. Filter: a row is listed when `rules.may(caller, access, referrer, READ)`; from stage 3 a
     **comment** referrer is listed only when the caller may read the comment's target and the
     comment is visible in that target's thread (PD-14: audience against
     `rules.roles(caller, access, target)`, parent visible). `hidden_count` = the number of
     distinct referrer IRIs not listed. Items sorted by (referrer, slot).
  The tenant root is never a referrer (no registry entry); a self-reference is listed.
- **PD-4**: fixture: `books.yaml` gains `Shelf` (root, `rp_path: shelves`, `Described`), slots
  `shelf` (Book → Shelf), `sequel_of` (Book → Book) and `about` (Note → Book), each a reference
  (not `owned`). `partial.yaml`'s own `Shelf` is another schema and stays.

### Reference collections (stage 2)

- **PD-5** (DEC-1, DEC-2, DEC-5): new module `model/rp_collections.yaml` (no `module_kind`, so a
  domain module may import it), imported by `rp.yaml`:
  - `ReferenceCollection` mixin, `class_uri: prov:Collection`, slots `member_class`
    (`rp:memberClass`, string, required: the schema name of the member class), `had_member`
    (`prov:hadMember`, uri, multivalued; named after the PROV property, as `was_associated_with`),
    `membership_rule` (`rp:membershipRule`, range `MembershipRule`, `owned: true`).
  - `MembershipRule` (`rp:MembershipRule`, owned part, no identifier, so a skolem IRI):
    `rule_equalities` (`rp:ruleEquality`, range `SlotEquality`, owned, multivalued). A rule with
    no equality means "every aggregate of `member_class`".
  - `SlotEquality` (`rp:SlotEquality`): `equals_slot` (`rp:equalsSlot`, string, required),
    `equals_value` (`rp:equalsValue`, string, required: the lexical form `find` would send).
  The toy `Shelf` mixes in `ReferenceCollection`. Nested collections are shelves whose
  `member_class` is `Shelf`. `prov:Collection` typing is in the generated OWL only: the mapper
  writes the consumer class's own type.
- **PD-6** (spec "refused as invalid"): **write guards** (`services/write_guards.py`,
  `WriteGuards`), built by the kit from the view, `Listings`, the generated models and (stage 4)
  `Workflows`, passed to `Tenancy` and from there to every `Session` (`Session(…, guards=None)`,
  `open_session(…, guards=None)`). `Transaction.add_graph` and `replace_graph`, the one write path
  after `atomic-commit`, call `await guards.prepare(session, iri, triples, stored, allowed_state)` (`allowed_state: str | None`, the `Transaction` passes `self._allowed.get(iri)`, PD-19) before they
  collect the change; it returns the triples to write or raises. So the generic API,
  `Session.*_graph` and `UnitOfWork.commit` all pass it. A session opened without guards
  (`open_session` in tests) checks nothing, as today. Collection rule, when the root's
  `rdf:type` is a class with `ReferenceCollection` among its ancestors (decoded with
  `Mapper.from_graph` into the generated class):
  1. `member_class` is a served root (`Listings.served_root`) else `InvalidBody`;
  2. every member passes `iris.is_aggregate(tenant, m)` else `InvalidIri` naming them;
  3. `Session.heads(iris) -> list[AggregateHead]` (new: one `SELECT ?m ?type ?version` over the
     `Aggregate` graphs, `FILTER (?m IN ($members))`, an unregistered IRI has no head): a member
     with no head, or whose types do not include `member_class` or a descendant, makes
     `InvalidBody` naming every such member. Accepted: whoever may modify a collection learns
     whether an IRI it names is a registered aggregate of that class, even one hidden from it
     (it cannot read it; the IRI was already known to it);
  4. the rule's slots and values pass `Listings.plan(served_root(member_class), ListRequest(filters=…))`
     else `InvalidBody` with the `BadQuery` message.
- **PD-7** (DEC-5, DEC-7): reads.
  - `members(collection, *, deep=False) -> MemberList`: `require(READ)` on the collection; read
    it (`get_graph` + mapper, the class from its `rdf:type`); members = `had_member` ∪
    `session.find(models.named(member_class), **equals)` where `equals` groups equal slots into a
    list (`find`'s "all of"); deep: breadth-first, a visited set of collection IRIs; a member is
    expanded when `member_class` has `ReferenceCollection` among its ancestors and the caller may
    read it; filter by `may(READ)`, `hidden_count` = distinct unlisted IRIs; sorted.
  - `collections_of(iri) -> MemberList` (the collections in `member_iris`): explicit holders are
    `referrers(iri, slot="had_member")` (its checks, filter and hidden count); rule holders: one
    `CONSTRUCT` of every graph whose root has `rp:membershipRule`, decoded per collection with
    the mapper; `iri`'s type from `Session.heads([iri])`; for each collection whose
    `member_class` is that type's schema name (exact, as `find`), one
    `Session.matches(iri, class_iri, conditions) -> bool` (new; `ASK { GRAPH graph(iri) { $iri a
    $class . $patterns } }`, the conditions from the same `Listings.plan` `find` uses); rule
    holders are read-filtered; the hidden counts add.
- **PD-8** (DEC-3, spec cascade): `delete_cascade(collection, if_version) -> None`:
  1. `require(DELETE)` on the collection; resolve the members (not deep, the collection itself
     excluded), remembering which came only from the rule;
  2. members + 1 over `DEFAULT_MAX_ROOTS` (`atomic-commit`'s `UnitOfWork` default, exposed as
     that constant in `services/mapper.py`) → `CommitTooLarge` before any further read;
  3. for each member `may(DELETE)`; refusals raise `Forbidden` naming the refused members the
     caller may read and counting the others;
  4. `Session.heads(members)` gives every version in one read; a member with no head is skipped
     (already gone);
  5. one transaction: `t.remove(collection, if_version)`; per member `t.remove(m, head_version)`,
     and for a rule-only member `t._require_match(m, class_iri, conditions)` (PD-15), so a member
     whose matching slot changed between the resolve and the send fails the guard. Any failed
     guard → `Conflict(iris=…)`, nothing deleted.
  A plain delete is `Session.remove` or `UnitOfWork.remove`, unchanged.

### Discussion (stage 3)

- **PD-9** (DEC-4): `rp_access.yaml` `Action` gains `annotate` (`meaning: ODRL:annotate`), last in
  the enum, so `ACTIONS` order and existing role files are unchanged; it implies `read` like every
  action but `read`. New on `AccessRules`: `roles(caller, access, target_iri) -> set[str]` (the
  role names of the caller's grants in `_scope(target)` plus its global roles), `defines(role)`
  (a role defined at any level), `prohibits(caller, access, target_iri, action) -> bool` (the
  public face of `_prohibited`).
- **PD-10** (DEC-1, DEC-3): new module `model/rp_discussion.yaml` (imported by `rp.yaml`):
  class `Comment`, `class_uri: oa:Annotation`, mixins `AggregateRoot`, `Tracked` (author =
  `creator`, time = `created`, written by the session about the graph), annotations
  `rp_path: rp-comments`, `rp_iri_type: rp-comment`, `rp_writes: toolkit`. Slots (qualified
  names, the context's note): `has_target` (`oa:hasTarget`, uri, required), `body_value`
  (`oa:bodyValue`, string, required), `motivated_by` (`oa:motivatedBy`, enum `Motivation`:
  `commenting` → `oa:commenting`, `replying` → `oa:replying`, required), `comment_audience`
  (`rp:audience`, string, multivalued: role names), `comment_references` (`dcterms:references`,
  uri, multivalued), `replies_to` (`rp:repliesTo`, uri). Stage 4 adds `from_state_iri`, `to_state_iri`.
- **PD-11**: `WritesKind` gains `toolkit` ("the toolkit writes and reads the root itself; no
  route serves it"); `served_roots` leaves such roots out, so no generic route, listing or frame
  exists for comments or records (their audience would leak through a generic `GET`). The IRI is
  minted with `iris.mint_aggregate(tenant, iri_type_of(cls), rp_path)` from the class's own
  annotations. `hard.py` gains a rule: an application class's `rp_path` or `rp_iri_type` that
  starts with `rp-` is reserved (HardRule `RESERVED_SEGMENT`). Kept on gate 1's cut-list check:
  nothing else refuses a consumer root with `rp_path: rp-comments`, whose generic `GET` would
  then read a toolkit comment's graph under the default template.
- **PD-12** (DEC-2 refined): every comment, reply or not, has `oa:hasTarget` the aggregate; a
  reply has `oa:motivatedBy oa:replying` and `rp:repliesTo` the comment it answers. Reason: a
  thread and the delete of its aggregate are then one pattern; with Web Annotation's "the reply
  targets the comment", replies of replies need a recursive walk across graphs. `oa:bodyValue` is
  Web Annotation's own shorthand for a `TextualBody`, so no owned body node.
- **PD-13** (spec "posted on any aggregate"): `comment(iri, text, *, audience=(), references=(),
  reply_to=None) -> str` (the comment's IRI):
  1. `iri` is the tenant root → `InvalidIri` (no thread on the tenant: it has no registry entry,
     so its comments could never be deleted with it); `require(ANNOTATE)` on `iri`;
     `get_graph(iri)` (`NotFound`); a target whose type is a `rp_writes: toolkit` class →
     `InvalidIri` (no comment on a comment or a record);
  2. `text.strip()` empty → `InvalidBody`; an audience role not `rules.defines` → `UnknownRole`;
     a reference not `is_aggregate` → `InvalidIri`;
  3. `reply_to` must be in `thread(iri)` as this caller sees it, else `NotFound`;
  4. one transaction: `t._require_present(iri)` (PD-15) and
     `t.add_graph(c, mapper.to_triples(Comment(...)))`. The target's graph is not written, so its
     version is unchanged.
- **PD-14** (spec thread): `thread(iri) -> list[Comment]`: `require(READ)` on `iri`; one
  `CONSTRUCT` of every `Aggregate` graph whose root is `a oa:Annotation ; oa:hasTarget $iri`,
  decoded per root with `Mapper.from_graph(Comment, c, graph, graph_iri(c))`. Visible when the
  audience is empty or meets `rules.roles(caller, access, iri)`, and, for a reply, its parent is
  visible. Flat, oldest first by `created`, ties by IRI; a reply names its parent. The same
  visibility function serves PD-3 step 4.
- **PD-15** (DEC-3, atomic-commit DEC-6): pieces added to `Transaction`, internal to services
  (leading underscore, not exported, not in the public docs; consumers never pass SPARQL):
  - `_require_present(iri)` (stage 3): a guard fragment `GRAPH $g { $g $p_version ?v_n }`;
    when it fails the diagnosis names `iri` (a comment racing the delete of its target).
  - `_require_match(iri, class_iri, conditions)` (stage 2): a guard fragment
    `GRAPH $g { $iri a $class . $patterns }` (`match_patterns`, variables suffixed per change).
  - in `remove(iri, …)`, one more marked operation `_DROP_DEPENDENTS` (stage 3):
    ```sparql
    DELETE { GRAPH ?d { ?s ?p ?o } GRAPH $registry { ?d ?ep ?eo } }
    WHERE { $marked
      GRAPH $registry { ?d $p_kind $aggregate ; $p_owned_by ?c }
      VALUES (?type ?link) { $dependents }
      GRAPH ?d { ?c a ?type ; ?link $root }
      { GRAPH ?d { ?s ?p ?o } } UNION { GRAPH $registry { ?d ?ep ?eo } } }
    ```
    `$dependents` is `(oa:Annotation oa:hasTarget)` in stage 3 and gains
    `(rp:TransitionRecord prov:used)` in stage 4 (IRIs read from the metamodel through
    `vocabulary.py`). No per-dependent version guard: comments and records are never edited. One
    operation whatever the number of comments, so no root limit applies.
  - `_allow_state(iri, state_iri)` (stage 4): marks that this transaction may set `iri`'s state
    to `state_iri` (PD-19).

### Workflow (stage 4)

- **PD-16** (DEC-1): new module `model/rp_workflow.yaml` (imported by `rp.yaml`):
  - configuration classes, never stored: `Workflow` (`rp:Workflow`): `id` (the
    `skos:ConceptScheme` IRI, required), `workflow_name` (string, url_segment pattern, required),
    `workflow_states` (string, url_segment pattern, multivalued, required), `initial_state`
    (required), `workflow_transitions` (`WorkflowTransition`, multivalued, inlined as list).
    `WorkflowTransition`: `from_state`, `to_state` (here strings, the state names, required),
    `transition_roles` (string, multivalued, required), `comment_required` (boolean,
    `ifabsent: false`).
  - `UnderWorkflow` mixin: slot `workflow_status` (`adms:status`, uri). The state IRI is
    `f"{workflow.id}/{state}"`.
  - `TransitionRecord`: `class_uri: rp:TransitionRecord`, `is_a: Activity` (so `prov:Activity`
    in the generated OWL only — the mapper writes `rp:TransitionRecord` — and
    `was_associated_with`), mixin `AggregateRoot`, annotations `rp_path: rp-transitions`,
    `rp_iri_type: rp-transition`, `rp_writes: toolkit`; slots `used_resource` (`prov:used`, uri,
    required), `from_state_iri`, `to_state_iri` (`rp:fromState`, `rp:toState`, uri, required;
    also optional slots of `Comment`), `started_at_time` (`prov:startedAtTime`, datetime,
    required), `transition_comment` (`rp:transitionComment`, uri: the comment it posted).
    `from_state`/`to_state` of the file are names, the `*_iri` slots of stored records are IRIs:
    two meanings, two slots.
- **PD-17** (file format): one workflow per YAML file, validated by the generated `Workflow`:
  ```yaml
  id: https://example.org/ns/library/workflows/review
  workflow_name: review
  workflow_states: [draft, in_review, accepted]
  initial_state: draft
  workflow_transitions:
    - {from_state: draft, to_state: in_review, transition_roles: [librarian]}
    - {from_state: in_review, to_state: accepted, transition_roles: [librarian]}
    - {from_state: in_review, to_state: draft, transition_roles: [librarian], comment_required: true}
  ```
  `services/workflows.py`: `load_workflow(path) -> Workflow` (`model_validate`, problems named as
  in `load_role_definitions`); `Workflows(definitions, view, rules)` checks, all raising the new
  `InvalidWorkflow(PersistenceError, ValueError)` naming file and element: a state, initial state
  or transition end not in the states; a role `rules.defines` does not know; two transitions
  with the same ends; two workflows with one name; a class annotated `workflow: X` with no
  workflow `X`. It maps each schema class (annotated, or inheriting the annotation through `is_a`)
  and its class IRI to its `Workflow`. Configured by `ServiceKit(…, workflows: Sequence[Path] = ())`
  and `install_service(…, workflows=…)`; checked in the kit's constructor, so a bad file stops
  the service before it serves.
- **PD-18** (schema annotation): `RpAnnotation` gains `workflow` ("class annotation on an
  aggregate root: the name of the workflow its instances follow; the root includes
  `UnderWorkflow`"); it joins `PATTERNED_ANNOTATIONS`; a new HardRule `WORKFLOW`: an annotated
  class that is not an aggregate root, is the tenant root (`graph: meta`), or lacks
  `UnderWorkflow`, or a concrete root with `UnderWorkflow` and no annotation (own or inherited),
  is a problem with a fix hint. The generators emit nothing for it.
- **PD-19** (spec "toolkit owns the state"): the workflow rule of `WriteGuards.prepare`, for a root
  whose stored type (replace) or new type (add) maps to a workflow:
  - add: no `workflow_status` → the initial state's IRI is added; equal to it → kept; else
    `Forbidden("the state is changed only by a transition")`;
  - replace: the stored status is read with the stored tracking (one `SELECT` more, only when
    workflows are configured); the new status absent → the stored one is kept (absent stays
    absent: PD-22); equal → kept; different → `Forbidden`, unless the transaction holds
    `_allow_state(iri, new)` (PD-15). Public signatures of `Session.transaction()` and
    `Transaction.*` do not change, so no consumer call can skip review.
- **PD-20** (DEC-6): `transition(iri, to, *, if_version, comment=None) -> str` (new version):
  1. `require(READ)` on `iri`; `rules.prohibits(…, iri, MODIFY)` → `Forbidden` (a Prohibition of
     `modify` freezes the resource, transitions included); `get_graph`; the workflow of its type,
     else `InvalidBody` ("not under a workflow"); current state = stored status, or the initial
     state when absent;
  2. no transition current → `to` → `Conflict` naming both states (it depends on the current
     state); none of its roles in `rules.roles(caller, access, iri)` → `Forbidden`;
     `comment_required` and a blank comment → `InvalidBody`;
  3. one transaction: `t._allow_state(iri, to_iri)`, `t.replace_graph(iri, triples with
     workflow_status = to_iri, if_version)`, `t.add_graph(record)` (`TransitionRecord`:
     `used_resource`, `from_state_iri`, `to_state_iri`, `started_at_time` = the session clock,
     `was_associated_with` = [principal], `transition_comment` = the comment's IRI), and, with a
     comment, `t.add_graph(comment)` (`Comment`, motivation `commenting`, no audience,
     `from_state_iri`, `to_state_iri`; no `annotate` needed: the transition's role is the
     permission).
- **PD-21**: `transitions(iri) -> list[TransitionRecord]`: `require(READ)`; one `CONSTRUCT` like
  PD-14 for `a rp:TransitionRecord ; prov:used $iri`; oldest first by `started_at_time`, ties by
  IRI. The comment text is in the thread, found by `transition_comment`.
- **PD-22** (spec "stays readable"): a stored state the workflow no longer lists is read as
  stored; every transition from it is refused (`Conflict`), plain writes still pass (the state is
  unchanged). An aggregate stored before its class named the workflow has no state until its
  first transition, which starts from the initial state (spec wording aligned). A workflow's `id`
  must stay stable; changing it strands stored states (RISK-4).

### Delivery

- **PD-23**: docs per stage: a how-to page per capability under `docs/modules/ROOT/pages/howto/`
  (in the nav), a question each in `questions.adoc`, and the data-flows page's write-path and
  delete rows; `make check-docs`.
- **PD-24** (gate): gate 1 (2026-11-12), an independent attack and clarity gate, scored the first
  draft 8/10 with eight findings and a cut-list. Folded in: slot names qualified (PD-2, PD-5,
  PD-10, PD-16); cascade limit checked before reads (PD-8); rule members guarded at send (PD-8,
  PD-15); a Prohibition of `modify` refuses a transition (PD-20); comment referrers need the
  target and the audience (PD-3); the kit's models (PD-1); `_allow_state` replaces the public
  `moving_to` (PD-19); hidden-member probe accepted, tenant root refused for comments and
  workflows, dependent links paired with their type, spec wording aligned (PD-6, PD-13, PD-18,
  PD-3, PD-22). Cut: `comment_text` (the record names its comment), `Session.versions` (folded
  into `Session.heads`), a separate explicit-holder query (`collections_of` reuses `referrers`).
  Not cut: `RESERVED_SEGMENT` (PD-11 says why); nested collections (the EPIC's shape).

- **PD-25** (PLAN revision 2026-11-14, before task 1; the lead's, on the developer's instruction
  to check the PLAN against `atomic-commit` as built). Checked at `develop` `38f4a41` against the
  "As built" table of `openspec/changes/archive/2026-11-13-atomic-commit/proposal.md`. Held as
  written: `Session.transaction()`, `Transaction.add_graph/replace_graph/remove`, `Conflict.iris`
  (a tuple of `str`), `UnitOfWork.version(iri)`, `CommitTooLarge`, the limit enforced by
  `UnitOfWork.commit` only. Where this PLAN differs from the code, the code wins:
  1. The transaction's lists are **private** (`Transaction._guards: list[SparqlTerm]`,
     `_operations: list[str]`, `_confirm`; atomic-commit PD-18a), not `guards`/`operations`
     (Context, RISK-5, the Assumption). This EPIC's pieces (`_require_present`, `_require_match`,
     `_DROP_DEPENDENTS`, `_allow_state`, the call to `WriteGuards.prepare`) are private methods of
     `Transaction` or code in `services/session.py`; `Collaboration` (also in `services`) calls
     them. Nothing of it is exported or documented for consumers.
  2. The diagnosis (`Transaction._diagnose`) names only the roots of collected changes
     (`_roots`). So `_require_present(iri)` also records its graph and root in a private map the
     diagnosis reads: a required graph found with no version is named "was removed by someone
     else" (TC-62's `Conflict(iris=(b1,))`). `_require_match` records nothing: a member whose
     version changed is named by its remove's guard (TC-36, TC-36a); a member that only stopped
     matching (TC-36b) gives a `Conflict` with empty `iris` and the "lost a race" message.
  3. A remove whose root another writer already removed is a success in a removes-only commit
     (atomic-commit PD-17e); a cascade inherits this (TC-40 is the read-time form).
  4. `DEFAULT_MAX_ROOTS` already exists in `services/mapper.py` (task 2.4's "if not exported"
     falls away). `UnitOfWork.discard(iri)` exists (`38f4a41`); this PLAN does not need it.
  5. An add has no stored state: `Transaction.add_graph` calls
     `guards.prepare(session, iri, triples, None, allowed_state)`; `replace_graph` passes the
     `Tracked` it read with `Session._stored`.
  6. The fake store runs a request one operation at a time on rdflib (atomic-commit PD-17a), so
     `READ_REFERRERS` and `_DROP_DEPENDENTS` must run there as on Fuseki. With no dependent pair
     (stages 1 and 2) the `FILTER NOT EXISTS { VALUES … }` clause is left out of the query rather
     than sent with an empty `VALUES`.
  7. Names: `match_patterns` is in `domain/sparql.py`; minting is `Iris.mint_aggregate`; the
     session fixture is `testkit.fakes.fake_session` (there are no session fixtures in
     `tests/unit/services/conftest.py`; the `collaboration` fixture is new there); TC-01 goes in
     `tests/unit/entrypoints/test_kit_require.py`; the hard-rule tests in
     `tests/unit/generation/test_hard_check.py`; `tests/toy.py` `MODULES` gains each new module.
  8. Session E (`cross-aggregate-unique-keys`) changes `Transaction` in parallel: this EPIC's
     additions stay additive (own methods, own templates), the branch is rebased on `develop`
     before every PR (rule P-0002), both sides are kept in `services/session.py`, and a conflict
     in a generated file is resolved in the sources and regenerated (rule P-0003).
- **PD-26** (stage 1 challenge, 2026-11-14; four review passes and the adversarial tester on
  PR #95). Accepted, and fixed before the merge:
  1. **The hidden count never follows the narrowing** (L1 W1, L4/L5 no. 1; replaces PD-3 step 2's
     `$narrow` and the how-to's "the narrowing applies to the count too"). With the narrowing in
     the query, a caller could probe class by class and slot by slot and learn the class and slot
     of a referrer it may not read, which the spec forbids. `Session.referrer_rows` takes no
     class or slot; `Collaboration` computes `hidden_count` over every distinct referrer the
     caller may not read, then keeps the readable items of the asked class and slot. The spec
     says so in words. As built, the narrowing compares the names shown on each item, so an
     item whose class or slot is shown as an IRI (the schema does not know it) matches no name.
  2. **`Authorised` is built in one place**, a `Gate` method both `require` and
     `aggregate_access` use, so `global_roles` cannot be forgotten (L4/L5 no. 2).
     `kit.collaboration`'s docstring says `authorised` must be the answer of `require` or
     `require_aggregate`, never one built by hand (L1 S1; the signature stays PD-1's).
  3. **The reference pattern comes first in `READ_REFERRERS`**, before the registry pattern, so
     the store starts from the triples that hold `iri` and not from every aggregate of the
     tenant (L4/L5 no. 3; not measured, the result must not change).
  4. **A referrer with several types** (tester's failing test, L4/L5 no. 4): a root's own link
     is named against the root's class, not against each of its types in turn (the `OPTIONAL`
     subject class binds only for a part); a type the schema does not know is listed only when
     the referrer has no type it knows. So a book that also carries an unknown type is one item
     `(book, Book, shelf)`.
  5. The descriptions of `referrer_class` and `referrer_slot` say the IRI is given when the
     schema does not know the class or slot (L4/L5 no. 5); regenerate.
  6. Tests (L2 W1 to W3, S1, S2; the tester's file is kept): a positive row for `class_name`
     and for `slot`; the tenant root is not a referrer; a self-reference is listed; an unknown
     class or slot comes back as its IRI; `require_aggregate` → `kit.collaboration` →
     `referrers` (the how-to's snippet); TC-08's data made valid (two slots that both may hold
     a book) and books built through validation; one assert per idea. The tester's two
     "narrowing narrows the hidden count" tests are turned round to assert item 1.
  7. `architecture/data-flows.adoc`: one sentence in the gate section naming
     `kit.collaboration` as the third way in, which checks access itself (L3's note).

  Rejected: `ReferrerRow` as a `NamedTuple` (the model guard refuses hand-written models in
  services); folding `_class_iri`/`_slot_iri` (falls away with item 1 or stays trivial); moving
  `MemberList`/`AggregateHead` to stage 2 (PD-2 and task 1.1 place them); `referrers` defaulting
  to an empty list (every generated list is optional; one convention); a `NotFound` row and an
  other-tenant row in the unit file (the tester's file has both); TC-02 reading the manifest.
  Pinned by the tester and confirmed as intended: a triple in a loaded graph is not a
  reference; the tenant root is never a referrer but may be the target.
- **PD-27** (stage 2, the adversarial tester after task 2.4 and the cold reader of the how-to,
  2026-11-14; 171 tests, 7 failing). Accepted, fixed before the PR:
  1. **A cascade deletes only members of the collection's member class** (tester nos. 2, 3).
     `delete_cascade` trusted the stored `had_member`: a collection written without guards that
     names the tenant's access record, or an aggregate of another class, had it deleted. Now a
     head whose types hold neither the member class nor a descendant refuses the whole cascade
     with `StoredDataInvalid` naming the collection, not the member; nothing is deleted. The
     check uses the heads already read, so it costs no query.
  2. **The write guard refuses triples that do not decode** (no. 4): a collection whose triples
     the generated class refuses (no `member_class`) is `InvalidBody`, not a bare pydantic
     `ValidationError`.
  3. **A stray `rp:membershipRule` does not break `collections_of`** (no. 7): a root with the
     rule predicate whose type is not a collection class is skipped, not `BadQuery` for every
     caller.
  4. **An unreadable collection is not named in `StoredDataInvalid`**: when a stored collection
     the schema no longer accepts makes `collections_of` fail, the message names it only if the
     caller may read it; otherwise it says one collection of the tenant cannot be read.
  5. `Referrer`, `ReferrerList` and `MemberList` are exported from `rdf_persistence`, as `Page`
     is: they are what the public reads return.
  6. Tests: the failure branch of the match guard on Fuseki (TC-36b's form, in IT-04); a named
     member of a subclass is accepted and a rule member of a subclass is not listed; the
     vacuous assertion of the stage 1 test for a schema without `rp_collections` is replaced by
     the fixture that really lacks the module (`partial.yaml`).
  7. The how-to page, from the cold read: where `if_version` comes from; how a shelf is changed
     (a replace, guarded like an add); what "all or nothing" covers beside skipped members and
     left blobs; a deleted member stays named and the next save of the shelf is refused until
     it is taken out; a shelf of shelves with an empty rule holds itself; the example's books
     made consistent; one errors table for the cascade.

  Rejected, the tests turned round to pin the behaviour: two cascades of one collection where
  the loser reports success (no. 1: a removes-only commit whose roots another writer already
  removed is a success, atomic-commit PD-17e; the collection is gone either way); a literal as
  the rule, or two `member_class` values, written as raw triples (nos. 5, 6: the guard checks
  the decoded model; the generic API validates the shape before it, and the mapper writes one
  value). Pinned by the tester and confirmed: a named member changed before the versions are
  read is deleted at its new version, and only a change after that is a `Conflict`; a member
  removed after the versions are read is a `Conflict` naming it; `members` of a collection
  that lists itself includes it.
- **PD-28** (stage 2 challenge, 2026-11-14; four review passes on PR #98). Accepted, fixed
  before the merge. Security first:
  1. **A rule member the caller may not read is neither listed nor counted** (L1 C1; the lead's
     decision, narrowing DEC-7 and PD-7 for rule members only; the developer may overrule). The
     rule's equalities are chosen by whoever may modify a collection, so counting its hidden
     matches let that caller count the aggregates it may not read by slot value, and with two
     equalities learn a slot value of one of them. `members` (plain and deep) drops unreadable
     rule members; `hidden_count` counts only unreadable **named** members, whose IRIs the
     writer already held. In `delete_cascade` a rule member the caller may not read is no
     member for that caller: it is not deleted and causes no refusal (the lead, after reading
     the fix: a refusal "members matched by the rule may not be deleted" was still a yes-or-no
     answer to "does something hidden match my rule"); `CommitTooLarge` gives the limit and no
     member count. `collections_of` is unchanged: its hidden holders are not chosen by the
     caller. The spec says so.
  2. **A cascade checks the stored member class as the write guard does** (L1 W1; completes
     PD-27 item 1). A collection written without guards with `member_class` set to a class that
     is not a served root (the tenant's access class) could still have that aggregate deleted.
     `delete_cascade`, and a deep read before it expands, require `member_class` to be a served
     root, else `StoredDataInvalid` naming the collection; an unknown class is the same error,
     not an `AttributeError`.
  3. **The tenant root is never cascaded** (L1 W2): `delete_cascade` refuses the tenant IRI with
     `InvalidIri`. On the tenant, deleting needs `administer`, which a cascade's `delete` check
     would have bypassed for a tenant root class that mixes in `ReferenceCollection`.
  4. RISK-8 reworded (L1 S1): the modifier of a collection learns the class of a hidden
     aggregate it names, by trying member classes; still never its content.

  Correctness:
  5. **Each rule collection is decoded from its own graph** (L4/L5 W1, L3 W1). The read of rule
     collections is a generic `Session.graphs_with(predicate, obj=None)`: the graphs of the
     registered aggregates whose root has that predicate (and object), one `Graph` per root,
     the predicate pattern first. `Session` no longer names the collection rule; stage 3's
     thread uses the same read. Triples about another subject inside one collection's graph no
     longer invent or corrupt a holder.
  6. A deep read names the nested collection, not the root, when the nested one cannot be read
     (L4/L5 W2, L2 no. 1); a nested member that is no longer a collection is skipped like one
     that is gone (L4/L5 W3); the stored-data wrapper catches the errors each step documents,
     not every `LookupError` (L4/L5 W4).
  7. `READ_HEADS` starts from `VALUES` of the IRIs asked, not from the registry (L4/L5 W6).
  8. An explicit holder in `collections_of` is a referrer by `prov:hadMember` **typed with a
     collection class** (L4/L5 S9); `members` and `delete_cascade` refuse an IRI that is not an
     aggregate of the tenant with `InvalidIri`, as `collections_of` does.

  Structure:
  9. **The collection code moves to `services/reference_collections.py`** (L3 W2, S2; L4/L5
     S2): what a collection is (the helpers now in `write_guards.py`, with the three duplicated
     checks made one each) and a `ReferenceCollections` class with `members`, `collections_of`
     and `delete_cascade`. `Collaboration` keeps `referrers` and delegates the three, so PD-1's
     public face is unchanged; `write_guards` imports the collection rule from the new module.
     Stage 3 and 4 add their own modules the same way.
  10. An import contract in `.importlinter`: `services.session` imports none of
      `services.access`, `services.collaboration`, `services.reference_collections`,
      `services.write_guards` (L3 S3).

  Spec, tests and docs:
  11. The spec's cascade requirement says what is built (L2 no. 2): member versions are guarded
      from the moment they are read; a rule member that stopped matching refuses the cascade
      without being named. The how-to says both, and that one bad stored rule collection fails
      `collections_of` for the resources of its member class (L2 nos. 3, 4);
      `data-flows.adoc` names the match guard and its empty `Conflict.iris` (L3 S4).
  12. Tests (L2 nos. 5 to 7 and suggestions): one slow Fuseki cascade just under the root limit
      with stored members; a shelf and its new books in one commit is refused; `delete_cascade`
      without the module; TC-15 also reads the members back; a cascade over a stored-file member
      leaves the blob, if the existing fakes make it a short test; `and`-chained and
      message-less asserts split in the stage's main test files; two misnamed adversarial tests
      renamed; the durations row's test count.
  13. Small: the `Forbidden` text built with a plain `if`; the misformatted `except`; a comment
      that the match guard's suffix is the guard's index.

  14. From the checker (2026-11-14): a stored rule collection of a class the schema no longer
      has is `StoredDataInvalid` for `collections_of` too, not an `AttributeError`; the spec and
      the how-to say that a member another writer removed during the cascade is skipped or
      refuses it, depending on the moment (replaced is always a refusal); message-less and
      chained asserts in the stage's three small test files. Not built: the test that a cascade
      over a stored-file member leaves its blob (the fixer judged the existing fakes need more
      than a short test); the how-to's sentence rests on the code, where only
      `services/file_removal.py` deletes blobs.

  Rejected: making `_require_match` public (L3 S1, L4/L5 W5: private is PD-15; recorded here
  that the collaboration-side modules of `services` are its only callers); narrowing the
  rule-collection read by member class, one plan shared by `find`, the cascade and `matches`,
  and building the schema lookup tables once in the kit (L4/L5 S1, S3, S4: optimisations with
  no measurement behind them; RISK-2 stands); `deque` and the `visited` side effect (L4/L5 S6:
  falls away or stays trivial with item 9). Marked untested, not built: a named member of a
  subclass is accepted and a rule member of a subclass is not listed (the toy schema has no
  aggregate-root subclass, and adding one ripples through every generated artefact; the shared
  class helper is tested; the how-to says "the class or a class derived from it" without an
  example).
- **PD-29** (stage 3, the adversarial tester after task 3.3 and the cold reader of the how-to,
  2026-11-14; 174 tests, 7 failing, one defect). Accepted, fixed before the PR:
  1. **An annotation that is not a toolkit comment breaks nothing.** `thread` and `referrers`
     decoded every root typed `oa:Annotation` as a `Comment`; an application's own annotation,
     or one written as raw triples, without a body or a motivation made a bare pydantic
     `ValidationError` escape for every caller. A root that does not decode as a `Comment` is
     not a comment: `thread` leaves it out, and `referrers` treats it as any other referrer
     (listed if the caller may read it, counted if not). New Error matrix row, below.
  2. **Mentions** (the EPIC's rabbit-hole says a mention is a reference whose target is a
     principal): as planned in PD-13 and built, a reference is an aggregate IRI of the tenant.
     A principal can be referenced only where the application stores principals as aggregates.
     The how-to says so; no code change.
  3. The how-to page, from the cold read: the example's audience uses a role the example
     defines; one spelling of "no audience"; what a reply's audience is (its own; it is hidden
     with its parent anyway); `thread` gives no hidden count; `creator` is the principal's IRI;
     application code that holds a session can read and remove a comment like any aggregate
     (the toolkit offers no caller-facing way: no route, no listing, never a collection
     member), and the type `oa:Annotation` with a target, a body and a motivation is what makes
     a comment, wherever its IRI; a stored audience names roles by name, so renaming a role
     hides its comments; "a reply may answer a reply" beside "no comment on a comment" said
     once, together; which check opens the collaboration for reading (`read`) and for posting
     (`annotate`).

  Pinned by the tester and confirmed as intended: a comment that races the removal of its
  target is refused or dropped with it, never orphaned; a comment racing a replace of its
  target succeeds; a comment racing a remove-and-re-add lands on the new aggregate (the guard
  asks only for a version); a session opened without the dependent pairs orphans the comments
  (documented limit); an undefined role in a stored audience hides the comment from everyone
  without that role name; a reply whose parent is on another target, in a cycle or gone is
  hidden; references may name any aggregate IRI of the tenant, the tenant root and the access
  record included (an IRI is shown as given, PD-13).
- **PD-30** (stage 3 challenge, 2026-11-14; four review passes on PR #99). Accepted, fixed
  before the merge. Security first:
  1. **A generic aggregate route answers only for an aggregate of its own class** (L1 C1; the
     lead's decision). PD-11 relied on "no route reaches a comment", but a route builds its
     target IRI from the IRI policy, and a policy whose aggregate template names neither the
     type nor the path gives a comment and a book of the same id one IRI: a reader outside the
     audience could then `GET` a comment as a book, and with `modify` or `delete` overwrite or
     remove it. `Aggregates.read`, `replace` and `remove` refuse with `NotFound` a stored root
     that is not typed with the route's class or a class derived from it. Read and replace
     already read the graph; remove gains one read. This also closes the older confusion
     between two served classes under such a policy. A test uses a flat policy. As built: the
     class is a required argument of `read` and `remove` (the lead, over the fixer's optional
     one: a check that can be left out by forgetting an argument protects nobody), and the
     class family comes from `Documents.family`.
  2. **Every annotation that refers is judged as a comment** (L1 W1): `referrers` of a hidden
     comment listed its replies (their `rp:repliesTo` link), because only `dcterms:references`
     rows went through the visibility rule. Every referrer row whose class is `oa:Annotation`
     does now, whatever the link; and for a referrer that is a comment the thread's rule alone
     decides (L4/L5 W4: the read right on the comment's own IRI no longer hides a comment the
     caller sees in the thread).
  3. **A token role counts for an audience only if it is defined at system level** (L1 W2,
     L4/L5 W1, L2 W1; narrows PD-9's "plus its global roles"). A token role named like a tenant
     role, which the identity provider's administrator assigns and not the tenant's, no longer
     opens that role's comments. The spec says so, with a scenario.
  4. **A long chain of replies cannot break a thread** (L4/L5 C1): the visibility rule walked
     reply chains by recursion and hit Python's limit at about a thousand replies, depending on
     the order the store returned them; any caller with `annotate` could cause it. The walk is
     a loop; a test reads 5 000 shuffled replies.

  Correctness and cost:
  5. The comment referrers of a resource are read in one `graphs_with` query, not one read per
     comment: no `NotFound` when a comment goes between the two reads (L4/L5 W3, L1 S1).
  6. The dependents operation starts from the link to the removed root, then checks the
     registry (L4/L5 W2), as PD-26 and PD-28 did for the reads; measured on Fuseki on a tenant
     with thousands of aggregates and no comment, with and without the operation, and the
     figures go in the durations table.
  7. A comment may be posted on an application's own `oa:Annotation` aggregate; only what
     decodes as a toolkit comment (or, from stage 4, a record) refuses one (L4/L5 W6).
  8. The dependent pairs have one source, the session's own: `referrer_rows` uses them, so
     what `referrers` leaves out and what a remove drops cannot differ (L3 W2, L4/L5 S2).
     "What the toolkit writes" is one helper in `schema_structure.py` (L3 W3, L4/L5 S1).
     `.importlinter` names `services.discussion` (L3 W1).
  9. Small: the sort key of a thread does not compare a naive with an aware time; minting does
     not fall back to an empty path; `_require_present`'s docstring says it must not be used
     on a graph the same transaction removes.

  Spec, tests and docs:
  10. Tests (L2): the author of a comment is the caller, through `kit.collaboration` with two
      callers; the generic `DELETE` route drops the comments; the stage 2 kit test swallowed by
      a stage 3 test gets its own `def` back; a reference to a never-stored aggregate IRI is
      accepted (pinned); removing a comment keeps its replies stored and hidden; a reviewer's
      modify is refused through a guarded path (the rp-access scenario); messages on the
      message-less asserts of the stage's test files; the assertion that cannot fail.
  11. Docs: references are checked for the IRI's shape, not for existence; a hidden comment
      that references a resource is still counted in that resource's referrers; an
      application's own annotation deleted with its target leaves the graphs it loaded
      (L4/L5 W5, L1 S3: documented, not built, since toolkit comments load nothing);
      `data-flows.adoc` says the same pairs leave comment links out of `referrers`. The Error
      matrix row "10 000 comments" reads 600, what TC-63 and IT-07 test.

  Rejected: answering `NotFound` and not `InvalidIri` for a comment on a comment (L1 S2: the
  developer reviewed PD-13; comment IRIs are random, and item 1 and 2 close the paths that hand
  them out); one value for `keys`, `guards` and `dependents` (L3 S1: when a fourth appears);
  moving the validation of the text before the read of the target (L4/L5 S7: PD-13's order).

## Delivery decisions

- **D-1** (2026-11-14, the lead): the developer granted, for this EPIC, commit, push, PR and
  merge on green CI, one PR per stage, worked in a worktree until completion.
- **D-2** (2026-11-14, the lead): TC-09a is split. Task 1.2 tests that `referrers` works on a
  view without `rp_collections`; the `members` → `LookupError` half moves to task 2.3, where
  `members` first exists. Reason: no stub methods for later stages.
- **D-3** (2026-11-14, the lead, task 1.2 as built): `Collaboration` takes the kit's `Iris`
  (PD-3 step 1 needs `is_aggregate`) and holds the mapper, models and listings only from the
  stage that first uses them. The cross-graph read is `Session.referrer_rows` (rows of IRIs, no
  access, no schema names); the names and the access filter stay in `Collaboration`.
- **D-4** (2026-11-14, the lead, before stage 2): two consequences of PD-26 for PD-7 and the
  impact gate.
  1. `collections_of` cannot reuse the public `referrers(iri, slot="had_member")` for its hidden
     count: since PD-26 that count covers every hidden referrer, not only hidden collections.
     It uses the same rows (`Session.referrer_rows`) and keeps those whose predicate is
     `prov:hadMember` before the access split. This narrowing is the toolkit's own, not a
     caller's, so it reveals nothing a caller chose to probe.
  2. Impact before task 2.2 (GitNexus, 2026-11-14): `open_session` CRITICAL (187 dependents),
     `Session.replace_graph` HIGH, `Tenancy` MEDIUM. Reported to the developer. The change is
     PD-6's: an optional `guards=None`, so a session opened without guards behaves as before;
     the session tests, the store conformance suite and the full gates are the safety net.
- **D-5** (2026-11-14, the lead, task 2.2): `Session.heads` and TC-32 move from task 2.3 to
  task 2.2, because the collection guard (PD-6 step 3) is its first caller.
  `WriteGuards.prepare` takes `(session, iri, triples, stored)` in stage 2; `allowed_state`
  arrives with the workflow rule in task 4.3, its first use. `testkit.fake_session` gains the
  same optional `guards` as `open_session`, so the guard tests run on the fake store.
- **D-6** (2026-11-14, the lead, task 2.2 as built): the collection guard reads the store when
  the collection is collected, so a collection cannot be saved in the same commit as members
  that are not stored yet: they have no head and the save is refused (`InvalidBody`). Members
  are saved first. The how-to says so (task 2.6). The guard asks the session which IRIs are not
  aggregates of the tenant (`Session.not_aggregates`), so it reads no private state.
- **D-7** (2026-11-14, the lead, before stage 3): what stages 1 and 2 as built change for
  stage 3, so the briefs follow the code and not the older text.
  1. The discussion code lives in `services/discussion.py` (a `Discussion` class with `comment`
     and `thread`, and the visibility function `referrers` also uses); `Collaboration`
     delegates, as for collections (PD-28 item 9).
  2. `thread` reads with `Session.graphs_with(oa:hasTarget, iri)` and keeps the roots typed
     `oa:Annotation` (PD-28 item 5 in place of PD-14's own `CONSTRUCT`).
  3. `Transaction._require_present` records its graph and root for the diagnosis (PD-25 item 2).
  4. Removing an aggregate drops its dependents inside `Transaction.remove`, so a cascade's
     member removes drop the members' comments too, with no extra code in the cascade.
  5. A comment or a record is never a member a collection may name: its class is
     `rp_writes: toolkit`, not a served root, which the write guard and the cascade refuse
     (PD-28 item 2).
  6. Tasks 3.1 and 3.2 go to one builder and one commit: both change the metamodel and
     regenerate every artefact, and their code does not overlap.
  7. Impact (GitNexus, before the build): the `Action` enum and `Transaction.remove` are hubs.
     `annotate` is added last in the enum (PD-9) and the dependents operation is one more
     marked operation of a remove; the access matrix tests, the session tests and the store
     conformance suite are the safety net.
- **D-8** (2026-11-14, the lead, tasks 3.1 and 3.2 as built):
  1. An application imports `rp_discussion` to use discussion; the toy does so from
     `library.yaml`. Without the import the view has no `Comment` and PD-1's `LookupError`
     applies.
  2. The toolkit's own generation still emits `Comment.frame.jsonld` and a `Comment` component
     schema, with no path. PD-11's "no frame" is met where it matters: no route, listing or kit
     code reads the frame, and `served_roots` leaves the class out. Not worth a generator rule.
  3. `RESERVED_SEGMENT` checks every class of the application's own modules, roots or not.
  4. Regenerating after adding a metamodel module that the package exports needs two passes
     (the package cannot import before the generated module exists, and the hard check reads
     the old generated `WritesKind`). A fresh clone is unaffected; task 4.1 will meet it again.

## Algorithm / approach

Toy library `T`; books `b1`, `b2`, `b3`; shelves `s1`, `s2`; principals ada (`librarian` on
`T`) and bob (`reader` on `T`, prohibited `read` on `b2`).

**Stage 1, referrers.** `b1.shelf = s1`, `b2.shelf = s1`, `b3.shelf = s2`, `b3.sequel_of = b1`.

| Call (bob) | Query rows | Result |
|---|---|---|
| `referrers(s1)` | (b1, Book, Book, lib:shelf), (b2, …) | referrers [b1 shelf], hidden_count 1 |
| `referrers(b1, slot="sequel_of")` | (b3, Book, Book, lib:sequelOf) | [b3 sequel_of], 0 |
| `referrers(s2)` as ada | (b3, …) | [b3 shelf], 0 |

**Stage 2, collections.** `s1`: `member_class Book`, `had_member [b1]`, rule `genre = poetry`;
`b3` is poetry.

| Step | Result |
|---|---|
| save `s1` (UnitOfWork) | guard: `Book` served; heads: b1 is a Book; rule plans → stored |
| `members(s1)` as ada | [b1] ∪ find(Book, genre="poetry") [b3] → [b1, b3], 0 |
| `collections_of(b3)` | `referrers(b3, slot="had_member")` none; rule holders [s1]; `matches` → [s1] |
| bob `delete_cascade(s1, v)` | bob may not delete b1 → `Forbidden`, nothing deleted |
| ada `delete_cascade(s1, v)` | heads(b1, b3); one transaction: remove s1, b1, b3, `_require_match(b3, Book, genre=poetry)` |
| as above, b3 re-genred between heads and send | b3's version changed → `Conflict(iris=(b3,))`; if re-genred before heads, the match guard fails → `Conflict` |

**Stage 3, discussion.** ada: `comment(b1, "check ch. 3", audience=["librarian"])` → `c1`;
bob (granted `reader` + direct `annotate`) `comment(b1, "nice")` → `c2`;
ada `comment(b1, "thanks", reply_to=c2)` → `c3`.

| Call | Result |
|---|---|
| bob `thread(b1)` | [c2, c3] (c1's audience misses `reader`) |
| ada `thread(b1)` | [c1, c2, c3] |
| remove b1 | one request: b1's graph, entries, and c1, c2, c3 (`_DROP_DEPENDENTS`) |

**Stage 4, workflow.** `Book` annotated `workflow: review`.

| Step | Stored | Result |
|---|---|---|
| add b1 without status | status `…/review/draft` | v1 |
| replace b1 with status `…/accepted` | unchanged | `Forbidden` |
| ada `transition(b1, "in_review", if_version=v1, comment="ready")` | status in_review; record r1 (`transition_comment` c4); comment c4 | v2 |
| bob `transition(b1, "accepted", if_version=v2)` | unchanged | `Forbidden` (no `librarian`) |
| ada `transition(b1, "accepted", if_version=v1)` | unchanged | `Conflict` (version) |
| ada prohibited `modify` on b1, `transition(b1, "accepted", if_version=v2)` | unchanged | `Forbidden` |
| ada `transitions(b1)` | — | [r1] |

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Add access checks or schema knowledge to `Session` | `Collaboration` (PD-1); guards injected (PD-6) | The session is the graph level; the caller gates |
| Name a new metamodel slot `target`, `status`, `members`, `items` … | Qualified names (`has_target`, `workflow_status`, `had_member`, `referrers`) | One slot namespace across `rp.yaml` and the consumer's schema |
| Read members, rules or comments as dicts of triples | Decode with `Mapper.from_graph` into generated classes | Models, not dicts (AGENTS.md) |
| Store or run a rule as SPARQL | `SlotEquality` rows → `find` / `matches` through `Listings.plan` (DEC-5) | No caller-built SPARQL |
| Name a hidden referrer or member in a result or an error | Count it (`hidden_count`) | DEC-7 |
| Check a collection or a state in `Collaboration` only | `WriteGuards` on the transaction (PD-6, PD-19) | The generic API and `UnitOfWork` bypass `Collaboration` |
| A public flag that lets a write change the state | `_allow_state` inside services (PD-15) | It would skip review |
| Give comments or records an `rp_path` without `rp_writes: toolkit` | PD-11 | A generic `GET` would bypass the audience |
| Remove dependents one `t.remove` each | One `_DROP_DEPENDENTS` operation (PD-15) | Root limit; no version to guard |
| Rely on the transaction for the cascade's root limit | Count before reading (PD-8) | Only `UnitOfWork.commit` enforces it |
| Hard-code `oa:`/`prov:` IRIs in templates | `vocabulary.py` reads them from the metamodel | Single source |
| Hand-write `Workflow`, `Comment`, `Referrer` classes | Generate from LinkML | DEC-1 |

## Error matrix

| Input | Result |
|---|---|
| `referrers(x)`, x not minted for the tenant | `InvalidIri` |
| `referrers(b)`, caller may not read b | `NotFound` or `Forbidden` (as `require`) |
| `referrers(b, slot="nope")` / `class_name="Nope"` | `BadQuery` |
| A referrer refers by two slots | two items; `hidden_count` counts it once if hidden |
| A comment referencing b whose target the caller may not read, or whose audience misses its roles | not listed, `hidden_count` +1 |
| Comments on b / records of b | not referrers of b (dependent links paired with type, PD-3) |
| A consumer aggregate with a `prov:used` slot pointing at b | a referrer (only `rp:TransitionRecord`'s link is dropped) |
| Collection saved with a member of another class, or never stored | `InvalidBody` naming it; nothing written |
| Collection member not minted for the tenant | `InvalidIri`; nothing written |
| Collection member hidden from the modifier | accepted if it is a registered member-class aggregate (PD-6 probe, accepted) |
| Collection `member_class` not a served root | `InvalidBody` |
| Rule naming a slot the class does not list, or a bad value | `InvalidBody` (the `BadQuery` text) |
| Member deleted after the collection was saved | stays listed (no referential integrity); deep read and cascade skip what has no head |
| Rule or `member_class` invalid after a schema change | `members`/`collections_of` raise `StoredDataInvalid` naming the collection |
| Rule-matched member of a subclass of `member_class` | not a member (`find` matches the exact type); explicit members may be of a subclass |
| Deep read through a collection the caller may not read | not expanded; counted hidden |
| Cycle A → B → A | each visited once |
| Collection lists itself | deep read visits it once; cascade excludes it from the members |
| Cascade: more than `DEFAULT_MAX_ROOTS - 1` members | `CommitTooLarge` before the permission and version reads; nothing deleted |
| Cascade: one member not deletable | `Forbidden` naming readable refusers, counting the rest; nothing deleted |
| Cascade: a member changed since resolved, or a rule member no longer matching at send | `Conflict(iris=…)`; nothing deleted |
| Cascade: a new rule match appears during the cascade | not deleted (resolved at the call) |
| Cascade of a StoredFile member | graph removed; its blob left to the sweep |
| Schema without `rp_collections` / `rp_discussion` / `rp_workflow` | the methods needing it raise `LookupError` naming the module |
| `comment` without `annotate` | `Forbidden` (or `NotFound` when the target is invisible); nothing stored |
| `comment` on the tenant root, on a comment or on a record | `InvalidIri` |
| `comment` on a missing target | `NotFound` |
| `comment` with blank text | `InvalidBody` |
| `comment` audience role undefined | `UnknownRole` |
| `reply_to` on another target, missing, or hidden from the caller | `NotFound` |
| Target deleted between the check and the write | `Conflict(iris=[target])`, nothing stored (PD-15 guard) |
| A comment references a resource some thread readers may not read | the IRI is shown as given; the resource itself stays guarded |
| Author not in its own comment's audience | the author does not see it (spec as written, Q-1) |
| A reply under a hidden parent | hidden too |
| Delete of an aggregate with 600 comments (tested; more is the same one operation) | one operation; all gone in the same request |
| A consumer's own `oa:Annotation` aggregate targeting a deleted resource | deleted with it (RISK-3) |
| An `oa:Annotation` aggregate on b that does not decode as a `Comment` (no body, no or an unknown motivation) | not in `thread(b)`; as a referrer it is an ordinary one (PD-29) |
| Workflow file: undefined state / unknown role / duplicate transition / duplicate name | `InvalidWorkflow` at kit start |
| Class annotated `workflow: x`, no file `x` | `InvalidWorkflow` at kit start |
| Annotated class without `UnderWorkflow`, the reverse, or the tenant root annotated | `make generate` hard problem `WORKFLOW` |
| Add with a non-initial status | `Forbidden`; nothing written |
| Replace changing the status (generic `PUT`, `UnitOfWork`, `Session.transaction`) | `Forbidden`; nothing written |
| Replace omitting the status | stored status kept |
| Stored aggregate under a newly annotated class, no status | stays without; its first transition starts from the initial state |
| `transition` with a Prohibition of `modify` on the resource or tenant | `Forbidden`; nothing written |
| `transition` to a state with no transition from the current one | `Conflict` naming both states |
| `transition` by a caller without one of its roles | `Forbidden` |
| `transition` without a required comment (blank counts) | `InvalidBody` |
| `transition` at a stale `if_version` | `Conflict`; nothing written (no record, no comment) |
| Two transitions racing from one version | one wins, the other `Conflict` |
| Stored state dropped from the workflow file | readable; transitions from it `Conflict`; plain writes pass |
| `transition` on a class with no workflow | `InvalidBody` |
| Session opened with `open_session` and no guards | no state or collection checks (documented) |
| The store fails during any transaction | one request: nothing written; the store's error raised |

## Risks / Trade-offs

- **RISK-1** — `referrers`, `members`, `thread`, `collections_of` have no paging (medium; medium).
  Mitigation: hundreds is the EPIC's appetite; paging is a later change.
- **RISK-2** — `collections_of` runs one `ASK` per rule collection of the member's class (medium;
  low). Accepted by the EPIC; measured in IT-05 with 50 rule collections.
- **RISK-3** — `_DROP_DEPENDENTS` matches by type, so a consumer's own `oa:Annotation` targeting a
  deleted resource is deleted too (low; low). Accepted; documented in the how-to.
- **RISK-4** — changing a workflow's `id` or dropping a state strands stored states (medium;
  medium). Mitigation: the how-to says the `id` is permanent; migration is `schema-migrations`.
- **RISK-5** — `Transaction` gains internal pieces (`_require_present`, `_require_match`,
  `_DROP_DEPENDENTS`, `_allow_state`) where `atomic-commit` says "used as is" (certain; low).
  Mitigation: its DEC-6 opens the transaction to exactly such fragments; the lead tells its owner.
  `DEFAULT_MAX_ROOTS` must be a module constant there (or added here, one line).
- **RISK-6** — a referrer row needs `?referrer a ?class`; an aggregate written with no type is
  not found (low; low). The mapper and the generic API always write the type.
- **RISK-7** — `Action.annotate` and the new slots appear in generated artefacts (OpenAPI,
  TypeScript, snapshots, golden files) (certain; low). Regenerate and refresh in each stage.
- **RISK-8** — the collection guard reveals to a collection's modifier whether a hidden IRI is a
  registered aggregate of the member class, and so, by trying member classes, the class of a
  hidden aggregate whose IRI it holds (certain; low). Accepted (PD-6, PD-28 item 4): no content
  is shown, and the modifier already holds the IRI.
- **Assumption** — aggregate graphs hold only slot predicates (checked: the mapper and the
  shape-validated generic API are the only writers).
- **Assumption** — `atomic-commit` is merged with `Transaction`, its `guards`/`operations` lists,
  `Conflict.iris` and `CommitTooLarge` as its PLAN states (PD-2 to PD-8 there).

## Open Questions

- **Q-1** — Should a comment's author always see it, even outside its audience? Recommendation:
  no for now (the spec says audience decides); revisit if the consumer asks.
- **Q-2** — Should `transition` also require `modify`? Recommendation: no (DEC-6: the roles on
  the transition decide; a reviewer often may not edit). A Prohibition of `modify` does refuse it
  (PD-20).
