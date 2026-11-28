"""TC-11: the goldens of ``rp-uml2linkml`` (PD-22, I-2).

Two generic library models are converted through the command into a folder: the stage-1 model of
``tests/generator/uml_library.py`` and the stage-2 model of ``tests/generator/uml_library_stage2.py``
(the design's worked example with an activity root, a tenant root, an abstract root and a slot shared
across packages). The files, the report included, equal the golden under ``fixtures/uml/golden/<stage>/``
as exact text and exact file set, and a second run writes the same bytes. A golden is rewritten only when
``RP_REFRESH_GOLDEN`` is set (``make refresh-golden``); a plain run never writes it.
"""

import os
from pathlib import Path
from types import ModuleType

import pytest
import yaml

from rdf_persistence_generation.uml.cli import main
from tests.generator import uml_library, uml_library_stage2
from tests.generator.uml_qea import QeaBuilder

GOLDENS = Path(__file__).parents[1] / "fixtures" / "uml" / "golden"
REFRESH_VARIABLE = "RP_REFRESH_GOLDEN"
MODELS: dict[str, ModuleType] = {"stage1": uml_library, "stage2": uml_library_stage2}


def convert_library(stage: str, folder: Path, out: Path) -> None:
    """Run the command over the library model of ``stage`` in ``folder`` (built once), into ``out``; exit 0."""
    model = MODELS[stage]
    qea = folder / "library.qea"
    code = main(
        [
            str(qea if qea.exists() else model.build_library(folder)),
            "--package",
            model.PACKAGE,
            "--prefixes",
            str(model.write_prefixes(folder)),
            "--out",
            str(out),
            "--root-name",
            model.ROOT_NAME,
        ]
    )
    assert code == 0, f"the {stage} library must convert without a problem"


def files_of(folder: Path) -> dict[str, str]:
    return {file.name: file.read_text(encoding="utf-8") for file in sorted(folder.iterdir())}


def _refresh(golden: Path, produced: dict[str, str]) -> None:
    golden.mkdir(parents=True, exist_ok=True)
    for old in golden.iterdir():
        old.unlink()
    for name, text in produced.items():
        (golden / name).write_text(text, encoding="utf-8")


@pytest.mark.parametrize("stage", sorted(MODELS))
def test_the_output_equals_the_golden(stage: str, tmp_path: Path) -> None:
    out = tmp_path / "out"
    convert_library(stage, tmp_path, out)
    produced = files_of(out)
    golden_folder = GOLDENS / stage
    if os.environ.get(REFRESH_VARIABLE):
        _refresh(golden_folder, produced)

    golden = files_of(golden_folder)

    assert sorted(produced) == sorted(golden), f"the {stage} file set differs from the golden one"
    for name, text in produced.items():
        assert text == golden[name], f"{stage}/{name} differs from the golden text"


@pytest.mark.parametrize("stage", sorted(MODELS))
def test_a_second_run_writes_the_same_bytes(stage: str, tmp_path: Path) -> None:
    out = tmp_path / "out"
    convert_library(stage, tmp_path, out)
    first = {file.name: file.read_bytes() for file in sorted(out.iterdir())}

    convert_library(stage, tmp_path, out)

    assert {file.name: file.read_bytes() for file in sorted(out.iterdir())} == first, (
        f"a second {stage} run must write the same bytes"
    )


def read_schemas(folder: Path) -> dict[str, bytes]:
    return {
        file.name: file.read_bytes() for file in sorted(folder.iterdir()) if file.suffix == ".yaml"
    }


def convert_model(qea: Path, out: Path, package: str, prefixes: Path) -> int:
    return main([str(qea), "--package", package, "--prefixes", str(prefixes), "--out", str(out)])


def test_a_model_drawn_both_ways_converts_the_same(tmp_path: Path) -> None:
    """PD-6a: «root» and a boundary restate what the compositions say, so the schema files are the same bytes.

    Fails if the reader lets «root» or the boundary change a slot, a class or a file (the written
    schema files are compared, not the report, which does gain lines).
    """
    outs: dict[str, dict[str, bytes]] = {}
    for drawing, annotated in (("annotated", True), ("plain", False)):
        folder = tmp_path / drawing
        folder.mkdir()
        qea = uml_library.build_library(folder, annotated=annotated)
        out = folder / "out"
        code = convert_model(qea, out, uml_library.PACKAGE, uml_library.write_prefixes(folder))
        assert code == 0, f"the {drawing} library must convert without a problem"
        outs[drawing] = read_schemas(out)

    assert outs["annotated"], "the conversion must write schema files"
    assert sorted(outs["annotated"]) == sorted(outs["plain"]), "both drawings write the same files"
    for name, data in outs["annotated"].items():
        assert data == outs["plain"][name], f"{name} differs between the two drawings"


def _internal_reference_model(folder: Path, boundary: bool) -> Path:
    """An order composing a line and a remark, with a line to remark reference a boundary once owned."""
    builder = QeaBuilder(folder / "orders.qea")
    model = builder.package("MODEL")
    orders = builder.package("orders", parent=model)
    order = builder.cls(orders, "lib:Order")
    line = builder.cls(orders, "lib:Line")
    remark = builder.cls(orders, "lib:Remark")
    builder.attribute(order, "lib:reference", "xsd:string", "1", "1")
    builder.attribute(line, "lib:quantity", "xsd:integer", "1", "1")
    builder.attribute(remark, "lib:text", "xsd:string", "1", "1")
    builder.association(order, line, "lib:hasLine", "0..*")
    builder.aggregation(order, line)
    builder.association(order, remark, "lib:hasRemark", "0..*")
    builder.aggregation(order, remark)
    builder.association(line, remark, "lib:remarkedBy", "0..1")  # a part to part reference
    if boundary:
        builder.boundary(diagram=1, package=orders, name="Order")
    return builder.finish()


def test_a_boundary_model_outside_the_precondition_changes_output(tmp_path: Path) -> None:
    """PD-6a, RISK-10: a boundary that owned a part to part reference no longer owns it once redrawn.

    The slot ``remarked_by`` is a plain reference (no ``owned`` annotation, not inlined) with the
    boundary drawn or not, while the composition's slot is owned. Fails if a boundary owns again.
    """
    outs: dict[str, str] = {}
    for drawing, boundary in (("boundary", True), ("bare", False)):
        folder = tmp_path / drawing
        folder.mkdir()
        qea = _internal_reference_model(folder, boundary)
        out = folder / "out"
        code = convert_model(qea, out, "MODEL/orders", uml_library.write_prefixes(folder))
        assert code == 0, f"the {drawing} model must convert without a problem"
        outs[drawing] = (out / "app_main.yaml").read_text(encoding="utf-8")

    slots = yaml.safe_load(outs["boundary"])["slots"]
    assert "owned" in slots["has_line"].get("annotations", {}), "a composition owns its part's slot"
    assert "owned" not in slots["remarked_by"].get("annotations", {}), (
        "the part to part reference is not owned after the redraw"
    )
    inlined = [key for key in ("inlined", "inlined_as_list") if slots["remarked_by"].get(key)]
    assert not inlined, "the part to part reference is a plain reference, not an inlined slot"
    assert outs["boundary"] == outs["bare"], (
        "the boundary owns nothing: the schema is the same without it"
    )
