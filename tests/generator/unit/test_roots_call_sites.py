"""Every generator call of a toolkit-schema function passes ``roots=`` (PD-5, TC-14a).

Without it the library's default applies, and the generator's own schema would get a consumer's
defaults and class-level rules.
"""

import json
import subprocess
from pathlib import Path

from rdf_persistence_generation.config import GENERATOR_DIR

PATTERNS = ("is_toolkit_schema($$$A)", "apply_defaults($$$A)", "generation_view($$$A)")
KEYWORD = "roots="


def calls_without_roots(folder: Path) -> list[str]:
    """The ``file:line`` of each call under ``folder`` that does not pass ``roots=``."""
    found: list[str] = []
    for pattern in PATTERNS:
        done = subprocess.run(
            [
                "ast-grep",
                "run",
                "--pattern",
                pattern,
                "--lang",
                "python",
                "--json=compact",
                str(folder),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        found += [
            f"{match['file']}:{match['range']['start']['line'] + 1}: {match['text']}"
            for match in json.loads(done.stdout)
            if KEYWORD not in match["text"]
        ]
    return sorted(found)


def test_every_generator_call_of_a_toolkit_schema_function_passes_roots() -> None:
    assert not calls_without_roots(GENERATOR_DIR), "a call without roots= (PD-5)"


def test_a_call_without_roots_is_named_by_file_and_line(tmp_path: Path) -> None:
    """Adversarial: the planted call is found, the one with ``roots=`` is not."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        "ok = is_toolkit_schema(folder, roots=ROOTS)\n"
        "\n"
        "bad = generation_view(path)\n"
        "worse = apply_defaults(view, folder)\n",
        encoding="utf-8",
    )

    found = calls_without_roots(tmp_path)

    assert [f.split(": ")[0] for f in found] == [f"{planted}:3", f"{planted}:4"], found
