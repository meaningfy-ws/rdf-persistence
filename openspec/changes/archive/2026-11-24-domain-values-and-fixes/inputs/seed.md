<!-- Secondary input: never deleted or groomed. The EPIC (proposal.md) is the shaped truth. -->

# Seeds

## The developer's request (2026-11-23)

> Fix rdf-persistence #301 (domain value types: generate non-stored classes and enums for the domain
> layer) first, then #303, #302 and #300, each as its own PR into develop. MWB2 v2-05 stage 1 waits on
> #301; MWB2 v2-02's open tests wait on the others.
>
> Work independently, put them in an epic, then shape it, then plan it, then start implementing it.
> Work autonomously as a team leader, with subagents.

## Read during intake

- Issues #301, #303, #302, #300 (bodies as filed; acceptance criteria copied into the PLAN's tests).
- `rdf_persistence_generation/checks/boundary.py`, `checks/hard.py` (`_stored_classes`), `steps.py`
  (the boundary step and `derived_kind`).
- `rdf_persistence/model/rp_core.yaml` (`ModuleKind`).
- `tests/generator/unit/test_technical_exemption_adversarial.py` (how scratch projects are built).
- `docs/modules/ROOT/pages/architecture/generation.adoc#cross-target`.
- `rdf_persistence_generation/testkit/strategies.py` (`aggregate`, `_scalar`, `_fields_for`).
- `rdf_persistence/schema/services/schema_structure.py` (`is_owned`, the inlining predicate ~l.537).
- `rdf_persistence/__init__.py` (`_LAZY_MODULES`), `api/entrypoints/negotiation.py`,
  `howto/workflow.adoc` l.191-196, `architecture/api.adoc` l.271.
- The archived `slot-resolution` change (format and the one-place-for-all-readers decision).

## Questions and answers

No round was sent: the developer asked for independent work. Each open question was decided by the
lead and recorded as a `DEC-` in `proposal.md`, with the option rejected:

| Question | Decided |
|---|---|
| A module kind or a class annotation? | Module kind `value` (DEC-1) |
| Which rules does a value class skip? | Those a technical class skips; root refused (DEC-2) |
| Who may import a value module? | Domain and technical; it imports domain, value, toolkit (DEC-3) |
| A new target kind? | No; domain folder (DEC-4) |
| May a stored class hold a value class? | No; its enums yes (DEC-5) |
| Where does the #303 fix sit? | One place all readers use (DEC-6) |
| Export `matched_version` too? | Yes, the how-to names it (DEC-8) |
| One PR or four? | Four, as asked (DEC-9) |

## Risks (R-0002, asked of the context by the lead)

- What outside the work could change: MWB2 locks a develop commit; a breaking generated-code change
  (#303) reaches it on the next lock refresh. Who is hurt: MWB2 code that built the embedded object.
  What we do: say it in the PR and the release notes (RISK-2 in design.md).
- The metamodel enum change regenerates every toolkit artefact that lists `ModuleKind`; accepted,
  checked by `make check-generated`.
