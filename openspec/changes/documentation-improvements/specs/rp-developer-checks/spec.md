## ADDED Requirements

### Requirement: Every docs link resolves to a page and an anchor

`make check-docs` SHALL fail when an `xref:` in a docs page or in the nav names a page that does
not exist in the component (an alias declared with `:page-aliases:` counts as a page) or an anchor
the target page does not define, and when a `<<anchor>>` names an anchor its own page does not
define. An anchor is defined by `[#id]`, `[[id]]`, `anchor:id[]` or by a section title, whose
implicit id SHALL be computed as Asciidoctor computes it with the `idprefix` and `idseparator` the
site playbook sets (today `''` and `-`).

#### Scenario: a link to a moved section
- **GIVEN** a page links to `xref:user-manual/tenants.adoc#tenancy[...]` and no page defines that id there
- **WHEN** `make check-docs` runs
- **THEN** it fails naming the page, the link and the missing anchor

#### Scenario: a link through an alias
- **GIVEN** a page links to `xref:howto/adopt.adoc[...]` and `user-manual/index.adoc` declares `:page-aliases: howto/adopt.adoc`
- **WHEN** `make check-docs` runs
- **THEN** the link passes

### Requirement: The generated reference is fresh

`make check-docs` SHALL fail when the reference partials written by `docs/tools/reference.py`
(the public Python API from `rdf_persistence.__all__` and the `rp-generate` usage) differ from what
the tool would write now.

#### Scenario: a name added to the public API
- **GIVEN** a name is added to `rdf_persistence.__all__` and the partials are not rewritten
- **WHEN** `make check-docs` runs
- **THEN** it fails saying the reference is stale and naming the command that rewrites it
