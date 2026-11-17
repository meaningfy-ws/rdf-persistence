# Docs owed: technical-models

None owed by this change. Task 4.3 and its fix (D-51) wrote every page the PLAN named and the
items owed from stages 1 to 3: the pre-split docstrings (stage 1 floor L3 S1), `pydantic_split.py`'s
module docstring (stage 3 L2 S6), `develop/index.adoc`'s `max_roots=500` (stage 3 L2 S8), and the
how-to's table of every removed keyword and constant (D-42). The cold reader's Critical and
Warnings on `howto/settings.adoc` and `howto/adopt.adoc` were fixed before the PR.

Left to later changes, by design:

- Retiring the `iris.py` wrappers (E-6) and the theme prefix: `thematic-structure`.
- The generator's hand bootstrap when it imports a record it generates (stage 1 floor L4+L5 W3):
  `generator-package` moves the generator and removes the cause.
