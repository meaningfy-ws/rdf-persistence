"""Steps of ``generation.feature``: ``rp-generate`` run on a copy of the toy library (PD-11).

Each scenario copies the toy library's schemas, migrations and ``pyproject.toml`` to ``tmp_path`` and
calls ``cli.main`` there, as the command line does. TC-41 to TC-45 of ``generator-package``.
"""

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .toy_run import copy_toy, edit, generate, tree

scenarios("generation.feature")

OUTPUT = "domain/generated"
TYPESCRIPT = "web/src/domain/generated"
MANIFEST = "rp-manifest.json"
BOOKS = "books.yaml"
ACTIVITIES = "books_activities.yaml"
NOTE_DESCRIPTION = "    description: A short note on a chapter, with a label of its own.\n"
NOTE_SLOTS = "    slots: [text, about]\n"
SHELVE_SLOTS = "    slots: [used_resource, shelf_note]\n"
TOOLKIT_FILLED_USAGE = "    slot_usage:\n      started_at_time:\n        required: true\n"
REGENERATE_COMMAND = "run `rp-generate` to regenerate, then commit the result"
SCHEMA_MODULES = (
    "books",
    "books_activities",
    "library",
    "library_access",
    "library_tenant",
    "scans",
    "templates",
)


class Run:
    """What one scenario has built and seen so far."""

    def __init__(self, tmp_path: Path) -> None:
        self.folder = tmp_path / "library"
        self.second = tmp_path / "second"
        self.code: int | None = None
        self.error = ""

    @property
    def project(self) -> Path:
        return self.folder / "pyproject.toml"


@pytest.fixture
def run(tmp_path: Path) -> Run:
    return Run(tmp_path)


def output(run: Run) -> Path:
    return run.folder / OUTPUT


@given("a copy of the toy library")
def a_copy(run: Run) -> None:
    copy_toy(run.folder)


@given("a copy of the toy library that has been generated")
def a_generated_copy(run: Run, capsys: pytest.CaptureFixture[str]) -> None:
    copy_toy(run.folder)
    code, error = generate(run.project, capsys)
    assert code == 0, f"the toy must generate: {error}"


@when("the library is generated")
def generated(run: Run, capsys: pytest.CaptureFixture[str]) -> None:
    run.code, run.error = generate(run.project, capsys)


@when("the library is generated again into a second copy")
def generated_again(run: Run, capsys: pytest.CaptureFixture[str]) -> None:
    copy_toy(run.second)
    code, error = generate(run.second / "pyproject.toml", capsys)
    assert code == 0, f"the second generation failed: {error}"


@when("a slot is added to the books schema")
def slot_added(run: Run) -> None:
    edit(run.folder / BOOKS, NOTE_SLOTS, "    slots: [text, about, number]\n")


@when("the freshness of the generated files is checked")
def checked(run: Run, capsys: pytest.CaptureFixture[str]) -> None:
    run.code, run.error = generate(run.project, capsys, "--check")


@when(parsers.parse("the description of the {name} class is removed from the books schema"))
def description_removed(run: Run, name: str) -> None:
    assert name == "Note", "the step knows the Note class only"
    edit(run.folder / BOOKS, NOTE_DESCRIPTION, "")


@when("the ShelveBooks class gives a usage to the slot the toolkit fills")
def usage_given(run: Run) -> None:
    edit(run.folder / ACTIVITIES, SHELVE_SLOTS, SHELVE_SLOTS + TOOLKIT_FILLED_USAGE)


@then("generation succeeds")
def succeeds(run: Run) -> None:
    assert run.code == 0, f"generation failed with {run.code}: {run.error}"


@then("generation fails")
def fails(run: Run) -> None:
    assert run.code == 1, f"expected exit 1, got {run.code}: {run.error}"


@then("the check fails")
def check_fails(run: Run) -> None:
    fails(run)


@then("there is a Python module for each schema module")
def python_modules(run: Run) -> None:
    missing = [m for m in SCHEMA_MODULES if not (output(run) / f"{m}.py").is_file()]
    assert not missing, f"no Python module for {missing}"


@then("there are the shapes, the context and the frames")
def shapes_context_frames(run: Run) -> None:
    for name in ("shapes.ttl", "context.jsonld", "Book.frame.jsonld", "Shelf.frame.jsonld"):
        assert (output(run) / name).is_file(), f"{name} was not generated"


@then("there are the TypeScript types and the diagrams")
def typescript_and_diagrams(run: Run) -> None:
    assert (run.folder / TYPESCRIPT / "books.ts").is_file(), "no TypeScript for the books module"
    assert (output(run) / "diagrams" / "books.mmd").is_file(), "no diagram for the books module"


@then("there is a manifest that lists the generated files")
def manifest(run: Run) -> None:
    path = output(run) / MANIFEST
    assert path.is_file(), "no manifest"
    assert "books.py" in path.read_text(encoding="utf-8"), "the manifest does not list books.py"


@then("both copies hold byte-identical files")
def identical(run: Run) -> None:
    first, second = tree(run.folder), tree(run.second)
    assert first.keys() == second.keys(), f"different files: {sorted(first.keys() ^ second.keys())}"
    different = [name for name in first if first[name] != second[name]]
    assert not different, f"different content in {different}"


@then("it names the books schema")
def names_books(run: Run) -> None:
    assert BOOKS in run.error, f"{BOOKS} is not named in {run.error!r}"


@then("it names the command that regenerates")
def names_command(run: Run) -> None:
    assert REGENERATE_COMMAND in run.error, f"the regenerate command is not named in {run.error!r}"


@then(parsers.parse('the problem names the class "{name}" and the missing "{metaslot}"'))
def names_class_and_metaslot(run: Run, name: str, metaslot: str) -> None:
    # The lint step runs before the hard check and refuses a class without a description first,
    # tagged [recommended]; the hard check's [description] tag is pinned by the unit tests.
    lines = [line for line in run.error.splitlines() if f"'{name}'" in line and metaslot in line]
    assert lines, f"no problem names {name} and {metaslot} in {run.error!r}"


@then(
    parsers.parse(
        'the problem is tagged "{rule}" and names the class "{name}" and the slot "{slot}"'
    )
)
def tagged_class_and_slot(run: Run, rule: str, name: str, slot: str) -> None:
    lines = [line for line in run.error.splitlines() if f"[{rule}]" in line]
    assert lines, f"no [{rule}] problem in {run.error!r}"
    assert any(name in line and slot in line for line in lines), f"{name} and {slot} not in {lines}"


@then("no file has been written")
def nothing_written(run: Run) -> None:
    assert not output(run).exists(), f"{OUTPUT}/ was written: {sorted(tree(output(run)))[:5]}"
    assert not (run.folder / "web").exists(), "TypeScript was written"
