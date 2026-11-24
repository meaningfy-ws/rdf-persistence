# Clarity gate: aggregate-guards

The gate was run by a fresh reviewer who did not write the PLAN, after an attack against the code.

- run 1, 2026-11-24, 8.2/10, fail. The reviewer attacked and gated the PLAN and found 10
  counterexamples:
  - the port's other implementer, `Recording`;
  - no `may_read` on the delete path;
  - a `Conflict` inside a rule turned into a 500;
  - the reader had no decoder and no cache;
  - the Context was wrong about the system-database session and restore;
  - the root's types on remove;
  - the comment exemption;
  - a stale `If-Match` against a rule's refusal;
  - collected triples that do not decode.
- run 2, 2026-11-24, 9.3/10, pass. Same reviewer, re-gating only the gaps: all closed. Two nits
  were fixed after the run: the type of D-7's `may_read`, and the import in the delete-rule
  example.

No gaps were accepted. Scenarios: the issues' Acceptance lists and the owner's four edge cases, in
`specs/rp-service-api/spec.md`. The owner signs them off with the PR.
