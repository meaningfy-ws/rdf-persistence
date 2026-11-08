"""Consistency checks for the rdf-persistence docs (run by `make check-docs`).

1. The architecture pages, the package and the tests use no consumer terms (capability
   rp-package-boundaries, PD-20); the background study is exempt.
2. Every page is reachable from the navigation.
3. The testing page names only exported testkit helpers (PD-7).
"""

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "docs/modules/ROOT"
CODE_DIRS = ["rdf_persistence", "tests"]
CODE_SUFFIXES = {
    ".py",
    ".yaml",
    ".yml",
    ".toml",
    ".feature",
    ".ttl",
    ".jsonld",
    ".json",
    ".ini",
    ".md",
}
FORBIDDEN = [
    "MWB",
    "Mapping Workbench",
    "mapping project",
    "conceptual mapping",
    "technical mapping",
]


def pages() -> list[Path]:
    return sorted((MODULE / "pages").rglob("*.adoc"))


def rel(page: Path) -> str:
    return page.relative_to(MODULE / "pages").as_posix()


def code_files() -> list[Path]:
    return sorted(
        f
        for d in CODE_DIRS
        for f in (ROOT / d).rglob("*")
        if f.suffix in CODE_SUFFIXES and "__pycache__" not in f.parts
    )


def forbidden_in(files: list[Path]) -> list[str]:
    errors = []
    for f in files:
        text = f.read_text(errors="replace")
        errors += [
            f"{f.relative_to(ROOT)}: uses '{t}'"
            for t in FORBIDDEN
            if re.search(rf"\b{re.escape(t)}\b", text)
        ]
    return errors


def check_forbidden_terms() -> list[str]:
    architecture = [p for p in pages() if rel(p).startswith("architecture/")]
    return forbidden_in(architecture) + forbidden_in(code_files())


def check_nav() -> list[str]:
    linked = set(re.findall(r"xref:([\w./\-]+\.adoc)", (MODULE / "nav.adoc").read_text()))
    return [f"page not in nav: {rel(p)}" for p in pages() if rel(p) not in linked]


def testkit_exports(testkit: Path) -> set[str] | None:
    """The names in the testkit's ``__all__``, or None if it declares none."""
    init = testkit / "__init__.py"
    for node in ast.parse(init.read_text()).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets
        ):
            return set(ast.literal_eval(node.value))
    return None


def check_testkit_names() -> list[str]:
    testkit = ROOT / "rdf_persistence/testkit"
    exports = testkit_exports(testkit)
    if exports is None:
        return [f"{testkit.relative_to(ROOT)}/__init__.py: defines no __all__"]
    known = (
        exports
        | {p.stem for p in testkit.glob("*.py")}
        | {p.name for p in testkit.iterdir() if p.is_dir()}
    )
    page = MODULE / "pages/develop/testing.adoc"
    return [
        f"{rel(page)}: testkit.{name} is not exported"
        for name in sorted(set(re.findall(r"testkit\.(\w+)", page.read_text())) - known)
    ]


def main() -> int:
    errors = check_forbidden_terms() + check_nav() + check_testkit_names()
    for e in errors:
        print(f"FAIL {e}")
    print(f"{len(errors)} problem(s)" if errors else "docs check passed")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
