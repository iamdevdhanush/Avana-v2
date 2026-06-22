"""Scans Python files for typing constructs used but not imported from typing module."""
import ast
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

TYPING_SYMBOLS = {
    "Optional", "List", "Dict", "Set", "Tuple", "Any", "Union", "Callable",
    "Generator", "Iterable", "Iterator", "Type", "Sequence", "Mapping",
    "MutableMapping", "FrozenSet", "TypeVar", "Generic", "Protocol",
    "Literal", "Final", "ClassVar", "NamedTuple", "TypedDict",
    "Iterable", "Iterator", "AsyncIterable", "AsyncIterator",
    "Awaitable", "Coroutine", "AsyncGenerator",
    "Match", "Pattern", "Self",
    "NoReturn", "Never",
    "TypeAlias", "TypeGuard",
    "Concatenate", "ParamSpec", "ParamSpecArgs", "ParamSpecKwargs",
    "Unpack", "Annotated",
    "overload", "cast", "NewType",
}


def get_all_py_files():
    py_files = []
    for root, dirs, files in os.walk(BACKEND_DIR):
        # Skip virtual environments, __pycache__, etc.
        skip_dirs = {"__pycache__", ".git", ".venv", "venv", ".env", "env", ".mypy_cache", ".pytest_cache"}
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for f in files:
            if f.endswith(".py"):
                py_files.append(os.path.join(root, f))
    return sorted(py_files)


def get_imported_typing_symbols(tree):
    """Return set of typing symbols imported in the file."""
    imported = set()
    for node in ast.walk(tree):
        # from typing import Optional, List, ...
        if isinstance(node, ast.ImportFrom):
            if node.module == "typing":
                for alias in node.names:
                    imported.add(alias.name if alias.asname is None else alias.asname)
            # Handle from typing import Optional as Opt
            if node.module and (node.module == "typing" or node.module.startswith("typing.")):
                for alias in node.names:
                    imported.add(alias.name if alias.asname is None else alias.asname)
        # import typing
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "typing":
                    # Everything accessed as typing.Optional etc is implicitly available
                    imported.add("typing")
    return imported


def find_used_typing_symbols(tree):
    """Find all Name nodes that reference typing symbols in annotation contexts."""
    used = set()
    usages = {}  # symbol -> list of line numbers

    def record_usage(name, line):
        if name in TYPING_SYMBOLS:
            used.add(name)
            if name not in usages:
                usages[name] = []
            if line not in usages[name]:
                usages[name].append(line)

    for node in ast.walk(tree):
        # Function annotations (args and return)
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            if node.returns:
                for n in ast.walk(node.returns):
                    if isinstance(n, ast.Name):
                        record_usage(n.id, n.lineno)
                    # Handle subscript: Optional[str] -> Name.id = "Optional"
                    if isinstance(n, ast.Subscript):
                        if isinstance(n.value, ast.Name):
                            record_usage(n.value.id, n.value.lineno)
                        # Handle nested subscripts
                        _walk_annotation(n, record_usage)
            for arg in node.args.args + node.args.kwonlyargs + node.args.posonlyargs:
                if arg.annotation:
                    for n in ast.walk(arg.annotation):
                        if isinstance(n, ast.Name):
                            record_usage(n.id, n.lineno)
                        if isinstance(n, ast.Subscript):
                            if isinstance(n.value, ast.Name):
                                record_usage(n.value.id, n.value.lineno)
                            _walk_annotation(n, record_usage)
                # also check *args and **kwargs
            if node.args.vararg and node.args.vararg.annotation:
                for n in ast.walk(node.args.vararg.annotation):
                    if isinstance(n, ast.Name):
                        record_usage(n.id, n.lineno)
            if node.args.kwarg and node.args.kwarg.annotation:
                for n in ast.walk(node.args.kwarg.annotation):
                    if isinstance(n, ast.Name):
                        record_usage(n.id, n.lineno)

        # Variable annotations (e.g., x: Optional[str] = None)
        if isinstance(node, ast.AnnAssign):
            if node.annotation:
                for n in ast.walk(node.annotation):
                    if isinstance(n, ast.Name):
                        record_usage(n.id, n.lineno)
                    if isinstance(n, ast.Subscript):
                        if isinstance(n.value, ast.Name):
                            record_usage(n.value.id, n.value.lineno)
                        _walk_annotation(n, record_usage)

        # Class annotations / Pydantic model fields
        # Pydantic models use standard class annotations + Field(default=..., description=...)
        # We already catch AnnAssign above.
        # Also check class bases
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                if isinstance(base, ast.Name):
                    record_usage(base.id, base.lineno)
                if isinstance(base, ast.Subscript):
                    if isinstance(base.value, ast.Name):
                        record_usage(base.value.id, base.value.lineno)
                    _walk_annotation(base, record_usage)
                # Also check Attribute (e.g., BaseModel)
                _walk_annotation(base, record_usage)

        # Also check isinstance/issubclass calls
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in ("isinstance", "issubclass"):
                for arg in node.args:
                    for n in ast.walk(arg):
                        if isinstance(n, ast.Name):
                            record_usage(n.id, n.lineno)
                        if isinstance(n, ast.Subscript):
                            if isinstance(n.value, ast.Name):
                                record_usage(n.value.id, n.value.lineno)
                            _walk_annotation(n, record_usage)

        # Type aliases (e.g., MyType = Optional[str])
        if isinstance(node, ast.Assign):
            if node.value:
                for n in ast.walk(node.value):
                    if isinstance(n, ast.Name):
                        record_usage(n.id, n.lineno)
                    if isinstance(n, ast.Subscript):
                        if isinstance(n.value, ast.Name):
                            record_usage(n.value.id, n.value.lineno)
                        _walk_annotation(n, record_usage)

    return used, usages


def _walk_annotation(node, record_usage):
    """Walk nested annotations recursively."""
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            record_usage(child.id, child.lineno)
        if isinstance(child, ast.Subscript) and isinstance(child.value, ast.Name):
            record_usage(child.value.id, child.value.lineno)
        if isinstance(child, ast.Attribute):
            # e.g. typing.Optional -- if someone does `from typing import Optional` they'd use bare name
            pass


def main():
    files = get_all_py_files()
    print(f"Scanning {len(files)} Python files...\n")

    all_issues = []

    for filepath in files:
        relpath = os.path.relpath(filepath, BACKEND_DIR)
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()
        except Exception as e:
            print(f"  SKIP {relpath}: {e}")
            continue

        try:
            tree = ast.parse(source, filename=filepath)
        except SyntaxError as e:
            print(f"  PARSE ERROR {relpath}: {e}")
            continue

        imported = get_imported_typing_symbols(tree)
        used, usages = find_used_typing_symbols(tree)

        if not used:
            continue

        # Determine missing: symbols used but not imported
        missing = set()
        if "typing" not in imported:
            # Only individual imports from typing matter (not `import typing`)
            for sym in used:
                if sym not in imported:
                    missing.add(sym)
        else:
            # `import typing` is used, so typing.Optional etc are available
            # But if they use bare `Optional` without `typing.` prefix, it's still missing
            # Ast.Name nodes give us bare names, not qualified ones (typing.Optional would be an Attribute)
            # Since we check ast.Name nodes only, `typing.Optional` would appear as `Attribute(value=Name('typing'), attr='Optional')` 
            # So if we see `Optional` as ast.Name, it's a bare reference requiring an import
            for sym in used:
                if sym not in imported:
                    missing.add(sym)

        if missing:
            lines_info = {}
            for sym in missing:
                lines_info[sym] = usages.get(sym, [])
            all_issues.append((relpath, missing, lines_info))

    if not all_issues:
        print("No files found with missing typing imports!")
    else:
        print(f"Found {len(all_issues)} file(s) with missing typing imports:\n")
        for relpath, missing, lines_info in sorted(all_issues, key=lambda x: x[0]):
            print(f"  {relpath}")
            for sym in sorted(missing):
                lines = lines_info.get(sym, [])
                lines_str = ", ".join(str(l) for l in sorted(set(lines)))
                print(f"    Missing: {sym}")
                print(f"    Used at lines: {lines_str}")
            print()


if __name__ == "__main__":
    main()
