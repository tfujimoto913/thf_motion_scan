"""Generate docs/functions.md listing top-level public classes and functions."""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
OUT = ROOT / "docs" / "functions.md"


def first_line(doc: str | None) -> str:
    """Return the first non-empty line from a docstring-like value."""
    if not doc:
        return ""
    return doc.strip().splitlines()[0]


def parse_symbols(py_path: Path):
    """Collect top-level public classes and functions from a module."""
    tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
    module = py_path.relative_to(SRC).with_suffix("").as_posix().replace("/", ".")
    items = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            doc = first_line(ast.get_docstring(node))
            items.append(("class", node.name, doc if doc else "_no doc_", node.lineno))
        elif isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            doc = first_line(ast.get_docstring(node))
            items.append(("function", node.name, doc if doc else "_no doc_", node.lineno))

    return module, sorted(items, key=lambda it: (it[0], it[1].lower()))


def main() -> None:
    """Generate the Markdown index."""
    if not SRC.exists():
        raise SystemExit(f"Expected source directory at {SRC}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    by_module: dict[str, list[tuple[Path, str, str, str, int]]] = defaultdict(list)

    for py_file in sorted(SRC.rglob("*.py")):
        module, items = parse_symbols(py_file)
        if items:
            for kind, name, doc, lineno in items:
                by_module[module].append((py_file, kind, name, doc, lineno))

    lines = [
        "# Functions & Classes Index\n",
        "_Auto-generated. Edit code/docstrings, not this file._\n",
    ]

    for module in sorted(by_module):
        lines.append(f"\n## `{module}`\n")
        for py_path, kind, name, doc, lineno in sorted(
            by_module[module], key=lambda it: (it[1], it[2].lower())
        ):
            rel_path = py_path.relative_to(ROOT).as_posix()
            lines.append(
                f"- **{kind}** `{name}` — {doc}  \n"
                f"  `./{rel_path}:{lineno}`"
            )

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
