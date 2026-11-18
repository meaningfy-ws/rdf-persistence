"""The artefacts a fresh generation writes hold up outside the generator: shapes, context, frames, TypeScript (PD-12).

The toy library is generated once per session (``fresh_toy``); nothing here reads the committed
``generated/`` folder.
"""

import json
import os
import subprocess
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import pytest
import yaml
from linkml_runtime.utils.schemaview import SchemaView
from pyld import jsonld
from rdflib import SH, Graph

from rdf_persistence.core.domain.exceptions import InvalidBody
from rdf_persistence.schema.services.schema_structure import generation_view, json_name
from rdf_persistence.services.documents import Documents
from rdf_persistence.services.shacl import validate_locked
from rdf_persistence_generation.config import TOOLKIT_ROOTS
from rdf_persistence_generation.testkit.conformance import Conformance, load_cases
from rdf_persistence_generation.testkit.roundtrip import without_framing

ROOT = Path(__file__).parents[3]
CASES = ROOT / "tests" / "fixtures" / "conformance" / "cases.yaml"
INTEGRATION = Path(__file__).parent
TSC = ["npx", "-y", "-p", "typescript@5.9.3", "tsc", "--noEmit", "--strict"]  # the Makefile's pin

# The SHACL constraint component that reports each kind of constraint (the case's `kind`).
COMPONENT = {
    "required": "MinCountConstraintComponent",
    "range_type": "DatatypeConstraintComponent",
    "range_enum": "InConstraintComponent",
    "pattern": "PatternConstraintComponent",
    "identifier": "NodeKindConstraintComponent",  # no id: a blank node, which the shape refuses
    "closed": "ClosedConstraintComponent",
    "exactly_one_of": "XoneConstraintComponent",
    "unique_keys": "SPARQLConstraintComponent",
}


@dataclass(frozen=True)
class Fresh:
    """The fresh toy's schema view and the router's reader of its freshly generated documents."""

    conformance: Conformance
    folder: Path

    @property
    def view(self) -> SchemaView:
        return self.conformance.view


@cache
def _opened(schema: Path) -> Fresh:
    view = generation_view(schema, roots=TOOLKIT_ROOTS)
    folder = schema.parent / "generated"
    documents = Documents(view, folder)
    return Fresh(
        Conformance(view=view, models={}, shapes=documents.shapes, documents=documents), folder
    )


@pytest.fixture
def fresh(fresh_toy: Path) -> Fresh:
    return _opened(fresh_toy / "library.yaml")


def _rows(files: str) -> list:
    """One parameter per instance file of the cases of the toy library (rows of other schemas are theirs)."""
    toy = ROOT / "tests" / "fixtures" / "library" / "library.yaml"
    classes = set(generation_view(toy, roots=TOOLKIT_ROOTS).all_classes())
    return [
        pytest.param(case.kind, case.class_name, Path(file), id=f"{case.kind}-{Path(file).stem}")
        for case in load_cases(CASES)
        if case.class_name in classes
        for file in getattr(case, files) or []
    ]


def _verdict(fresh: Fresh, class_name: str, file: Path) -> tuple[bool, set[str]]:
    """Whether the fresh shapes accept the instance, and the components the report names."""
    data = yaml.safe_load(file.read_text(encoding="utf-8"))
    body = fresh.conformance.public(class_name, data)
    graph = fresh.conformance.documents.expand(body, fresh.view.get_class(class_name))
    conforms, report, _ = validate_locked(graph, fresh.conformance.shapes)
    named = {str(c).rpartition("#")[2] for c in report.objects(None, SH.sourceConstraintComponent)}
    return conforms, named


@pytest.mark.parametrize(("kind", "class_name", "file"), _rows("valid"))
def test_a_valid_instance_conforms_to_the_fresh_shapes(
    fresh: Fresh, kind: str, class_name: str, file: Path
) -> None:
    conforms, named = _verdict(fresh, class_name, file)
    assert conforms, f"the fresh shapes refuse a valid {kind} instance of {class_name}: {named}"


@pytest.mark.parametrize(("kind", "class_name", "file"), _rows("invalid"))
def test_an_invalid_instance_does_not_conform_and_the_report_names_the_kind(
    fresh: Fresh, kind: str, class_name: str, file: Path
) -> None:
    try:
        conforms, named = _verdict(fresh, class_name, file)
    except InvalidBody as refused:
        # The router refuses a key the class has no slot for before the shapes see the body.
        assert kind == "closed", f"only a closed case is refused by the reader: {refused}"
        return
    assert not conforms, f"the fresh shapes accept an invalid {kind} instance of {class_name}"
    assert COMPONENT[kind] in named, f"the report names {named}, not the {kind} constraint"


def test_the_toy_cases_cover_every_kind_the_report_is_asserted_on() -> None:
    kinds = {p.values[0] for p in _rows("invalid")}
    assert kinds == set(COMPONENT), (
        "a kind has no invalid toy instance, or COMPONENT has a stale one"
    )


BOOK = {"id": "https://example.org/library/b1", "label": "Dune", "description": "A desert planet."}


def test_a_book_body_expands_to_the_schema_predicates_and_frames_back_to_itself(
    fresh: Fresh,
) -> None:
    context = fresh.conformance.documents.context
    book = fresh.view.get_class("Book")
    document = {"@context": context, "@type": "Book", **BOOK}
    expanded = json.dumps(jsonld.expand(document))  # PyLD with the fresh context
    triples = Graph().parse(data=expanded, format="json-ld")
    predicates = {str(p) for p in triples.predicates()}
    expected = {
        str(fresh.view.get_uri(slot, expand=True))
        for slot in fresh.view.class_induced_slots("Book")
        if json_name(slot) in BOOK and json_name(slot) != "id"
    }
    assert expected, "the body names no slot"
    assert expected <= predicates, f"the expansion lacks {expected - predicates}"
    framed = fresh.conformance.documents.frame(fresh.conformance.documents.expand(BOOK, book), book)
    assert without_framing(framed) == BOOK, "the framed body differs from the body"


def run_tsc(files: list[Path], path: str | None = None) -> None:
    """Run ``tsc`` through ``npx`` on ``files`` (with ``path`` as PATH, if given); fail without Node."""
    env = {**os.environ, **({"PATH": path} if path is not None else {})}
    try:
        done = subprocess.run(
            [*TSC, *map(str, files)], capture_output=True, text=True, check=False, env=env
        )
    except FileNotFoundError:
        pytest.fail("npx is not on PATH: install Node 20 or later to run the TypeScript check")
    assert done.returncode == 0, f"tsc failed:\n{done.stdout}{done.stderr}"


@pytest.mark.slow
def test_the_fresh_typescript_compiles_strictly(fresh_toy: Path) -> None:
    files = sorted((fresh_toy / "web" / "src" / "domain" / "generated").glob("*.ts"))
    assert files, "the generation wrote no TypeScript"
    run_tsc(files)


def test_a_missing_node_is_a_failure_that_says_to_install_it(tmp_path: Path) -> None:
    with pytest.raises(pytest.fail.Exception, match="install Node 20"):
        run_tsc([], path=str(tmp_path))


def _ignores(config: pytest.Config, folder: Path) -> bool:
    """Whether the session's ``--ignore`` or ``--ignore-glob`` options leave out ``folder``."""
    base = Path(config.invocation_params.dir)
    ignored = [(base / path).resolve() for path in config.getoption("ignore") or []]
    globs = config.getoption("ignore_glob") or []
    return folder.resolve() in ignored or any(folder.match(glob) for glob in globs)


def test_the_tier_loads_no_container_plugin(request: pytest.FixtureRequest) -> None:
    """No container starts in this lane, so the session has not registered the fixtures plugin (D-20 S3, D-27, D-29).

    The generator's e2e conftest registers it whenever a session collects ``tests/generator``;
    the lanes that run this tier ignore ``tests/generator/e2e`` so that it never does. The
    session assertion therefore holds only when the session ignores that folder: ``make
    test-containers`` collects it on purpose, loads the plugin and runs this tier too, and
    asserts nothing here. The static scan of the tier's conftests holds in every session.
    """
    e2e = ROOT / "tests" / "generator" / "e2e"
    if _ignores(request.config, e2e):
        registered = request.config.pluginmanager.has_plugin(
            "rdf_persistence.testkit.containers.fixtures"
        )
        assert not registered, (
            "the container fixtures plugin is registered: tests/generator/e2e was collected"
        )
    sources = [*INTEGRATION.rglob("conftest.py"), INTEGRATION.parent / "conftest.py"]
    named = [
        str(path)
        for path in sources
        if path.exists()
        and any(
            word in path.read_text(encoding="utf-8")
            for word in ("testkit.containers", "load_container_plugin", "CONTAINER_PLUGIN")
        )
    ]
    assert named == [], f"these conftests load the container plugin: {named}"
