"""Attacks on the claim "generating twice gives the same files" (TC-42, adversarial).

The feature scenario generates twice inside one process, where a set of strings iterates in the same
order both times. Python randomises string hashes per process, so an order that leaks from a set into
a generated file shows only across processes. Each generation here runs in a process of its own with
its own hash seed.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from rdf_persistence.services.schema_structure import generation_view
from rdf_persistence_generation.cli import main
from rdf_persistence_generation.config import TOOLKIT_ROOTS

TOY = Path(__file__).parents[2] / "fixtures" / "library"
IGNORED = shutil.ignore_patterns("__pycache__", "generated", "web")
RUN = "import sys; from rdf_persistence_generation.cli import main; sys.exit(main(sys.argv[1:]))"
SEEDS = ("1", "2", "3")


def generate_in_a_process(folder: Path, seed: str) -> dict[str, bytes]:
    shutil.copytree(TOY, folder, ignore=IGNORED)
    done = subprocess.run(
        [sys.executable, "-c", RUN, "--project", str(folder / "pyproject.toml")],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONHASHSEED": seed},
    )
    assert done.returncode == 0, f"generation under hash seed {seed} failed: {done.stderr}"
    return {
        str(p.relative_to(folder)): p.read_bytes()
        for p in sorted(folder.rglob("*"))
        if p.is_file() and ("generated" in p.parts or "web" in p.parts)
    }


@pytest.mark.slow
def test_every_activity_class_of_the_toy_gets_a_frame(tmp_path: Path) -> None:
    """An activity is read from the store and sent as a message: its frame is as needed as a root's."""
    folder = tmp_path / "library"
    shutil.copytree(TOY, folder, ignore=IGNORED)
    assert main(["--project", str(folder / "pyproject.toml")]) == 0, "the toy must generate"
    view = generation_view(folder / "library.yaml", roots=TOOLKIT_ROOTS)
    expected = {"Activity", *view.class_descendants("Activity")}
    assert len(expected) > 1, "the toy has no activity class: the test attacks nothing"
    frames = folder / "generated"
    missing = sorted(n for n in expected if not (frames / f"{n}.frame.jsonld").is_file())
    assert not missing, f"no frame for the activity classes {missing}"


@pytest.mark.slow
def test_generation_does_not_depend_on_the_hash_seed_of_the_process(tmp_path: Path) -> None:
    trees = {seed: generate_in_a_process(tmp_path / seed, seed) for seed in SEEDS}
    first = trees[SEEDS[0]]
    assert first, "nothing was generated: the test compares nothing"
    for seed, tree in trees.items():
        assert tree.keys() == first.keys(), f"seed {seed}: different files"
        different = sorted(name for name in first if first[name] != tree[name])
        assert not different, f"seed {seed} differs from seed {SEEDS[0]} in {different}"
