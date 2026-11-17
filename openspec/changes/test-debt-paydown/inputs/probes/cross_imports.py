"""List imports of one test module by another, grouped by the imported module, with the names."""
import ast, pathlib, re, collections
root = pathlib.Path("tests")
by_source = collections.defaultdict(list)
for path in sorted(root.rglob("test_*.py")):
    tree = ast.parse(path.read_text())
    pkg = ".".join(path.parent.parts)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if node.level:
                base = path.parent.parts[: len(path.parent.parts) - (node.level - 1)]
                mod = ".".join(base) + ("." + mod if mod else "")
            if re.search(r"(^|\.)test_[a-z0-9_]+$", mod):
                by_source[mod].append((str(path), [a.name for a in node.names]))
for src in sorted(by_source, key=lambda s: -len(by_source[s])):
    names = collections.Counter(n for _, ns in by_source[src] for n in ns)
    print(f"\n## {src}  ({len(by_source[src])} importers)  names: {', '.join(f'{n}x{c}' if c>1 else n for n,c in names.most_common())}")
    for imp, ns in by_source[src]:
        print(f"   <- {imp}: {', '.join(ns)}")
print("\nTOTAL import statements:", sum(len(v) for v in by_source.values()), "source modules:", len(by_source))
