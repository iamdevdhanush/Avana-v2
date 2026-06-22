"""AST-based scanner for typing symbols used but not imported."""
import ast
import os

BACKEND = r'D:\Avana-v2\backend'

TYPING_SYMBOLS = {
    'Optional', 'List', 'Dict', 'Set', 'Tuple', 'Any', 'Union', 'Callable',
    'Generator', 'Iterable', 'Iterator', 'Type', 'Sequence', 'Mapping',
    'MutableMapping', 'FrozenSet', 'TypeVar', 'Generic', 'Protocol',
    'Literal', 'Final', 'ClassVar', 'NamedTuple', 'TypedDict',
    'Awaitable', 'Coroutine', 'AsyncGenerator', 'AsyncIterable',
    'AsyncIterator', 'Match', 'Pattern', 'Self', 'NoReturn', 'Never',
    'TypeAlias', 'TypeGuard', 'Unpack', 'Annotated', 'overload', 'NewType'
}


def get_imports(tree):
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == 'typing':
                for alias in node.names:
                    name = alias.asname if alias.asname else alias.name
                    imported.add(name)
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == 'typing':
                    imported.add('typing')
    return imported


def find_typing_usage(node, used):
    if isinstance(node, ast.Name):
        if node.id in TYPING_SYMBOLS and node.id != 'Type':
            used.append((node.id, node.lineno))
    for child in ast.iter_child_nodes(node):
        find_typing_usage(child, used)


files_checked = 0
issues = []

for root, dirs, files in os.walk(BACKEND):
    skip = {'__pycache__', '.git', '.venv', 'venv', '.mypy_cache', '.pytest_cache'}
    dirs[:] = [d for d in dirs if d not in skip]
    for f in files:
        if not f.endswith('.py'):
            continue
        filepath = os.path.join(root, f)
        relpath = os.path.relpath(filepath, BACKEND)
        files_checked += 1

        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as fh:
                source = fh.read()
        except:
            continue

        try:
            tree = ast.parse(source, filename=filepath)
        except SyntaxError:
            continue

        imports = get_imports(tree)
        has_typing_module = 'typing' in imports

        # Collect all uses of typing symbols
        raw_uses = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.returns:
                    find_typing_usage(node.returns, raw_uses)
                for arg in node.args.args + node.args.kwonlyargs + node.args.posonlyargs:
                    if arg.annotation:
                        find_typing_usage(arg.annotation, raw_uses)
                if node.args.vararg and node.args.vararg.annotation:
                    find_typing_usage(node.args.vararg.annotation, raw_uses)
                if node.args.kwarg and node.args.kwarg.annotation:
                    find_typing_usage(node.args.kwarg.annotation, raw_uses)
            if isinstance(node, ast.AnnAssign):
                if node.annotation:
                    find_typing_usage(node.annotation, raw_uses)
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    find_typing_usage(base, raw_uses)
            if isinstance(node, ast.Assign):
                if node.value:
                    find_typing_usage(node.value, raw_uses)
            if isinstance(node, ast.Call):
                find_typing_usage(node, raw_uses)

        # Group by symbol
        used_lines = {}
        for sym, lineno in raw_uses:
            if sym not in used_lines:
                used_lines[sym] = []
            if lineno not in used_lines[sym]:
                used_lines[sym].append(lineno)

        if not used_lines:
            continue

        missing = set()
        for sym in used_lines:
            if not has_typing_module and sym not in imports:
                missing.add(sym)
            elif has_typing_module and sym not in imports:
                missing.add(sym)

        if missing:
            issues.append((relpath, missing, used_lines))

# Exclude our own scanner scripts
issues = [(r, m, l) for r, m, l in issues if '_scan_missing_imports' not in r]

print(f'Files scanned: {files_checked}')
print(f'Files with missing typing imports: {len(issues)}')
print()

if not issues:
    print('No issues found.')
else:
    for relpath, missing, lines in sorted(issues, key=lambda x: x[0]):
        print(f'FILE: {relpath}')
        for sym in sorted(missing):
            print(f'  Missing: {sym}')
            print(f'  Used at lines: {sorted(lines[sym])}')
        print()
