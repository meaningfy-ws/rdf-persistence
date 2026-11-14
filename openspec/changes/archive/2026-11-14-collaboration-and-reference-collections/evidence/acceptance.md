# Acceptance: collaboration-and-reference-collections

> Derives from: EPIC `collaboration-and-reference-collections` (proposal.md, issues #78 to #81).

**Verdict: accepted by the developer, 2026-11-14** ("fine go ahead"), after the demo below, run
by the lead the same day, and the three decisions listed at the end, none of which the developer
overruled.

## What was shown (2026-11-14, real Fuseki, the toy library)

Run end to end through what a consumer uses: the generic HTTP API for the tenant, books, shelves
and grants; `kit.require_aggregate` and `kit.collaboration` for the collaboration calls. One
throwaway script, four scenes, all four passed (22 s). IRIs are cut to eight characters.

People: ada created the tenant (role `librarian`) and has a direct `annotate` permission; bob has
the role `reader` and a direct `annotate` permission; bob is prohibited `read` on one book where
a scene says so.

### 1. Reverse references (#78)

```
1. s1=a822bf31 b1=ff57512b b2=35bfb606 (shelf=s1) b3=23a7fa48 (sequel_of b1)
2. ada referrers(s1) -> [('35bfb606', 'Book', 'shelf'), ('ff57512b', 'Book', 'shelf')], hidden_count=0
3. bob is prohibited read on b2 (35bfb606)
4. bob referrers(s1) -> [('ff57512b', 'Book', 'shelf')], hidden_count=1
   b2 IRI in the answer text: False | b2 id segment in it: False
5. bob referrers(s1, slot='sequel_of') -> items=[], hidden_count=1
```

The hidden book is counted and never named; narrowing does not change the count.

### 2. Reference collections (#79)

```
1. s1=b2f36c63 b1=4342c26f b2=1c45bd34 (fiction) b3=1c0cb0a2 (poetry)
2. PUT s1 as collection (member_class Book, had_member [b1], rule genre=poetry) -> 200
3. POST a shelf naming a shelf as member of class Book -> 422 invalid-body
   "not stored aggregates of Book: [.../shelves/b2f36c63-...]"
4. ada members(s1) -> ['1c0cb0a2', '4342c26f']            (b1 named, b3 by the rule)
5. ada collections_of(b3) -> ['b2f36c63']                 (s1)
6. bob (prohibited read on b3) members(s1) -> ['4342c26f'], hidden_count=0
7. ada delete_cascade(s1) -> 1 update request(s)
8. GET s1 -> 404   9. GET b1 -> 404   10. GET b3 -> 404   11. GET b2 -> 200
```

A member bob may not read that only meets the rule is neither listed nor counted (PD-28). The
cascade removed the shelf and both members in one request and left the book outside it.

### 3. Discussion (#81)

```
1. ada c1=19ef938f 'check chapter 3' (audience librarian, references other=843dff02);
   bob c2=b6aa3487 'nice'; ada c3=b1ba511a 'thanks' replying to c2
2. bob thread(b) -> [('b6aa3487', 'nice'), ('b1ba511a', 'thanks')]          (2, not c1)
3. ada thread(b) -> [('19ef938f', 'check chapter 3'), ('b6aa3487', 'nice'), ('b1ba511a', 'thanks' -> b6aa3487)]
4. referrers(other) as ada -> [('19ef938f', 'Comment', 'comment_references')]
5. book version token unchanged by the comments: True
6. bob PUT book -> 403
7. ada comments c4=60161f51 on other, referencing b
8. DELETE b -> 204
9. stored comment graphs that target b -> []
10. thread(b) -> []
11. thread(other) -> [('60161f51', 'see b')]                                 (c4 remains)
```

Bob comments without the right to edit; the comment for librarians is hidden from him; the
generic `DELETE` took the three comments with the book and left the one that only referenced it.

### 4. Workflow (#80)

```
1. POST book -> workflow_status = .../review/draft
2. ada PUT workflow_status=accepted -> 403; book still draft
3. bob transition(in_review) -> Forbidden: the move to in_review needs one of the roles ['librarian']
4. ada transition(in_review, comment='ready') -> new version
5. book reads .../review/in_review
6. ada transition(accepted) at the OLD version -> Conflict: .../books/9943f9cf-... was changed by
   someone else since it was read
7. ada transition(accepted) at the current version -> book reads .../review/accepted
8. record: agent=ada from=draft to=in_review time=2026-11-14 09:53:18.068966+00:00 comment=3f9a9675
9. record: agent=ada from=in_review to=accepted time=2026-11-14 09:53:18.361926+00:00 comment=None
10. thread: 'ready' id=3f9a9675 from=draft to=in_review audience=None
11. GET books?workflow_status=<in_review> -> []
12. GET books?workflow_status=<accepted>  -> ['9943f9cf']
13. DELETE book -> 204
14. transition records using the book -> []     15. comments targeting the book -> []
16. transitions(book) -> []                     17. thread(book) -> []
```

A plain write cannot set the state; a reader cannot move the book; a stale version is a conflict;
each move left a record and the comment went into the thread; the listing by state is the review
queue; deleting the book took its history with it.

## What the developer is asked

Accept, or name what is wrong. Three decisions the lead took during delivery change what the EPIC
said and are the developer's to overrule (proposal.md "As built"; design.md):

1. A member that only meets a collection's rule and that the caller may not read is neither
   listed nor counted, and a cascade leaves it (PD-28 item 1; narrows DEC-7).
2. A generic route answers only for an aggregate of its own class, else 404 (PD-30 item 1; the
   EPIC said no new generic routes, and none was added, but the existing ones changed).
3. A role of the caller's token counts for a comment's audience and for a transition only if the
   role definitions define it at system level (PD-30 item 3; narrows PD-9).
