"""IT-1 of uml-to-linkml: the goldens pass the checks of ``rp-generate``.

The converter's output is the input of the generator, so a golden (the converted generic library model)
is copied into a project with a ``[tool.rp-generate]`` target and checked with the steps that read
schemas only: lint and boundary for the basic model, lint, boundary, hard and rules for the extended one. A refusal here
is the converter's fault, not the golden's and not the checks'.
"""

import importlib
import shutil
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml
from linkml_runtime.dumpers import yaml_dumper
from pydantic import ValidationError
from rdflib import RDF, SH, Graph, Literal, Namespace, URIRef

from rdf_persistence.api.services.shacl import validate_locked
from rdf_persistence_generation.checks.importable import type_problems
from rdf_persistence_generation.config import read_targets
from rdf_persistence_generation.generated.rp_generation import UmlModel, UmlPackage
from rdf_persistence_generation.pipeline import generate
from rdf_persistence_generation.steps import (
    BOUNDARY_STEP,
    HARD_STEP,
    LINT_STEP,
    RULES_STEP,
    STEPS,
)
from rdf_persistence_generation.uml.cli import main as uml2linkml
from tests.generator import uml_library
from tests.generator.uml_model import (
    BOOK,
    CHAPTER,
    EXTERNAL_PKG,
    MODEL_PKG,
    PACKAGES,
    SERIES,
    SHELF,
    attribute,
    composition,
    generalisation,
    klass,
    link,
    model,
    run,
    tag,
)

RP = Namespace("https://meaningfy.ws/ns/rdf-persistence#")
GOLDEN = Path(__file__).parents[1] / "fixtures" / "uml" / "golden" / "stage1"
GOLDEN_STAGE_2 = Path(__file__).parents[1] / "fixtures" / "uml" / "golden" / "stage2"
PACKAGE = "uml_app"
PYPROJECT = f"""\
[tool.rp-generate]
schema = "library.yaml"
package = "{PACKAGE}.domain.generated"
python = "{PACKAGE}/domain/generated"
migrations = "migrations"
"""


def _project_of(golden: Path, tmp_path: Path) -> Path:
    """A project folder holding a golden's files and a ``[tool.rp-generate]`` target."""
    project = tmp_path / "project"
    shutil.copytree(golden, project)
    (project / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    (project / PACKAGE / "domain").mkdir(parents=True)
    (project / PACKAGE / "__init__.py").write_text("", encoding="utf-8")
    (project / PACKAGE / "domain" / "__init__.py").write_text("", encoding="utf-8")
    return project


def test_the_golden_passes_the_lint_and_boundary_steps(tmp_path: Path) -> None:
    project = _project_of(GOLDEN, tmp_path)

    problems = generate(
        read_targets(project / "pyproject.toml"), project, (LINT_STEP, BOUNDARY_STEP), check=True
    )

    assert problems == [], "the stage-1 golden must pass the lint and the boundary check"


def test_the_stage_two_golden_passes_lint_boundary_hard_and_rules(tmp_path: Path) -> None:
    project = _project_of(GOLDEN_STAGE_2, tmp_path)

    problems = generate(
        read_targets(project / "pyproject.toml"),
        project,
        (LINT_STEP, BOUNDARY_STEP, HARD_STEP, RULES_STEP),
        check=True,
    )

    assert problems == [], "the stage-2 golden must pass all four checks of rp-generate"


@pytest.fixture
def importable_project(tmp_path: Path) -> Iterator[Path]:
    """The project folder on ``sys.path``; the generated package is forgotten afterwards."""
    sys.path.insert(0, str(tmp_path / "project"))
    yield tmp_path / "project"
    sys.path.remove(str(tmp_path / "project"))
    for name in [n for n in sys.modules if n.split(".")[0] == PACKAGE]:
        del sys.modules[name]
    importlib.invalidate_caches()


def test_the_stage_two_golden_is_generated_like_a_hand_written_schema(
    tmp_path: Path, importable_project: Path
) -> None:
    project = _project_of(GOLDEN_STAGE_2, tmp_path)

    problems = generate(read_targets(project / "pyproject.toml"), project, STEPS, check=False)

    assert problems == [], "rp-generate must accept the converted schema with every step"
    generated = importlib.import_module(f"{PACKAGE}.domain.generated.library_catalogue")
    chapter = generated.Chapter(id="https://example.org/ns/library#chapter-1", heading="One")
    book = generated.Book(
        id="https://example.org/ns/library#book-1",
        label="A book",
        title="A title",
        identifier="B-1",
        has_chapter=[chapter],
    )
    assert book.title == "A title", "the generated package builds a Book from the converted schema"


def test_a_shared_slot_whose_usages_disagree_on_description_passes_the_lint(
    tmp_path: Path,
) -> None:
    uml = model(
        klass(BOOK, "lib:Book", attributes=(attribute(1, BOOK, "lib:isbn", note="The isbn."),)),
        klass(
            SERIES, "lib:Series", attributes=(attribute(2, SERIES, "lib:isbn", note="The code."),)
        ),
        klass(CHAPTER, "lib:Chapter", attributes=(attribute(3, CHAPTER, "lib:isbn", note=None),)),
    )
    project = _converted_project(uml, tmp_path)

    problems = generate(read_targets(project / "pyproject.toml"), project, (LINT_STEP,), check=True)

    assert problems == [], "the shared slot must keep a description for the lint"


def _converted_project(uml: UmlModel, tmp_path: Path, **overrides: object) -> Path:
    """A project folder holding the schemas ``uml`` converts to, as ``library``, and a target."""
    converted = run(uml, root_name="library", **overrides)
    assert converted.problems == [], converted.problem_texts()
    project = tmp_path / "project"
    project.mkdir()
    for schema in converted.schemas.values():
        yaml_dumper.dump(schema, str(project / f"{schema.name}.yaml"))
    (project / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    (project / PACKAGE / "domain").mkdir(parents=True)
    (project / PACKAGE / "__init__.py").write_text("", encoding="utf-8")
    (project / PACKAGE / "domain" / "__init__.py").write_text("", encoding="utf-8")
    return project


_SHELF_IRI = URIRef("https://example.org/ns/library#shelf-1")


def _member_class_refused(shapes: Graph, member: str) -> bool:
    """Whether the shapes report a result on ``rp:memberClass`` for a Shelf whose member class is ``member``."""
    data = Graph()
    data.add((_SHELF_IRI, RDF.type, URIRef("https://example.org/ns/library#Shelf")))
    data.add((_SHELF_IRI, RP.memberClass, Literal(member)))
    _, report, _ = validate_locked(data, Graph() + shapes)
    return RP.memberClass in set(report.objects(None, SH.resultPath))


def test_a_collection_s_drawn_member_class_refuses_another_class(
    tmp_path: Path, importable_project: Path
) -> None:
    """#241: the converted Shelf takes Book as its member class, in its model and in its shape."""
    uml = model(
        klass(SHELF, "lib:Shelf", stereotype="root"),
        klass(BOOK, "lib:Book", stereotype="root"),
        links=(link(1, SHELF, BOOK, target_role="dct:hasPart", target_card="0..*"),),
        tags=(tag(SHELF, "rp_mixins", "ReferenceCollection"),),
    )
    project = _converted_project(uml, tmp_path, default_mixins=["Described"])

    problems = generate(read_targets(project / "pyproject.toml"), project, STEPS, check=False)

    assert problems == [], "rp-generate must accept the converted collection"
    generated = importlib.import_module(f"{PACKAGE}.domain.generated.library_library")
    with pytest.raises(ValidationError):
        generated.Shelf(id=str(_SHELF_IRI), label="A shelf", member_class="Map")
    shelf = generated.Shelf(id=str(_SHELF_IRI), label="A shelf", member_class="Book")
    assert shelf.member_class == "Book", "the drawn member class is accepted"
    shapes = Graph().parse(project / PACKAGE / "domain" / "generated" / "shapes.ttl")
    assert _member_class_refused(shapes, "Map"), "the shape refuses another member class"
    assert not _member_class_refused(shapes, "Book"), "the shape accepts the drawn member class"


_COLLECTION, _RESOURCE = 17, 18  # lib:Collection and lib:Resource, both abstract (#274)


def test_an_abstract_collection_narrowed_by_its_subclass_type_checks(tmp_path: Path) -> None:
    """#274: an abstract Collection's role to an abstract Resource and Shelf's own role to Book."""
    has_part = {"target_role": "dct:hasPart", "target_card": "0..*"}
    uml = model(
        klass(_COLLECTION, "lib:Collection", abstract=True),
        klass(_RESOURCE, "lib:Resource", abstract=True),
        klass(SHELF, "lib:Shelf", stereotype="root"),
        klass(BOOK, "lib:Book", stereotype="root"),
        links=(
            link(1, _COLLECTION, _RESOURCE, **has_part),
            link(2, SHELF, BOOK, **has_part),
            generalisation(3, SHELF, _COLLECTION),
            generalisation(4, BOOK, _RESOURCE),
        ),
        tags=(tag(_COLLECTION, "rp_mixins", "ReferenceCollection"),),
    )
    project = _converted_project(uml, tmp_path, default_mixins=["Described"])
    targets = read_targets(project / "pyproject.toml")

    assert generate(targets, project, STEPS, check=False) == [], "rp-generate accepts the schema"
    assert type_problems(targets, project) == [], "the generated subclass narrows nothing typed"


_ACCESS_PKG, _ACCESS_ELEMENT, _LIBRARY_ACCESS, _TENANT_ACCESS = 9, 40, 41, 42


def test_an_access_package_passes_the_boundary_rule_for_the_root_that_imports_it(
    tmp_path: Path,
) -> None:
    """#245 part 1: a package tagged module_kind=access, its class an rp:TenantAccess, beside a domain one."""
    uml = model(
        klass(BOOK, "lib:Book", stereotype="root"),
        klass(_LIBRARY_ACCESS, "lib:LibraryAccess", _ACCESS_PKG),
        links=(generalisation(1, _LIBRARY_ACCESS, _TENANT_ACCESS),),
        tags=(tag(_ACCESS_ELEMENT, "module_kind", "access"),),
        packages=(
            *PACKAGES,
            UmlPackage(
                package_id=_ACCESS_PKG,
                name="access",
                parent_id=MODEL_PKG,
                object_id=_ACCESS_ELEMENT,
            ),
        ),
        outside=(klass(_TENANT_ACCESS, "rp:TenantAccess", EXTERNAL_PKG),),
        outside_packages=(UmlPackage(package_id=EXTERNAL_PKG, name="toolkit"),),
    )
    project = _converted_project(uml, tmp_path)
    access = yaml.safe_load((project / "library_access.yaml").read_text(encoding="utf-8"))
    assert access["annotations"]["module_kind"]["value"] == "access", "the access module's kind"
    assert access["classes"]["LibraryAccess"]["is_a"] == "TenantAccess", "it is a TenantAccess"
    root = yaml.safe_load((project / "library.yaml").read_text(encoding="utf-8"))
    assert "library_access" in root["imports"], "the root imports the access module"

    problems = generate(
        read_targets(project / "pyproject.toml"), project, (LINT_STEP, BOUNDARY_STEP), check=True
    )

    assert problems == [], "the boundary rule passes for a root that imports an access module"


def test_the_redrawn_library_converts_and_passes_the_generator_checks(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """D-9: the library drawn with compositions and a boundary goes through ``rp-uml2linkml``, then the checks."""
    project = tmp_path / "project"
    project.mkdir()
    converted = uml2linkml(
        [
            str(uml_library.build_library(tmp_path)),
            "--package",
            uml_library.PACKAGE,
            "--prefixes",
            str(uml_library.write_prefixes(tmp_path)),
            "--out",
            str(project),
            "--root-name",
            uml_library.ROOT_NAME,
        ]
    )
    assert converted == 0, capsys.readouterr().err
    (project / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    (project / PACKAGE / "domain").mkdir(parents=True)
    (project / PACKAGE / "__init__.py").write_text("", encoding="utf-8")
    (project / PACKAGE / "domain" / "__init__.py").write_text("", encoding="utf-8")

    # the hard check is left out: the library leaves one enumeration literal without a note on purpose
    problems = generate(
        read_targets(project / "pyproject.toml"), project, (LINT_STEP, BOUNDARY_STEP), check=True
    )

    assert problems == [], "the redrawn library must pass the lint and the boundary check"
    root = yaml.safe_load((project / "library.yaml").read_text(encoding="utf-8"))
    assert "library_catalogue" in root["imports"], "the root imports the catalogue module"


_SHELF_COUNT, _COUNT_REPORT, _SHAPE_REPORT, _SHAPE_RESULT = 30, 31, 32, 33
_OWN_GRAPH = "own graph"


def _shelf_count_model() -> UmlModel:
    """Design example 2: a shelf count with two «own graph» reports that are not generated."""
    return model(
        klass(_SHELF_COUNT, "lib:ShelfCount"),
        klass(_COUNT_REPORT, "lib:CountReport", stereotype="loaded graph"),
        klass(_SHAPE_REPORT, "lib:ShapeReport", stereotype="loaded graph"),
        klass(_SHAPE_RESULT, "lib:ShapeResult"),
        links=(
            link(1, _SHELF_COUNT, _COUNT_REPORT, target_role="lib:countReport", target_card="0..1"),
            link(2, _SHELF_COUNT, _SHAPE_REPORT, target_role="lib:shapeReport", target_card="0..1"),
            link(3, _SHAPE_REPORT, _SHAPE_RESULT, target_role="lib:result", target_card="0..*"),
        ),
        compositions=(
            composition(4, _SHELF_COUNT, _COUNT_REPORT, own_graph=True, stereotype=_OWN_GRAPH),
            composition(5, _SHELF_COUNT, _SHAPE_REPORT, own_graph=True, stereotype=_OWN_GRAPH),
            composition(6, _SHAPE_REPORT, _SHAPE_RESULT),
        ),
    )


def _loaded_graph_problems(project: Path) -> list[str]:
    """What is wrong with the shelf count's report slots in the converted schema."""
    problems: list[str] = []
    schema = yaml.safe_load((project / "library_library.yaml").read_text(encoding="utf-8"))
    for slot in ("count_report", "shape_report"):
        found = schema["slots"][slot]
        annotations = found.get("annotations", {})
        if found.get("range") != "uri":
            problems.append(f"{slot} ranges over {found.get('range')}, not uri")
        if "owned" in annotations:
            problems.append(f"{slot} is owned")
        if annotations.get("rp_loaded_graph", {}).get("value") != "true":
            problems.append(f"{slot} does not carry rp_loaded_graph")
    for part in ("CountReport", "ShapeReport", "ShapeResult"):
        if part in schema["classes"]:
            problems.append(f"{part} is generated")
    return problems


@pytest.mark.slow
def test_the_shelf_count_generates_with_its_loaded_graph_slots_as_uri(
    tmp_path: Path, importable_project: Path
) -> None:
    """D-9, PD-9: an «own graph» composition to a not-generated part is a ``uri`` slot, not an owned part."""
    project = _converted_project(_shelf_count_model(), tmp_path, default_mixins=["Described"])
    assert _loaded_graph_problems(project) == [], "the converted report slots hold graph IRIs"

    problems = generate(read_targets(project / "pyproject.toml"), project, STEPS, check=False)

    assert problems == [], "rp-generate must accept the shelf count with every step"
    generated = importlib.import_module(f"{PACKAGE}.domain.generated.library_library")
    for part in ("CountReport", "ShapeReport", "ShapeResult"):
        assert not hasattr(generated, part), f"{part} is inside an own graph: no class is generated"
    fields = generated.ShelfCount.model_fields
    for slot in ("count_report", "shape_report"):
        assert fields[slot].annotation == str | None, f"{slot} is a plain IRI string in Python"
    iri = "https://example.org/ns/library#graph-1"
    count = generated.ShelfCount(
        id="https://example.org/ns/library#count-1", label="A count", count_report=iri
    )
    assert count.count_report == iri, "the slot holds an IRI"
