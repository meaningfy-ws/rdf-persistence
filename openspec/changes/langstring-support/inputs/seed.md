# Seeds: langstring-support (secondary; never groomed)

The EPIC (`../proposal.md`) supersedes these seeds but does not replace them.

## Issue #209, verbatim (read 2026-11-22, open, no comments, no labels)

**toolkit: support language-tagged strings (rdf:langString)**, opened 2026-11-20 by the developer.

> ## Problem
>
> The toolkit has no LinkML range for language-tagged strings
> (`rdf:langString`). A model cannot declare a multilingual text slot, and
> `api/services/documents.py` (around line 524) replaces each value object
> `{"@value": v, "@language": l}` by `v`, so a language tag read from the
> store is lost in documents.
>
> ## Need
>
> Models in the SEMIC style use `rdf:langString` for multilingual text. Both
> plain strings and language strings must be supported, and a language tag
> must never be dropped.
>
> ## Scope
>
> - a language-string range in the toolkit metamodel, with its Pydantic,
>   SHACL (`sh:datatype rdf:langString`), JSON-LD and TypeScript output;
> - reading and writing it without losing the tag (documents included);
> - `rp-uml2linkml` then maps `rdf:langString` to it (uml-to-linkml D-12);
>   until then the converter refuses such an attribute and names it.
>
> Refs: #196

## Related sources read

- Issue #196 (the UML-to-LinkML converter; consumer Mapping Workbench 2, change `domain-model-v2`
  S6-12 and EPIC `v2-02-model-from-ea`), body and its one comment: no rule there asks for a
  language string; #209 was found while writing the converter's XSD map.
- `openspec/changes/archive/2026-11-21-uml-to-linkml/proposal.md` (row "The XSD datatype map":
  `rdf:langString` and `rdf:PlainLiteral` fail the run until the toolkit has a language-string
  range; #209 stays open) and `design.md` (the `[no_rule]` message naming #209).
- `openspec/specs/rp-uml-import/spec.md`, scenario "a language string" (the refusal in force).
- `docs/modules/ROOT/pages/reference/uml-conventions.adoc#lang-string` and
  `howto/uml-to-linkml.adoc` (the refusal, documented).
- `openspec/changes/archive/2026-11-17-manual-revision-notes/` (TC-22 to TC-24b: a tagged literal
  keeps its tag in JSON-LD; plain JSON shows a plain string) and `CHANGELOG.md` ("BREAKING: a
  language-tagged value keeps its tag in JSON-LD").
- `docs/modules/ROOT/pages/background/soa/decisions.adoc` DEC-35 / ADR-15 (`LangString` as a
  language map), `angles/dx.adoc` (G6, `LangString = dict[lang, str]`, an open question on the
  shape), `angles/codegen.adoc` (the tag is lost along the stock LinkML chain), `integration.adoc`
  C3 (no `@language` container from `gen-jsonld-context`).
- `openspec/specs/rp-generation/spec.md` "A generated field can hold a toolkit type" (the
  precedent for a toolkit range with its own Python class).

## Codebase notes (develop `25e23156`, in this worktree)

- `rdf_persistence/api/services/documents.py:547` `_without_languages`: plain JSON replaces each
  value object `{"@value", "@language"}` by its text. This is the documented behaviour since
  manual-revision-notes (TC-24b); JSON-LD keeps the tag. The issue's "lost in documents" holds for
  plain JSON only.
- `rdf_persistence/persistence/services/mapper.py:261` `_value`: a literal is read with
  `term.toPython()`; for a slot ranged `string`, a tagged literal reaches the model as text, and
  `_term` writes it back through `rdf_term` with no tag. A read-modify-write through the Python
  path therefore probably drops the tag (not probed; a planning probe would confirm it).
- `rdf_persistence/persistence/services/jsonld.py:162-176`: `dataset_of` emits `language` and
  `rdf:langString` for a tagged literal.
- `rdf_persistence/core/domain/sparql.py:59-62`: SPARQL terms already validate and render tags.
- `rdf_persistence_generation/uml/slots.py:43,298`: `LANG_STRINGS` and the refusal.
