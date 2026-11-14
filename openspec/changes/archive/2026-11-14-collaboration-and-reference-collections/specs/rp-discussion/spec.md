<!-- Capability: rp-discussion. Change: collaboration-and-reference-collections (GitHub issue #81). -->

## ADDED Requirements

### Requirement: A comment can be posted on any aggregate

`collaboration.comment(iri, text, audience, references, reply_to)` SHALL store a comment as an
aggregate of its own (an `oa:Annotation` targeting `iri`, with a textual body) carrying the
session's principal as author, the time, an optional audience of roles, optional references to
other resources of the tenant and an optional comment it replies to. Posting SHALL require the
`annotate` action on the target and SHALL leave the target's graph and version token unchanged. A
reply SHALL name a comment on the same target.

#### Scenario: a reader who may annotate
- **GIVEN** a principal holding `read` and `annotate` but not `modify` on book b
- **WHEN** it comments on b
- **THEN** the comment is stored and b's version token is unchanged

#### Scenario: no annotate permission
- **GIVEN** a principal holding only `read` on book b
- **WHEN** it comments on b
- **THEN** the comment is refused as forbidden and nothing is stored

### Requirement: A thread shows only what the caller's roles may see

`collaboration.thread(iri)` SHALL return the comments targeting `iri`, oldest first, with their replies,
leaving out every comment whose audience names none of the caller's roles on the tenant or the
aggregate, nor a role defined at system level that the caller's token carries. A role name in a
token that is not defined at system level SHALL NOT count. A comment with no audience SHALL be
visible to every caller who may read the target. A comment SHALL NOT be readable, replaceable or
deletable through a generic aggregate route, whatever the IRI policy.

#### Scenario: an audience the caller is not in
- **GIVEN** a comment on book b with audience `librarian`
- **WHEN** a principal granted only `reader` reads b's thread
- **THEN** the comment is not in the thread

#### Scenario: a token role with the name of a tenant role
- **GIVEN** a comment on book b with audience `librarian`, a role defined at tenant level only
- **WHEN** a principal granted only `reader`, whose token carries a role named `librarian`, reads b's thread
- **THEN** the comment is not in the thread

### Requirement: Comments are found through what they reference

A comment's references SHALL be stored as slots of the comment aggregate, so that the referrers
of a referenced resource include the comment, filtered by the caller's access like any referrer.
Deleting an aggregate SHALL delete the comments that target it and keep the comments that only
reference it.

#### Scenario: a comment that mentions another book
- **GIVEN** a comment on book b1 referencing book b2
- **WHEN** a session lists the referrers of b2
- **THEN** the comment is among them

#### Scenario: deleting the target
- **GIVEN** a comment on b1 referencing b2, and a comment on b2
- **WHEN** b2 is deleted
- **THEN** the comment on b2 is gone and the comment on b1 remains

### Requirement: A transition with a comment posts it into the thread

A workflow transition made with a comment SHALL post that comment into the aggregate's thread,
naming the source and target states, with no audience restriction, in the same update as the
transition.

#### Scenario: a review decision in the thread
- **WHEN** a `librarian` moves book b from `in_review` to `accepted` with comment "fine"
- **THEN** b's thread ends with a comment "fine" by that principal naming `in_review` and
  `accepted`
