# Open questions and the answers the lead assumed (2026-11-19)

Secondary input, never groomed. The developer asked for the work to be executed in one go; each
answer below is a leader's choice the developer may overrule at review.

| Id | Question | Assumed answer | Recorded as |
|---|---|---|---|
| Q-1 | Split `howto/adopt.adoc` or rewrite it? | Split verbatim by its steps; rewrite nothing | DEC-2 |
| Q-2 | Tutorial on the toy library or a new minimal app? | A new one-class app, tested | DEC-3 |
| Q-3 | Copy requirements into the docs? | No: summarise and link to `openspec/specs/` | DEC-4 |
| Q-4 | Hand-written or generated API reference? | Generated, checked for freshness | DEC-6 |
| Q-5 | Keep a "Concepts" section? | No: explanations live in Architecture | DEC-8 |
| Q-6 | Merge root README/INSTALL/CONTRIBUTING into the docs? | No: keep as repository entry points, link | DEC-9 |
| Q-7 | Touch the SOA background? | No, label only | No-gos |
| Q-8 | Use cases: who are the actors? | Application developer, operator, API client (end user's app), toolkit developer | design.md |

Risks asked (what outside could change, who is hurt, what we do): see design.md RISK-1..RISK-4.
