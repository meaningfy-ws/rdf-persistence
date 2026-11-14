> Derives from: EPIC `collaboration-and-reference-collections` (proposal.md, issues #78 to #81).
> Four stages, one PR each into `develop`, after `atomic-commit` is merged. Type: Implementation.

Fixtures: the toy library (`tests/toy.py`: `TENANT`, `ADA`, `BOB`, `book_iri`, `dune`, `caller`,
`role`, `direct`, `ban`, `access`, `toy_mapper`; schema `tests/fixtures/library/`). "As ada" means
a `Collaboration` for `caller(principal=ADA)` with `access(role("librarian"))`; "as bob" one for
`caller(principal=BOB)` with `access(role("reader", who=BOB), ban(Action.READ, graph_of(b2), BOB))`
unless a row says otherwise. In the tables, "items" is `ReferrerList.referrers` or
`MemberList.member_iris` and "hidden N" is `hidden_count == N`. Unit tests use the fake store (`testkit/fakes.py`) through
`tests/unit/services/conftest.py`'s session fixtures; a `collaboration` fixture there builds
`Collaboration` like `kit.collaboration`. Every stage regenerates with `make generate` after a
schema change and commits the generated files. After each task: `make test-changed` (after
changing `domain` or a port in `services`: `make test-fast`), `make check-quality`,
`make clean-code`. Each stage closes with `make check-all`, `make test-containers`,
`openspec validate collaboration-and-reference-collections --strict`, a PR into `develop`
(`Refs: collaboration-and-reference-collections`), merged on green CI.

## 1. Reverse references (#78)

- [x] 1.1 Models and fixture. `rp_service.yaml`: `Authorised.global_roles`, `Referrer`,
  `ReferrerList`, `MemberList`, `AggregateHead` (PD-1, PD-2; qualified slot names). `books.yaml`: `Shelf`, `shelf`, `sequel_of`, `about`
  (PD-4); `tests/toy.py` gains `shelf(iri)`. `make generate`; refresh the model-shape snapshot
  (`make refresh-snapshot`, review the diff). `Gate.aggregate_access` and `ServiceKit.require`
  fill `global_roles`. Test first in `tests/unit/entrypoints/test_kit.py`.

| ID | Input | Expected |
|---|---|---|
| TC-01 | `kit.require` for a caller with global role `admin` | `Authorised.global_roles == ["admin"]` |
| TC-02 | `Book(shelf=s1, sequel_of=b0)` mapped and read back | the same IRIs; the generated `Shelf` has `rp_path` `shelves` |
| TC-02a | `make generate` on the toy schema (imports `rp.yaml`'s modules) after each stage's schema change | no slot-name clash; `Grant.target` keeps `odrl:target` and `Page.items` keeps `rp:items` (assert through `metamodel().get_slot`) |

- [x] 1.2 `Collaboration` and `referrers` (PD-1, PD-3), `kit.collaboration`. Test first in
  `tests/unit/services/test_collaboration_referrers.py`; files `services/collaboration.py`,
  `entrypoints/kit.py`, `services/vocabulary.py`.

| ID | Input | Expected |
|---|---|---|
| TC-03 | b1, b2 on s1, b3 on s2; ada `referrers(s1)` | items (b1, Book, shelf), (b2, Book, shelf); hidden 0 |
| TC-04 | TC-03 as bob | items [b1]; hidden 1 |
| TC-05 | b3 `sequel_of` b1; a note in b2's chapter `about` b1; `referrers(b1, slot="sequel_of")` | items [b3] only |
| TC-06 | as TC-05 without the narrowing | (b2, Book, about), (b3, Book, sequel_of) |
| TC-07 | `referrers(b1, class_name="Shelf")` | empty, hidden 0 |
| TC-08 | b4 refers to s1 by `shelf` and, as bob hidden, by two slots | hidden counts b4 once |
| TC-09 | `referrers(s9)` unused | empty, hidden 0 |
| TC-09a | toy view without `rp_collections` (a schema importing only `rp_core`, `rp_annotations`); `referrers(s1)`; `members(s1)` | works; `LookupError` naming `rp_collections` |
| TC-10 | `referrers("https://elsewhere.org/x")` | `InvalidIri` |
| TC-11 | `referrers(s1, slot="nope")`; `class_name="Nope"` | `BadQuery` each |
| TC-12 | bob prohibited `read` on s1, `referrers(s1)` | `Forbidden` (as `require`) |
| TC-13 | b1's own graph names s1 in the tracking (`dcterms:creator` is about the graph) | not a referrer row |

- [x] 1.3 On Fuseki: `tests/integration/store/test_collaboration.py`; gate
  `make test-containers TEST_PATH=tests/integration/store/test_collaboration.py`.

| ID | Input | Expected |
|---|---|---|
| IT-01 | TC-03 and TC-04 | as there |
| IT-02 | TC-05 | as there |

- [x] 1.4 Docs (PD-23): `howto/reverse-references.adoc`, nav, `questions.adoc` ("Who points at
  this resource?"); `make check-docs`. Close the stage (header).

## 2. Reference collections (#79)

- [x] 2.1 `model/rp_collections.yaml` (PD-5), imported by `rp.yaml`; the toy `Shelf` mixes in
  `ReferenceCollection`; the kit's `generated_models_of` gains `rp_collections` (PD-1);
  `make generate`; snapshot; TC-02a re-run. Test first in `tests/unit/services/test_mapper.py`.

| ID | Input | Expected |
|---|---|---|
| TC-14 | `Shelf(member_class="Book", had_member=[b1], membership_rule=MembershipRule(rule_equalities=[SlotEquality(equals_slot="genre", equals_value="poetry")]))` round-trip | equal object; the rule is a skolem node in s1's graph; `rdf:type prov:Collection` is not written (mixin), `lib:Shelf` is |

- [x] 2.2 `WriteGuards` with the collection rule (PD-6); `Session(…, guards=)`,
  `open_session(…, guards=)`, `Tenancy(…, guards=)`, the kit builds it; `Transaction.add_graph`
  and `replace_graph` call it. Test first in `tests/unit/services/test_write_guards.py`.

| ID | Input | Expected |
|---|---|---|
| TC-15 | save s1 `Book` [b1, b2] (UnitOfWork) | stored; b1, b2 graphs unchanged (version tokens equal) |
| TC-16 | save s1 `Book` [s2] | `InvalidBody` naming s2; s1 not stored |
| TC-17 | save s1 `Book` [book_iri(99)] never stored | `InvalidBody` naming it |
| TC-18 | save s1 `Book` [`https://elsewhere.org/b`] | `InvalidIri` |
| TC-19 | save s1 `member_class="Chapter"` | `InvalidBody` (not a served root) |
| TC-20 | rule `equals_slot="colour"`; rule `genre = "haiku"` | `InvalidBody` each |
| TC-21 | the generic API `POST /shelves` with a wrong member (router test, `tests/unit/entrypoints/test_router.py`) | 422-class problem; nothing stored |
| TC-22 | session opened without guards saves TC-16 | stored (documented) |

- [x] 2.3 `members`, `collections_of` (explicit holders through `referrers(iri, slot="had_member")`),
  `Session.matches`, `Session.heads` (PD-6, PD-7). Test first in
  `tests/unit/services/test_collaboration_collections.py`.

| ID | Input | Expected |
|---|---|---|
| TC-23 | s1 rule `genre = poetry`; save poetry b5; `members(s1)` | b5 in members |
| TC-24 | s1 [b1] + rule matching b3 | [b1, b3] sorted, hidden 0 |
| TC-25 | as bob, s1 [b1, b2] | [b1], hidden 1 |
| TC-26 | A `Shelf` [B], B `Shelf` [b1]; `members(A, deep=True)` | [B, b1] |
| TC-27 | A [B], B [A]; deep | [A, B], ends |
| TC-28 | A [B], B hidden from bob; bob deep | [], hidden 1; B not expanded |
| TC-29 | b3 poetry listed in s1 and matched by s2's rule; `collections_of(b3)` | [s1, s2] |
| TC-30 | s2 `member_class="Shelf"` with a rule; `collections_of(b3)` | s2 not tested (class differs) |
| TC-31 | stored s1 whose rule slot the schema no longer has (write the graph without guards) | `StoredDataInvalid` naming s1 |
| TC-32 | `Session.heads([b1, b9])` | one `AggregateHead` for b1 (type `bibo:Book`, its version); none for b9 |

- [x] 2.4 `delete_cascade` (PD-8). This is the riskiest task of the change: the adversarial tester
  runs after it. Includes `Transaction._require_match` (PD-15) and the `DEFAULT_MAX_ROOTS`
  constant in `services/mapper.py` if `atomic-commit` did not export it. Test first in
  `tests/unit/services/test_collaboration_cascade.py`.

| ID | Input | Expected |
|---|---|---|
| TC-33 | `session.remove(s1, v)` with [b1, b2] | s1 gone; b1, b2 stored |
| TC-34 | ada `delete_cascade(s1, v)`, [b1] + rule match b3 | s1, b1, b3 gone, in one update request (count the fake store's updates) |
| TC-35 | caller may delete b1 not b2 (`direct(DELETE, graph_of(b1))` + `reader`) | `Forbidden` naming b2; nothing deleted |
| TC-36 | b2 changed between resolve and send (fake store hook) | `Conflict(iris=(b2,))`; nothing deleted |
| TC-36a | b3 (rule-only member) re-genred to fiction after `heads` and before send (hook) | `Conflict(iris=(b3,))`; nothing deleted |
| TC-36b | b3 re-genred between the resolve (`find`) and `heads` (hook) | the `_require_match` guard fails: `Conflict`; nothing deleted |
| TC-36c | s1 with `DEFAULT_MAX_ROOTS` explicit members | `CommitTooLarge` naming the limit; no `heads` query sent; nothing deleted |
| TC-37 | s1 lists itself and b1 | s1 and b1 gone; no `ValueError` for a double root |
| TC-38 | s1 [A], A a `Shelf` [b1] | s1 and A gone; b1 stored |
| TC-39 | stale `if_version` on s1 | `Conflict`; nothing deleted |
| TC-40 | s1 lists b9 already deleted | s1 deleted; no error |

- [x] 2.5 On Fuseki: `tests/integration/store/test_collaboration.py`; gate as 1.3.

| ID | Input | Expected |
|---|---|---|
| IT-03 | TC-15, TC-23, TC-26, TC-27 | as there |
| IT-04 | TC-34, TC-35 | as there |
| IT-05 | 50 rule shelves of `Book`, `collections_of(b3)` | correct; time noted in `develop/index.adoc` |

- [x] 2.6 Docs: `howto/reference-collections.adoc`, nav, `questions.adoc` ("How do I group
  resources I do not own?"); data-flows: the write guard. `make check-docs`. Close the stage.

## 3. Discussion (#81)

- [x] 3.1 `annotate` (PD-9): `rp_access.yaml`; `AccessRules.roles`, `AccessRules.defines`;
  `make generate`; snapshot, golden and OpenAPI files refreshed (RISK-7). `library_roles.yaml`
  is unchanged; a test role file adds `{role: reviewer, level: tenant, actions: [read, annotate]}`.
  Test first in `tests/unit/services/test_access.py`.

| ID | Input | Expected |
|---|---|---|
| TC-41 | `reviewer`: `may(…, b1, ANNOTATE)`, `may(…, b1, MODIFY)` | True, False |
| TC-42 | `librarian` (no `annotate` named) | `may(ANNOTATE)` False |
| TC-43 | `direct(ANNOTATE)` only | `may(READ)` True (implied) |
| TC-44 | `roles` for tenant `reader` + aggregate-level role on b1 + global `admin` | {reader, the aggregate role, admin}; on b2 without the aggregate role |
| TC-44a | `prohibits(…, b1, MODIFY)` with `ban(MODIFY, graph_of(b1))`; with `ban(MODIFY)` on the tenant; with none | True, True, False |

- [x] 3.2 `model/rp_discussion.yaml` (PD-10), `WritesKind.toolkit`, `served_roots` (PD-11), the
  `RESERVED_SEGMENT` hard rule; the kit's `generated_models_of` gains `rp_discussion` (PD-1);
  `make generate`; TC-02a re-run. Test first in
  `tests/unit/services/test_schema_structure.py` and `tests/unit/generation/test_hard_checks.py`.

| ID | Input | Expected |
|---|---|---|
| TC-45 | `served_roots(toy view)` | no `Comment` |
| TC-46 | `iri_types(toy view)` roots | include `rp-comment` |
| TC-47 | an own class with `rp_path: rp-notes` | hard problem `RESERVED_SEGMENT` |
| TC-48 | the toy service's router | no `/rp-comments` route |

- [x] 3.3 `comment`, `thread`, the transaction pieces `_require_present` and `_DROP_DEPENDENTS`
  (PD-12 to PD-15); the dependent pair `(oa:Annotation, oa:hasTarget)` excluded from `referrers`
  and comment referrers filtered by target readability and the thread rule (PD-3). Test first in
  `tests/unit/services/test_collaboration_discussion.py` and `tests/unit/services/test_session_transaction.py`.

| ID | Input | Expected |
|---|---|---|
| TC-49 | `reviewer` comments on b1, then modifies b1 | comment stored; modify `Forbidden` (spec rp-access) |
| TC-50 | `read` + `annotate` caller comments on b1 | stored; b1's version unchanged |
| TC-51 | `read` only | `Forbidden`; no comment graph |
| TC-52 | comment with audience `librarian`; bob `thread(b1)` | not in it; ada sees it |
| TC-53 | c2 no audience, c3 reply to c2; bob | [c2, c3], c3 names c2, motivation `replying` |
| TC-54 | reply under a hidden parent | hidden |
| TC-55 | `reply_to` a comment on b2; a missing IRI; a hidden one | `NotFound` each |
| TC-56 | blank text; audience `nobody`; reference `https://elsewhere.org/x` | `InvalidBody`, `UnknownRole`, `InvalidIri` |
| TC-57 | comment on c2 (a comment); comment on the tenant root `T` | `InvalidIri` each |
| TC-58 | comment on b1 referencing b2; `referrers(b2)` | the comment, class `Comment`, slot `comment_references` |
| TC-59 | as TC-58 with audience `librarian`, bob | not listed; hidden 1 |
| TC-59a | comment on b2 (bob prohibited `read` on b2) referencing b1, no audience; bob `referrers(b1)` | not listed; hidden 1 |
| TC-60 | `referrers(b1)` with comments on b1 | none of them |
| TC-61 | comment on b1 referencing b2, comment on b2; remove b2 | comment on b2 gone (graph and entry); comment on b1 stays |
| TC-62 | b1 removed between `get_graph` and send (fake store hook) | `Conflict(iris=(b1,))`; no comment stored |
| TC-63 | 600 comments on b1; remove b1 | one update request; no comment graph left; no `CommitTooLarge` |
| TC-64 | thread order: three comments with injected clock t2, t1, t1 | by created, then IRI |

- [x] 3.4 On Fuseki; gate as 1.3.

| ID | Input | Expected |
|---|---|---|
| IT-06 | TC-50, TC-52, TC-53 | as there |
| IT-07 | TC-61, TC-63 | as there |

- [x] 3.5 Docs: `howto/discussion.adoc`, nav, `questions.adoc` ("Can a reviewer comment without
  editing?"); data-flows: delete removes dependents. `make check-docs`. Close the stage.

## 4. Workflow (#80)

- [ ] 4.1 `model/rp_workflow.yaml` (PD-16), `from_state_iri`/`to_state_iri` on `Comment`, the
  kit's `generated_models_of` gains `rp_workflow` (PD-1), TC-02a re-run,
  `RpAnnotation.workflow` and the `WORKFLOW` hard rule (PD-18); the toy `Book` mixes in
  `UnderWorkflow` and is annotated `workflow: review`; `tests/fixtures/library/review.workflow.yaml`
  (PD-17's example); `make generate`; snapshot. Test first in
  `tests/unit/generation/test_hard_checks.py`.

| ID | Input | Expected |
|---|---|---|
| TC-65 | class annotated `workflow: review` without `UnderWorkflow` | hard problem `WORKFLOW` |
| TC-66 | root with `UnderWorkflow`, no annotation | hard problem `WORKFLOW` |
| TC-67 | `workflow: Review` | hard problem (pattern) |
| TC-68 | subclass of an annotated root | no problem (inherited) |
| TC-68a | the tenant root class annotated `workflow: review` | hard problem `WORKFLOW` |

- [ ] 4.2 `services/workflows.py` (PD-17), `InvalidWorkflow`, `ServiceKit(workflows=)`,
  `install_service(workflows=)`. Test first in `tests/unit/services/test_workflows.py`.

| ID | Input | Expected |
|---|---|---|
| TC-69 | the review file | loaded; `Book` maps to it |
| TC-70 | a transition to `archived` | `InvalidWorkflow` naming the transition |
| TC-71 | `initial_state: archived` | `InvalidWorkflow` |
| TC-72 | a role `editor` the role file lacks | `InvalidWorkflow` naming it |
| TC-73 | two transitions draft → in_review; two files named `review` | `InvalidWorkflow` each |
| TC-74 | `Book` annotated, no workflow files given to the kit | kit construction raises `InvalidWorkflow` |
| TC-75 | not YAML; a list instead of a mapping; `workflow_states` missing | `InvalidWorkflow` naming the file |

- [ ] 4.3 The workflow rule of `WriteGuards` (PD-19). Test first in
  `tests/unit/services/test_write_guards.py`.

| ID | Input | Expected |
|---|---|---|
| TC-76 | add b1 without status; `UnitOfWork.get` | status `…/review/draft` |
| TC-77 | add b1 with status `…/accepted` | `Forbidden`; nothing stored |
| TC-78 | replace b1 (draft) with status accepted; generic `PUT` too | `Forbidden`; b1 in draft |
| TC-79 | replace b1 without status (`label` changed) | stored; status draft |
| TC-80 | a transaction holding `_allow_state(b1, accepted)` replaces with status accepted | stored |
| TC-80a | `session.transaction()` without `_allow_state`, replace with status accepted | `Forbidden`; no public argument allows it (signature test) |
| TC-81 | `Shelf` (no workflow) writes | unchanged behaviour; no extra query |

- [ ] 4.4 `transition`, `transitions`; dependent link `prov:used` (PD-15, PD-20 to PD-22). The
  adversarial tester runs after it. Test first in
  `tests/unit/services/test_collaboration_workflow.py`.

| ID | Input | Expected |
|---|---|---|
| TC-82 | ada b1 draft → in_review | status in_review; new version returned |
| TC-83 | draft → accepted | `Conflict` naming both; b1 draft |
| TC-84 | bob (`reader`) draft → in_review | `Forbidden`; b1 draft |
| TC-85 | in_review → draft without comment; with "  " | `InvalidBody` each |
| TC-86 | stale `if_version` | `Conflict`; no record, no comment |
| TC-87 | p1 draft → in_review "ready", p2 → accepted; `transitions(b1)` | two records in order, agents p1, p2, times; the first's `transition_comment` is the IRI of the thread's "ready" comment |
| TC-87a | ada (librarian) with `ban(MODIFY, graph_of(b1), ADA)`; draft → in_review | `Forbidden`; b1 draft; no record |
| TC-88 | in_review → accepted with "fine" | `thread(b1)` ends with "fine" by ada, from in_review, to accepted, no audience; one update request |
| TC-89 | a plain replace after transitions | records unchanged |
| TC-90 | remove b1 | records and comments gone |
| TC-91 | b1 stored before the annotation (no status) → in_review | allowed from the initial state |
| TC-92 | stored state `retired` not in the file | read as stored; any transition `Conflict`; label replace passes |
| TC-93 | aggregate-level grant of `librarian` on b1 only | may transition b1, not b2 |
| TC-94 | `transition(shelf)` | `InvalidBody` |
| TC-95 | two transitions from one version (sequenced on the fake store) | first stored, second `Conflict` |
| TC-96 | `referrers(b1)` after transitions | no records listed |

- [ ] 4.5 On Fuseki; gate `make test-containers TEST_PATH="tests/integration/store/test_collaboration.py tests/integration/api/test_router.py"`.

| ID | Input | Expected |
|---|---|---|
| IT-08 | TC-82, TC-87, TC-88 | as there |
| IT-09 | TC-78 through the generic `PUT` | refused; b1 in draft |
| IT-10 | TC-90 | as there |

- [ ] 4.6 Docs: `howto/workflow.adoc` (file format, the stable `id`, RISK-4), nav,
  `questions.adoc` ("How do I put a resource through review?"); the adoption guide's kit
  arguments (`workflows=`). `make check-docs`. Close the stage and the change: archive it after
  the last merge.
