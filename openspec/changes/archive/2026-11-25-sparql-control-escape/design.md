<!-- PLAN (design half). PLAN = this file + tasks.md. -->

> Derives from: EPIC `sparql-control-escape` (proposal.md), GitHub issue #270.

## Context

`_string` (`rdf_persistence/core/domain/sparql.py`) escapes `\`, `"`, `\n`, `\r`, `\t` by
`_STRING_ESCAPES`, turns a `u` or `U` after an escaped backslash into `\U` with 8 digits (#108),
then writes the rest of `[\x00-\x1f\x7f]` as `\u` with 4 lower-case digits. rdflib expands
codepoint escapes over the whole request with `\\u([0-9a-f]{4}(?:[0-9a-f]{4})?)`, `re.I`
(`rdflib/plugins/sparql/parser.py`, `expandUnicodeEscapes`): `\u` and `\U` alike, 4 or 8 digits,
greedy.

## Goals / Non-Goals

**Goals:** DEC-1. **Non-Goals:** the EPIC's No-gos.

## Decisions

- **PD-1**: `_CONTROL` writes `\U{ord:08X}`, the form `_AFTER_BACKSLASH` already writes, so one
  escape form serves both. The regex takes at most 8 digits, so the text after it is never read
  into it. Fuseki (Jena) reads `\U` with exactly 8 digits, as SPARQL 1.1 defines.

## Algorithm / approach

`"\x1f0000"` → `"\U0000001F0000"`; rdflib reads `\U0000001F` then the text `0000`.

## Error matrix

| Failure mode | How it is detected | Expected handling |
|---|---|---|
| Control character then hex digits forming an invalid code point | rdflib `ValueError` | cannot happen: 8 digits are consumed exactly |
| Control character then hex digits forming a valid code point | silent change of the stored string | cannot happen, same reason; the property test asserts equality |

## Testing

Unit: the issue's example joins `HOSTILE`, so every hostile-literal and template test covers it;
a Hypothesis property over each control character followed by 1 to 9 hex digits of either case.
Container: the Fuseki round trip of a hostile literal is parametrized with the issue's example.

## Open Questions

None.

## Review fixes (lead's decisions after the one-pass review, 2026-11-25)

- **RF-1** (L2). The spec delta's new sentence ("read back exactly as given") is a deliberate
  strengthening; the proposal's Modified Capabilities now says so.
- **RF-2** (L2). A unit test pins the rendered form `"\U0000001F0000"`, so a switch to another
  escape cannot pass unnoticed.
- **RF-3** (L2). The property carries `@example`s for both reported readings (`\x1f`+`0000`,
  invalid; `\x01`+`0000`, the silent U+10000), independent of the `.hypothesis/` database.
- **RF-4** (L5). One `_codepoint_escape` serves `_AFTER_BACKSLASH` and `_CONTROL`, so the two
  substitutions share one escape form.
- Not taken: none. The Jena claim stands on `make test-containers`.
