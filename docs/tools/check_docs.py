"""Consistency checks for the rdf-persistence docs (run by `make check-docs`).

1. The architecture pages, the package and the tests use no consumer terms (capability
   rp-package-boundaries, PD-20); the background study is exempt.
2. Every page is reachable from the navigation.
3. The testing page names only exported testkit helpers (PD-7).
4. Every playbook serves the pinned mermaid.
5. Every xref and cross reference resolves to a page and an anchor (documentation-improvements
   DEC-7).
"""

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "docs/modules/ROOT"
CODE_DIRS = ["rdf_persistence", "rdf_persistence_generation", "tests"]
BYTECODE_DIR = "__pycache__"
ALL_NAME = "__all__"
MERMAID_PIN = "mermaid@"
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
        if f.suffix in CODE_SUFFIXES and BYTECODE_DIR not in f.parts
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
            isinstance(t, ast.Name) and t.id == ALL_NAME for t in node.targets
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


def check_mermaid_pin() -> list[str]:
    """Every playbook serves the mermaid the Makefile pins, so the site draws what `make check-diagrams` rendered."""
    pin = re.search(r"^MERMAID_VERSION\s*=\s*(\S+)", (ROOT / "Makefile").read_text(), re.M)
    if not pin:
        return ["Makefile: no MERMAID_VERSION"]
    wanted = f"mermaid@{pin.group(1)}/"
    return [
        f"{book.relative_to(ROOT)}: serves another mermaid than {pin.group(1)}"
        for book in sorted((ROOT / "docs").glob("antora-playbook*.yml"))
        if MERMAID_PIN in book.read_text() and wanted not in book.read_text()
    ]


VERBATIM = re.compile(r"^(-{4,}|\.{4,}|\+{4,}|/{4,})\s*$")
CODE_SPAN = re.compile(r"`[^`]*`")
XREF = re.compile(r"xref:([^\[\s]*)\[")
CROSS_REF = re.compile(r"<<([^>,\s]+)(?:,[^>]*)?>>")
HEADING = re.compile(r"^(={2,6})\s+(.+?)\s*$")
EXPLICIT_IDS = [
    re.compile(r"\[\[([\w:.-]+)(?:,[^\]]*)?\]\]"),
    re.compile(r"^\[[\w-]*#([\w:-]+)[^\]]*\]\s*$"),
    re.compile(r"anchor:([\w:-]+)\["),
]
ALIASES = re.compile(r"^:page-aliases:\s*(.+)$", re.M)
ROOT_MODULE = "ROOT:"
MODULE_MARK = ":"  # a target still holding one names another component or module
ATTRIBUTE_MARK = "{"  # a target built from an attribute cannot be resolved statically


def playbook_attribute(name: str, default: str) -> str:
    """An AsciiDoc attribute the site playbook sets, e.g. `idseparator: '-'`."""
    playbook = (ROOT / "docs/antora-playbook.yml").read_text()
    found = re.search(rf"^\s*{name}:\s*'([^']*)'", playbook, re.M)
    return found.group(1) if found else default


def section_id(title: str, prefix: str = "", separator: str = "-") -> str:
    """The id Asciidoctor gives a section title (the site sets idprefix '' and idseparator '-')."""
    text = re.sub(r"`([^`]*)`", r"\1", title)
    text = re.sub(r"(?<!\w)[*_]+(\S(?:.*?\S)?)[*_]+(?!\w)", r"\1", text)
    text = re.sub(r"[^\w .-]+", "", text.lower())
    text = (prefix + re.sub(r"[ .-]+", separator, text)).rstrip(separator)
    return text.lstrip(separator) if not prefix else text


def content_lines(text: str) -> list[str]:
    """The lines of a page outside verbatim blocks and comments, code spans removed."""
    lines, fence = [], None
    for line in text.splitlines():
        delimiter = VERBATIM.match(line)
        if fence:
            fence = None if line.strip() == fence else fence
        elif delimiter:
            fence = delimiter.group(1)
        elif not line.startswith("//"):
            lines.append(CODE_SPAN.sub("", line))
    return lines


def page_ids(text: str, prefix: str = "", separator: str = "-") -> set[str]:
    """Every anchor a page defines: explicit ids and the implicit ids of its section titles."""
    ids: set[str] = set()
    explicit_above = False
    for line in content_lines(text):
        found = [m for rx in EXPLICIT_IDS for m in rx.findall(line)]
        ids.update(found)
        heading = HEADING.match(line)
        if heading and not explicit_above:
            base = section_id(heading.group(2), prefix, separator)
            candidate, n = base, 1
            while candidate in ids:
                n += 1
                candidate = f"{base}{separator}{n}"
            ids.add(candidate)
        explicit_above = bool(found) and line.lstrip().startswith("[") and not heading
    return ids


def link_targets(text: str) -> list[tuple[str, str]]:
    """Each link of a page as (page, anchor); page '' is the page itself."""
    targets = []
    for line in content_lines(text):
        for target in XREF.findall(line) + CROSS_REF.findall(line):
            page, _, anchor = target.partition("#")
            if not page.endswith(".adoc"):
                page, anchor = "", anchor or page
            targets.append((page.removeprefix(ROOT_MODULE), anchor))
    return targets


def check_links() -> list[str]:
    """Every xref and cross reference names a page (or an alias) and an anchor that exist."""
    prefix, separator = playbook_attribute("idprefix", "_"), playbook_attribute("idseparator", "_")
    texts = {rel(p): p.read_text() for p in pages()}
    ids = {name: page_ids(text, prefix, separator) for name, text in texts.items()}
    for name, text in texts.items():
        for line in ALIASES.findall(text):
            for alias in line.split(","):
                ids[alias.strip().removeprefix(ROOT_MODULE)] = ids[name]
    sources = {**texts, "nav.adoc": (MODULE / "nav.adoc").read_text()}
    errors = []
    for name, text in sources.items():
        for page, anchor in link_targets(text):
            if MODULE_MARK in page or ATTRIBUTE_MARK in page + anchor:
                continue  # another component or module, or an attribute: not ours to resolve
            target = page or name
            shown = f"{page}#{anchor}" if page and anchor else page or anchor
            if target not in ids:
                errors.append(f"{name}: links to a page that does not exist: {shown}")
            elif anchor and anchor not in ids[target]:
                errors.append(f"{name}: links to an anchor that does not exist: {shown}")
    return errors


def mermaid_markdown() -> str:
    """Every `[mermaid]` block of every page, as one Markdown file the mermaid CLI renders at once."""
    blocks = re.compile(r"^\[mermaid\]\n\.{4}\n(.*?)\n\.{4}$", re.M | re.S)
    partial = re.compile(r"^include::partial\$([^\[]+)\[\]$", re.M)
    return "".join(
        f"<!-- {rel(page)} -->\n```mermaid\n"
        + partial.sub(lambda m: (MODULE / "partials" / m.group(1)).read_text().rstrip(), body)
        + "\n```\n\n"
        for page in pages()
        for body in blocks.findall(page.read_text())
    )


def main() -> int:
    if sys.argv[1:2] == ["--mermaid-markdown"]:
        Path(sys.argv[2]).write_text(mermaid_markdown())
        return 0
    errors = (
        check_forbidden_terms()
        + check_nav()
        + check_testkit_names()
        + check_mermaid_pin()
        + check_links()
    )
    for e in errors:
        print(f"FAIL {e}")
    print(f"{len(errors)} problem(s)" if errors else "docs check passed")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
