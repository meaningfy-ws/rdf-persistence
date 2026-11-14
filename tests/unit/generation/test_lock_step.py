"""What ``rp-generate`` does with the schema lock and the migration files (task 1.3b, PD-3, PD-4)."""

from pathlib import Path

import pytest

from rdf_persistence.generation.cli import main
from rdf_persistence.generation.generated.rp_generation import SchemaLock
from rdf_persistence.generation.manifest import MANIFEST_NAME
from rdf_persistence.services.migrations import load_migration

from .conftest import Breaker
from .test_lock import BOOK_SLOTS, DROP_SHELF, ISBN_REQUIRED, NEW_PATH, NEW_TYPE, Edits

LOCK_NAME = "schema.lock.json"
VERSION_2 = (("library.yaml", 'version: "1"', 'version: "2"'),)
FAILED = 1
ADD_SUBTITLE: Edits = (
    ("books.yaml", BOOK_SLOTS, BOOK_SLOTS.replace("sequel_of]", "sequel_of, subtitle]")),
    (
        "books.yaml",
        "slots:\n  isbn:",
        "slots:\n  subtitle:\n    title: Subtitle\n    description: The subtitle of a book.\n"
        "    slot_uri: lib:subtitle\n    range: string\n  isbn:",
    ),
)


class Toy:
    """The toy copy, run through the real command."""

    def __init__(
        self, folder: Path, break_toy: Breaker, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self.folder, self._break, self._capsys = folder, break_toy, capsys

    @property
    def migrations(self) -> Path:
        return self.folder / "migrations"

    @property
    def lock(self) -> Path:
        return self.migrations / LOCK_NAME

    def edit(self, edits: Edits) -> None:
        for edit in edits:
            self._break(*edit)

    def run(self, *flags: str) -> tuple[int, str]:
        """Run ``rp-generate``; return the exit code and everything it printed."""
        self._capsys.readouterr()
        code = main(["--project", str(self.folder / "pyproject.toml"), *flags])
        out = self._capsys.readouterr()
        return code, out.out + out.err

    def locked_version(self) -> str:
        return str(SchemaLock.model_validate_json(self.lock.read_text("utf-8")).schema_version)

    def files(self) -> dict[str, bytes]:
        """Every file of the copy, by path, to compare before and after a run."""
        return {
            str(p.relative_to(self.folder)): p.read_bytes()
            for p in sorted(self.folder.rglob("*"))
            if p.is_file() and ".rp-generate-" not in str(p)
        }


@pytest.fixture
def toy(toy_copy: Path, break_toy: Breaker, capsys: pytest.CaptureFixture[str]) -> Toy:
    """The toy with no lock: the fixture ships one, and a test that bootstraps starts without it."""
    (toy_copy / "migrations" / LOCK_NAME).unlink(missing_ok=True)
    return Toy(toy_copy, break_toy, capsys)


@pytest.fixture
def bootstrapped(toy: Toy) -> Toy:
    """The toy generated once at version 1: its lock is written."""
    assert toy.run()[0] == 0, "the toy must generate"
    return toy


def drafts(toy: Toy) -> list[str]:
    return sorted(p.name for p in toy.migrations.glob("*.yaml"))


# ---- bootstrap, the manifest and the freshness check (TC-12, TC-14) ------------------------------


def test_the_first_run_writes_the_lock_and_no_migration(bootstrapped: Toy) -> None:
    assert bootstrapped.locked_version() == "1", "the lock records the schema's version"
    assert drafts(bootstrapped) == [], "no lock yet is a bootstrap: no migration"


def test_the_lock_is_a_manifest_output_and_a_second_run_changes_nothing(bootstrapped: Toy) -> None:
    manifest = (bootstrapped.folder / "generated" / MANIFEST_NAME).read_text("utf-8")
    assert "migrations/schema.lock.json" in manifest, "the lock is listed like a generated file"
    before = bootstrapped.files()
    assert bootstrapped.run()[0] == 0
    assert bootstrapped.files() == before, "a second run writes the same bytes and removes nothing"


def test_a_hand_edited_lock_is_reported_stale(bootstrapped: Toy) -> None:
    """TC-12"""
    text = bootstrapped.lock.read_text("utf-8")
    bootstrapped.lock.write_text(text.replace('"1"', '"9"', 1), encoding="utf-8")
    code, printed = bootstrapped.run("--check")
    assert code == FAILED, printed
    assert "edited by hand: migrations/schema.lock.json" in printed


# ---- the rules without a new version (TC-06, TC-05a, TC-09) --------------------------------------


def test_a_removed_slot_with_the_version_unchanged_fails_naming_it(bootstrapped: Toy) -> None:
    """TC-06"""
    bootstrapped.edit(DROP_SHELF)
    before = bootstrapped.files()
    for flags in ((), ("--check",)):
        code, printed = bootstrapped.run(*flags)
        assert code == FAILED, f"{flags}: {printed}"
        assert "http://purl.org/ontology/bibo/Book" in printed, "the class is named"
        assert "https://example.org/ns/library#shelf" in printed, "the slot is named"
        assert "set a new `version:`" in printed, "the fix is named"
    assert bootstrapped.files() == before, "a refused run changes nothing"


@pytest.mark.parametrize(
    ("edits", "word"),
    [
        pytest.param(NEW_PATH, "IRI type or path", id="path"),
        pytest.param(NEW_TYPE, "IRI type or path", id="iri-type"),
    ],
)
@pytest.mark.parametrize("version", [(), VERSION_2], ids=["same-version", "new-version"])
def test_a_change_that_cannot_be_migrated_fails_with_any_version(
    bootstrapped: Toy, edits: Edits, word: str, version: Edits
) -> None:
    """TC-05a"""
    bootstrapped.edit((*edits, *version))
    code, printed = bootstrapped.run()
    assert code == FAILED, printed
    assert word in printed, "the change is named"
    assert drafts(bootstrapped) == [], "nothing is drafted for a change no step can do"
    assert bootstrapped.locked_version() == "1", "the lock is untouched"


@pytest.mark.parametrize("version", [(), VERSION_2], ids=["same-version", "new-version"])
def test_a_slot_that_was_inlined_when_the_lock_was_written_is_not_migratable(
    bootstrapped: Toy, version: Edits
) -> None:
    """TC-05a: a schema that passes the boundary check cannot flip `inlined`, so the lock is edited."""
    lock = SchemaLock.model_validate_json(bootstrapped.lock.read_text("utf-8"))
    owned = [s for c in lock.locked_classes or [] for s in c.locked_slots or [] if s.inlined]
    assert owned, "the toy owns parts"
    owned[0].inlined = False
    bootstrapped.lock.write_text(lock.model_dump_json(indent=2) + "\n", encoding="utf-8")
    bootstrapped.edit(version)
    code, printed = bootstrapped.run()
    assert code == FAILED, printed
    assert "inlined changed" in printed, "the change is named"
    assert drafts(bootstrapped) == [], "nothing is drafted for a change no step can do"


def test_safe_changes_with_the_version_unchanged_rewrite_the_lock_only(bootstrapped: Toy) -> None:
    """TC-09"""
    bootstrapped.edit(ADD_SUBTITLE)
    before = bootstrapped.lock.read_bytes()
    code, printed = bootstrapped.run()
    assert code == 0, printed
    assert "subtitle" in bootstrapped.lock.read_text("utf-8"), "the lock follows the schema"
    assert bootstrapped.lock.read_bytes() != before
    assert drafts(bootstrapped) == [], "no new version, no migration"


def test_safe_changes_with_a_new_version_draft_a_migration_with_no_steps(
    bootstrapped: Toy,
) -> None:
    """TC-09"""
    bootstrapped.edit((*ADD_SUBTITLE, *VERSION_2))
    assert bootstrapped.run()[0] == 0
    assert drafts(bootstrapped) == ["1__2.yaml"]
    migration = load_migration(bootstrapped.migrations / "1__2.yaml")
    assert (migration.from_version, migration.to_version) == ("1", "2")
    assert migration.steps == [], "a safe change needs no step"


def test_a_raised_version_with_no_change_drafts_a_migration_with_no_steps(
    bootstrapped: Toy,
) -> None:
    bootstrapped.edit(VERSION_2)
    assert bootstrapped.run()[0] == 0
    assert load_migration(bootstrapped.migrations / "1__2.yaml").steps == []
    assert bootstrapped.locked_version() == "2"


# ---- the draft (TC-07, TC-08, TC-13) -------------------------------------------------------------


def test_a_removed_slot_with_a_new_version_drafts_a_drop_and_prints_where(
    bootstrapped: Toy,
) -> None:
    """TC-07"""
    bootstrapped.edit((*DROP_SHELF, *VERSION_2))
    code, printed = bootstrapped.run()
    assert code == 0, printed
    draft = bootstrapped.migrations / "1__2.yaml"
    assert str(draft) in printed, "the run prints the path of the draft"
    (step,) = load_migration(draft).steps or []
    assert step.title.startswith("DROP "), step.title
    assert bootstrapped.locked_version() == "2"
    manifest = (bootstrapped.folder / "generated" / MANIFEST_NAME).read_text("utf-8")
    assert "1__2.yaml" not in manifest, "a draft is the developer's file, not a manifest output"
    again = bootstrapped.files()
    assert bootstrapped.run()[0] == 0
    assert bootstrapped.files() == again, "a second run changes nothing and removes nothing"
    assert bootstrapped.run("--check")[0] == 0


def test_an_edited_draft_is_kept_byte_for_byte(bootstrapped: Toy) -> None:
    """TC-08"""
    bootstrapped.edit((*DROP_SHELF, *VERSION_2))
    assert bootstrapped.run()[0] == 0
    draft = bootstrapped.migrations / "1__2.yaml"
    draft.write_text(
        draft.read_text("utf-8").replace("Review every step.", "Reviewed."), encoding="utf-8"
    )
    edited = draft.read_bytes()
    assert bootstrapped.run()[0] == 0
    assert draft.read_bytes() == edited, "the run keeps the file"
    assert bootstrapped.run("--check")[0] == 0


def test_a_version_with_a_slash_is_written_with_an_underscore_in_the_file_name(
    toy: Toy,
) -> None:
    """TC-13"""
    toy.edit((("library.yaml", 'version: "1"', 'version: "1.0/beta"'),))
    assert toy.run()[0] == 0
    toy.edit((("library.yaml", 'version: "1.0/beta"', 'version: "2"'),))
    assert toy.run()[0] == 0
    assert drafts(toy) == ["1.0_beta__2.yaml"]
    assert load_migration(toy.migrations / "1.0_beta__2.yaml").from_version == "1.0/beta"


# ---- an unresolved draft (TC-09a) and a file that does not load ----------------------------------


def test_an_unresolved_draft_succeeds_once_then_fails_the_next_run_and_the_check(
    bootstrapped: Toy,
) -> None:
    """TC-09a"""
    bootstrapped.edit((*ISBN_REQUIRED, *VERSION_2))
    code, printed = bootstrapped.run()
    assert code == 0, f"the run that drafts succeeds: {printed}"
    assert bootstrapped.locked_version() == "2"
    for flags in ((), ("--check",)):
        code, printed = bootstrapped.run(*flags)
        assert code == FAILED, f"{flags}: {printed}"
        assert "1__2.yaml" in printed, "the file is named"
        assert "step 1" in printed, "the step is named"


def test_a_migration_file_that_does_not_load_fails_the_run(bootstrapped: Toy) -> None:
    (bootstrapped.migrations / "1__2.yaml").write_text(
        "schema_id: https://example.org/ns/library\nfrom_version: '1'\nto_version: '2'\n"
        "steps:\n  - title: Half done\n    unresolved: still to write\n",
        encoding="utf-8",
    )
    code, printed = bootstrapped.run()
    assert code == FAILED, printed
    assert "1__2.yaml" in printed and "Half done" in printed, printed


def test_a_run_that_fails_earlier_writes_no_draft(bootstrapped: Toy) -> None:
    bootstrapped.edit(
        (
            *DROP_SHELF,
            *VERSION_2,
            (
                "books.yaml",
                "    description: The International Standard Book Number of the book.\n",
                "",
            ),
        )
    )
    assert bootstrapped.run()[0] == FAILED
    assert drafts(bootstrapped) == [], "a draft is written only when the whole run succeeds"


# ---- the refusals of PD-3's last row (TC-14) -----------------------------------------------------


def test_a_version_the_chain_already_left_is_refused(bootstrapped: Toy) -> None:
    """TC-14"""
    bootstrapped.edit(VERSION_2)
    assert bootstrapped.run()[0] == 0
    bootstrapped.edit((("library.yaml", 'version: "2"', 'version: "1"'),))
    code, printed = bootstrapped.run()
    assert code == FAILED, printed
    assert "1__2.yaml" in printed, "the file that left the version is named"


def test_a_lock_of_another_schema_is_refused(bootstrapped: Toy) -> None:
    """TC-14"""
    text = bootstrapped.lock.read_text("utf-8")
    other = text.replace("https://example.org/ns/library", "https://example.org/ns/other", 1)
    bootstrapped.lock.write_text(other, encoding="utf-8")
    code, printed = bootstrapped.run()
    assert code == FAILED, printed
    assert "https://example.org/ns/other" in printed, "the lock's schema id is named"


def test_an_unreadable_lock_is_refused(bootstrapped: Toy) -> None:
    """TC-14"""
    bootstrapped.lock.write_text("{not json", encoding="utf-8")
    code, printed = bootstrapped.run()
    assert code == FAILED, printed
    assert LOCK_NAME in printed, "the lock is named"
