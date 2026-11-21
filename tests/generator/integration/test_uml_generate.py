"""IT-1 of uml-to-linkml: the goldens pass the checks of ``rp-generate``.

The converter's output is the input of the generator, so a golden (the converted generic library model)
is copied into a project with a ``[tool.rp-generate]`` target and checked with the steps that read
schemas only: lint and boundary for stage 1, lint, boundary, hard and rules for stage 2. A refusal here
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
from tests.generator.uml_model import (
    BOOK,
    CHAPTER,
    EXTERNAL_PKG,
    MODEL_PKG,
    PACKAGES,
    SERIES,
    SHELF,
    attribute,
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
