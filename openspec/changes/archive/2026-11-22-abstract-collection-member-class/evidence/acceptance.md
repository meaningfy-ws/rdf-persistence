# Acceptance: abstract-collection-member-class

2026-11-22, retrospective. The fix was delivered as a bug-fix session (PR #287) and accepted by merge
on green CI under P-0013; the spine was written afterwards at the developer's request. What stands in
for a demo:
- IT-1: the converted toy shape generates and passes the generator's type check; it fails on the
  parent commit.
- MWB2's phase-B `.qea`, converted with its `convert-model` flags: `rp-generate --check` went from
  5 `Incompatible types` errors to none.
- `make check-all` and `make test-containers` green locally; CI green on #287.
- No clarity gate was run: the PLAN records delivered work.
