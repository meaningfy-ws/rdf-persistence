# Acceptance: narrowed-slot-override

TINY appetite: the demo is offered to the developer and may be skipped. PR #427.

## Demo offered

In the worktree, show:

1. `uv run pytest tests/generator/integration/test_generated_code_imports.py -k "narrowing or narrowed"`:
   a generated project reproducing #417 (`OnePartHolder` narrowing `has_part` to one required
   value) is mypy-clean, and the narrowed keyed slot validates one value while the parent still
   refuses a repeated key.
2. The generated line of the narrowed field ends with `# type: ignore[assignment]`.
3. MWB2's `rp-generate --check` on EA round 26 against the branch (asked in PR #427, RISK-3).

## Result

Pending the developer's verdict. The lead recommends skipping the demo: TC-1 and TC-4 are the demo
itself, run by CI's "Generator tests" job, and the real proof is MWB2's check of item 3.
