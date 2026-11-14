# Acceptance: cross-aggregate-unique-keys

> Derives from: EPIC `cross-aggregate-unique-keys` (proposal.md).

**Verdict: accepted by the developer, 2026-11-14**, after #96 and #97 were merged. The developer
judged the leader's summary of the run below, not its raw output.

## What was shown (2026-11-14, real Fuseki, the toy library)

`make test-containers TEST_PATH="tests/integration/store/test_unique_keys.py tests/integration/api/test_router.py"`:
13 passed in 65.89 s. The cases put to the developer:

1. 20 rounds of two sessions adding a book with one fresh ISBN at the same moment: in each round
   one book was stored and the other add raised `KeyConflict` (IT-01).
2. Replacing a book with another book's ISBN was refused; both books kept their versions and
   triples (IT-02).
3. Over HTTP, ISBN "1" was accepted once in each of two tenants; a second POST in one tenant got
   409 `key-conflict` (IT-03).
4. `key_duplicates()` listed the two books sharing an ISBN and left the store unchanged (IT-05).
5. A keyed add in a tenant of 1,000 books stayed under the 0.5 s limit (IT-06; measured mean
   0.049 s, design.md RISK-1).

## Left for the developer to overrule

The leader's own decisions, reported with the acceptance question and at the close: D-1, D-2,
PD-16, RISK-7, D-5 F-1 and F-5 (design.md), and the "As built" table of proposal.md.
