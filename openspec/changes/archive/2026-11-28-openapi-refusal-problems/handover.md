# Hand-over: openapi-refusal-problems

## Where it stands
One stage, one PR into `develop` (task 1.4 of `consumer-write-rules`, #457). Tasks 1.1 to 1.3
done; review `critical=0`; check 17 items, unmet 0. Merged with `--admin` on a green local
`make check-all` of the rebased head, at the developer's word. Next: archive the change (its own
PR), close #457.

## Decided since the PLAN
D-1 to D-9 (design.md, Delivery decisions). The developer decided D-9 (proceed past the CRITICAL
pre-PR rating); the lead decided the rest.

## Open
- **#459:** the review's and the checker's findings under the floor (W-1 a `$defs` name two
  listed classes share is refused at start-up; W-2 to W-5 tests; S-1 to S-6 tidy-ups).
- `consumer-write-rules`' RISK-3 (the document did not list the classes) is closed by this change.
