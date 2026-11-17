<!-- SECONDARY INPUT: preserved, never groomed. The EPIC (../proposal.md) is the shaped truth. -->

# Seed: tracing and structured logging (from the manual revision notes)

This change was cut from the developer's manual revision of 2026-11-16. Its sources live in the
`manual-revision-notes` change and are not copied here:

- `../../manual-revision-notes/inputs/seed.md`: the developer's note, verbatim: "the logging must be
  aligned to best loggin practices in OpenTelmetry".
- `../../manual-revision-notes/inputs/analysis.md` §3.3 (logging and OpenTelemetry) and §5.2 item 5
  (the log-attribute set as a concept).
- `../../manual-revision-notes/inputs/improvements.md`: the two ids this change owns.
  - **B-4**: `opentelemetry-api` spans around the Store port, `Session.commit`, migrations, sweep,
    relay rounds and bus handlers; the dependency declared; the application-side set-up documented.
  - **D-3**: one `LogContext` model with OpenTelemetry semantic-convention attribute names plus an
    `rp.*` namespace; every log call a constant message, attributes and `exc_info`.
- `../../manual-revision-notes/inputs/keep.md`: stdlib `logging` with module loggers and no handler
  configuration stays (§3.3).
- `../../manual-revision-notes/inputs/answers-2026-11-17.md`: the slicing (this change is third,
  after `manual-revision-notes` and `technical-models`) and Q-2 (the log context is a technical
  model, generated from LinkML, kept apart from the domain models).

Rule in force: P-0010 (logging follows OpenTelemetry practice: constant message, semconv attribute
names, `exc_info`, spans through `opentelemetry-api` only). A-7 (the duplicate ERROR log of
`MessageLimitExceeded`) is delivered by `manual-revision-notes`, not here.
