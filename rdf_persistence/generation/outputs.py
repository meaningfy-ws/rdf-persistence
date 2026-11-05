"""Rendered files, and writing them into a run's staging folder."""

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from rdf_persistence.generation.pipeline import Run


@dataclass(frozen=True)
class GeneratedFile:
    """One file a step renders: its name inside the target folder and its text."""

    name: str
    text: str


def stage(run: Run, folder: Path, files: Iterable[GeneratedFile]) -> None:
    """Write ``files`` into ``folder`` (relative to the run's ``base``) in the staging area."""
    for file in files:
        run.staged(folder / file.name).write_text(file.text, encoding="utf-8")
