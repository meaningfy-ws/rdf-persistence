# Acceptance: aggregate-events

**Verdict:** accepted by the developer on 2026-11-16 ("i accept the demo, continue"). The
developer also validated the delivery decisions D-1 to D-21 ("decissions are fine").

**What was shown:** the final report of the epic session (session J): the two merged pull requests
(#124 the outbox mark in the commit, the relay, the `EventBus` port, `RedisEventBus` on FastStream
in the extra `events`, incoming events handed to the message bus; #126 the server-sent-events route
`GET /{tenant}/rp-events` with access filtering and resume, and the end-of-epic review's fixes
D-14 to D-21), the challenge each stage passed, and the test status on the final head (7355 tests
passed at 95.78% coverage; 267 container tests passed; CI green on develop after the merge).

**Demo:** `tests/feature/events.feature` and `tests/feature/incoming_events.feature`: a commit
relayed to the bus after a crash, an incoming event from another deployment handed to the message
bus, a reader following a tenant and seeing only what it may read, and a resume with
`Last-Event-ID`.

**Left open at acceptance:** issue #125 (the review findings under the floor and the checker's text
fixes); the browser `fetch-event-source` snippet of the how-to and the Redis older than 8.4
fallback are untested. None blocks a consumer.
