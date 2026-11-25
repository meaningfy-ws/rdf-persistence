# Docs owed: generator-module-cycles

No docs owed. Each stage wrote its docs with its code and passed `make check-docs`:

- Stage 1 (#358): `architecture/generation.adoc` (`[[module-cycles]]`), `user-manual/generate.adoc`
  (`[#module-cycles]`), `CHANGELOG.md` *Fixed* (#208).
- Stage 2 (#368): `reference/uml-conventions.adoc` (`#packages`, `#module-kind`, `#shared-slots`,
  the problems table, incl. D-9's refusal), `howto/uml-to-linkml.adoc`, `CHANGELOG.md` BREAKING.

The stage 2 checker was the cold reader of the changed reference sections and the how-to.
