## ADDED Requirements

### Requirement: Modules of one target that import each other generate Python that loads

When modules that one target generates import each other, directly or through others,
`rp-generate` SHALL write Python that imports in any order: every module of the cycle, the root
module and the package import without error, whichever is imported first, and their classes
validate nested data typed by a class of another module of the cycle. A class of another module of
the same cycle that a module names only in annotations SHALL be imported for the type checker
only, and the package's `__init__.py` SHALL complete those classes once every module of the cycle
is loaded. A module in no cycle, and the `__init__.py` of a target with no cycle, SHALL be written
exactly as they were before this requirement. When the modules of a cycle need each other's
classes while they load (as an `is_a` parent or mixin, a `default_instance` default or a member of
a `union_of`), `rp-generate` SHALL fail at its `python` step, naming the modules and the classes,
and SHALL leave the target's generated files as they were.

#### Scenario: two domain modules that refer to each other
- **GIVEN** a target whose root imports `app_books` and `app_shelves`, each importing the other,
  `Book` referring to a `Shelf` and `Shelf` owning a part declared in `app_books`
- **WHEN** `rp-generate` runs, then `rp-generate --check`
- **THEN** both exit 0, and importing `app_shelves` first, or `app_books` first, gives classes that
  build a `Shelf` with its part from nested data

#### Scenario: a target with no cycle is written as before
- **GIVEN** the toolkit's own targets and the test library, none of whose modules import each other
- **WHEN** they are generated
- **THEN** every generated file, `__init__.py` included, is byte-identical to the one written
  before this requirement

#### Scenario: a cycle that Python cannot load
- **GIVEN** `app_a` and `app_b` importing each other, a class of `app_a` with its `is_a` parent in
  `app_b` and a class of `app_b` with its `is_a` parent in `app_a`
- **WHEN** `rp-generate` runs
- **THEN** it exits 1 with a `python` problem naming `app_a`, `app_b` and the two parents, and
  the target's generated files are left as they were
