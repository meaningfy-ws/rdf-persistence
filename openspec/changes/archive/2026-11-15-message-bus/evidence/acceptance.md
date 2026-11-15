# Acceptance: message-bus

> Derives from: EPIC `message-bus` (proposal.md, DEC-1 to DEC-13).

**Verdict: accepted by the developer, 2026-11-15** ("Accept"), after the demo below, run by the
lead on `develop` once all four stages were merged (#107, #110, #114).

## What was shown (2026-11-15, the toy library, the fake store)

One throwaway script (`temp/demo_message_bus.py`, not kept), five parts, all five held. It used
what a consumer uses: the toy service over HTTP, `kit.collaboration`, `bootstrap`, `bus.handle`,
`RecordingObserver`.

```
== 1. A generic HTTP replace records one activity ==
activity: Replace, made by ada: True
replaced book: 04739a13-499c-40f8-ad57-905599688dd9 (the PUT book: True)
invalidated version == ETag before: True
generated version   == ETag after:  True
== 2. A transition is kept after the book is deleted ==
transitions(book): draft -> in_review
book deleted; Transition activities still stored: 1
transitions(book) now answers: NotFound
== 3. A consumer's command through the bus ==
new version returned: True (differs from the old, equals the stored one)
stored activity types: Activity, ApproveBook, Transition
observer of Transition got: ApproveBook, draft -> in_review, principal ada
observer of Activity got: ApproveBook, draft -> in_review, principal ada
== 4. A use case over several books is one commit ==
activities stored: 1; class ShelveBooks; shelf_note 'top shelf'
generations: ['00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000002']
invalidations: ['00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000002']
== 5. A loop is stopped ==
commands that ran: 5; the caller got MessageLimitExceeded: message limit 5 reached
== all five shown ==
```

The script also logged, at error level, `message limit 5 reached by ShelveBooks urn:uuid:…`
(design.md D-11 c).

## What the demo did not show

- A real Fuseki store: the container suite ran on every stage (stage 3 and 4: 259 passed), and the
  cost of the activity was measured there (develop/index.adoc, the durations table).
- A consumer's own handler replacing the toolkit's `Transition` handler; it is tested
  (`tests/unit/services/test_messagebus_wiring.py`).
