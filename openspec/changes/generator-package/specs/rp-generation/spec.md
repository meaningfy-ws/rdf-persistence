## ADDED Requirements

### Requirement: The generator is a sibling package installed with the library

The generator SHALL be the top-level package `rdf_persistence_generation`, shipped in the
`rdf-persistence` distribution beside `rdf_persistence`. The `rp-generate` command, the
`[tool.rp-generate]` table and its keys SHALL stay as they are. LinkML's generators SHALL be
installed only with the `generate` extra; without it, `rp-generate --check` SHALL still compare the
manifests, and `rp-generate` SHALL exit 2 naming the extra.

#### Scenario: generating with the extra
- **GIVEN** `rdf-persistence[generate]` installed and a `[tool.rp-generate]` entry
- **WHEN** `rp-generate` runs
- **THEN** the artefacts are written as before the move, byte for byte

#### Scenario: checking without the extra
- **GIVEN** `rdf-persistence` installed without the `generate` extra
- **WHEN** `rp-generate --check` runs on a fresh tree
- **THEN** it exits 0 after comparing the manifests

#### Scenario: generating without the extra
- **GIVEN** `rdf-persistence` installed without the `generate` extra
- **WHEN** `rp-generate` runs
- **THEN** it exits 2 and names `rdf-persistence[generate]`

### Requirement: The metamodel declares where its generated classes are imported from

Each metamodel module SHALL carry the annotation `python_package`, the package its classes are
generated into, and the root metamodel schema SHALL carry `public_package`, the package a
consumer's generated code imports metamodel classes from. The generator SHALL read both from the
metamodel. On the toolkit's own run, a module without `python_package`, or whose `python_package`
differs from the `package` of the toolkit entry that generates it, SHALL fail the hard check,
naming the module and the packages.

#### Scenario: a consumer's generated class
- **GIVEN** a consumer schema that imports `rp_core`
- **WHEN** it is generated
- **THEN** its classes import the metamodel classes from the `public_package`

#### Scenario: a module moved to another package
- **GIVEN** `rp_core.yaml` annotated with another `python_package` and the toolkit entry changed to match
- **WHEN** the toolkit's other targets are generated
- **THEN** they import `rp_core`'s classes from that package

#### Scenario: an annotation that disagrees
- **GIVEN** `rp_core.yaml`'s `python_package` differs from the toolkit entry's `package`
- **WHEN** the toolkit's `rp-generate` runs
- **THEN** it fails naming `rp_core` and both packages, and writes nothing

### Requirement: The generator has its own test pyramid

The generator's tests SHALL live in `tests/generator/{unit,feature,integration,e2e}`, apart from
the library's, each tier stamped by its folder. The feature tests SHALL generate the toy library;
the integration tests SHALL check freshly generated shapes with pySHACL, the context and frames
with PyLD, and the TypeScript with `tsc --strict`; the end-to-end test SHALL serve a freshly
generated toy library through the service kit on Fuseki.

#### Scenario: freshly generated code is served
- **GIVEN** the toy library generated into a new package in a temporary folder
- **WHEN** it is served through the service kit on Fuseki
- **THEN** a librarian creates, reads, replaces and deletes a book over the API, a reader is
  refused the write, and an outsider gets 404

#### Scenario: fresh shapes judge the conformance cases
- **GIVEN** the toy library freshly generated
- **WHEN** pySHACL validates each conformance case against the fresh shapes
- **THEN** every valid case conforms and every invalid case does not
