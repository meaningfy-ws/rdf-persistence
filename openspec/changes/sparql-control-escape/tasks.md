> Derives from: EPIC `sparql-control-escape` (proposal.md), GitHub issue #270.

## 1. The escape

- [x] 1.1 Test first: add `"\x1f0000"` to `HOSTILE` and the property
  `test_a_control_character_followed_by_hex_digits_round_trips` in
  `tests/unit/core/test_sparql.py`; parametrize the Fuseki round trip in
  `tests/integration/store/test_session.py` with it. See them fail with rdflib's
  "Invalid unicode code point". Gate: `uv run pytest tests/unit/core/test_sparql.py`.
- [x] 1.2 Write control characters as `\U` with 8 digits in `_string` (PD-1). Gates:
  `make test-fast check-quality` (domain changed), then `make check-all` and
  `make test-containers`.

## Roadmap

- [x] 1.1 · [x] 1.2

## Verification

`make check-all` and `make test-containers` green; `openspec validate sparql-control-escape
--strict` passes; issue #270 closed by the PR.
