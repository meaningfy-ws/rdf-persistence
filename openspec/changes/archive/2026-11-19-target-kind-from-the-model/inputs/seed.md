# Seed: target-kind-from-the-model (secondary; never groomed)

Shaped in one session with `domain-model-per-theme`, then split by the developer ("okay yes
split"), this one first. The seeds, the Q&A and the attack on the first PLAN are in
`openspec/changes/domain-model-per-theme/inputs/seed.md`. The parts that seed this EPIC:

- RISK-9 of `thematic-structure`: "I would make it mandatory for consumers too."
- "why do we even have to separate these 'kinds'?" — the lead's answer: the kind is stated three
  times (module annotation, `pyproject.toml` key, folder); one source proposed, accepted.
- From the attack: base the kind on the modules a target generates, not every module of its folder;
  a package without a `generated` segment must fail too; the exempt packages are exempt from the
  whole rule; about 25 inline configs in the generator's tests use layer-less packages; the toy
  library's package appears in about 60 files.
