"""Run contracts of the repository's own ``.importlinter`` on a scratch package, and read which are broken.

Two test modules plant an import in a scratch copy of the layout and expect a named contract to break:
``test_theme_contracts`` and ``test_technical_split``. They share this one helper, so the way a
contract is copied, re-rooted and read back is one place.

The scratch config names each contract by its key (``domain-pure``), not by its long title, and the
report is read as one text with its whitespace removed, so a name that the report wraps over two lines
is still found.
"""

import configparser
import re
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[2]
ROOT_PACKAGE = "rdf_persistence"
LINT_IMPORTS = Path(sys.executable).parent / "lint-imports"
BROKEN = "BROKEN"


def write_package(tmp_path: Path, files: Mapping[str, str]) -> None:
    """Write ``files`` (path relative to the package, text) under ``tmp_path / rdf_persistence``."""
    for rel, text in files.items():
        path = tmp_path / ROOT_PACKAGE / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def scratch_config(
    contracts: tuple[str, ...],
    overrides: Mapping[str, Mapping[str, str]] | None = None,
    source: Path = ROOT / ".importlinter",
) -> configparser.ConfigParser:
    """The named contracts of ``source`` on the scratch root package, each named by its key.

    ``overrides`` sets options of a contract (``{"runtime-without-extras": {"source_modules": ...}}``),
    for a name the scratch package does not have.
    """
    parsed = configparser.ConfigParser(inline_comment_prefixes=None, interpolation=None)
    parsed.read(source, encoding="utf-8")
    scratch = configparser.ConfigParser(interpolation=None)
    scratch["importlinter"] = {
        "root_packages": f"\n{ROOT_PACKAGE}",
        "include_external_packages": "True",
    }
    for key in contracts:
        section = f"importlinter:contract:{key}"
        assert parsed.has_section(section), f"contract {key} is gone from {source.name}"
        scratch[section] = {**parsed[section], "name": key, **(overrides or {}).get(key, {})}
    return scratch


def broken_in(report: str, contracts: tuple[str, ...]) -> list[str]:
    """The keys of ``contracts`` the report names BROKEN, whatever way it wrapped the line."""
    squeezed = re.sub(r"\s+", "", report)
    parts = re.split(r"(KEPT|BROKEN)", squeezed)
    broken = set()
    for before, verdict in zip(parts[0::2], parts[1::2], strict=False):
        name = re.search(r"[\w-]+$", before)  # the name is what ends the text before its verdict
        if verdict == BROKEN and name:
            broken.add(name.group().lstrip("-"))
    return [key for key in contracts if key in broken]


class Linted(NamedTuple):
    """What a lint run says: the exit code, the keys of the broken contracts, the whole report."""

    code: int
    broken: list[str]
    report: str


def run_contracts(
    tmp_path: Path,
    files: Mapping[str, str],
    contracts: tuple[str, ...],
    overrides: Mapping[str, Mapping[str, str]] | None = None,
) -> tuple[int, list[str]]:
    """Plant ``files``, lint the named contracts: ``(exit code, keys of the broken ones)``."""
    linted = lint_contracts(tmp_path, files, contracts, overrides)
    return linted.code, linted.broken


def lint_contracts(
    tmp_path: Path,
    files: Mapping[str, str],
    contracts: tuple[str, ...],
    overrides: Mapping[str, Mapping[str, str]] | None = None,
) -> Linted:
    """Plant ``files``, lint the named contracts, and keep the report (it names the modules)."""
    write_package(tmp_path, files)
    config = tmp_path / "scratch.importlinter"
    with config.open("w", encoding="utf-8") as handle:
        scratch_config(contracts, overrides).write(handle)
    done = subprocess.run(
        [str(LINT_IMPORTS), "--config", config.name],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    return Linted(done.returncode, broken_in(done.stdout, contracts), done.stdout)


# The contracts that keep a technical model out of a domain and a layer from reaching the one above it
# (thematic-structure PD-6): `domain-never-imports-technical-models` and `layers` are gone, and these
# take their place. The first words of each contract's `name` are what a BROKEN line carries.
CONTRACT_DOMAIN = "domain-of-a-theme-imports-no-upper-layer"
CONTRACT_SERVICES = "services-of-a-theme-import-no-adapters-or-entrypoints"
CONTRACT_ENTRYPOINTS = "entrypoints-of-themes-import-no-adapters"
CONTRACT_RUNTIME = "runtime-without-extras"

SCRATCH_LAYOUT = {
    "__init__.py": "",
    "core/__init__.py": "",
    "core/domain/__init__.py": "",
    "core/domain/generated/__init__.py": "",
    "core/domain/generated/rp_core.py": "",
    "iris/__init__.py": "",
    "iris/domain/__init__.py": "",
    "iris/domain/layout.py": "",
    "persistence/__init__.py": "",
    "persistence/services/__init__.py": "",
    "persistence/services/session.py": "",
    "access/__init__.py": "",
    "access/adapters/__init__.py": "",
    "access/adapters/generated/__init__.py": "",
    "access/adapters/generated/rp_access_adapters.py": "",
    "api/__init__.py": "",
    "api/entrypoints/__init__.py": "",
    "api/entrypoints/router.py": "",
    "api/entrypoints/generated/__init__.py": "",
    "api/entrypoints/generated/rp_api_entrypoints.py": "",
    "api/entrypoints/generated/settings/__init__.py": "",
    "api/entrypoints/generated/settings/rp_api_settings.py": "",
}
KEPT_CONTRACTS = (CONTRACT_DOMAIN, CONTRACT_SERVICES, CONTRACT_ENTRYPOINTS, CONTRACT_RUNTIME)
# the runtime contract also names the generator and test tools, which are no package of the scratch copy
SCRATCH_OVERRIDES = {
    CONTRACT_RUNTIME: {
        "forbidden_modules": "\nrdf_persistence.testkit",
        "source_modules": (
            "\nrdf_persistence.*.domain\nrdf_persistence.*.services\nrdf_persistence.*.adapters"
        ),
    }
}


def lint_scratch(tmp_path: Path, planted: dict[str, str]) -> Linted:
    """The kept contracts on the scratch layout: exit code, broken contracts, report."""
    return lint_contracts(
        tmp_path, {**SCRATCH_LAYOUT, **planted}, KEPT_CONTRACTS, SCRATCH_OVERRIDES
    )
