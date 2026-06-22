"""Grep-based scanner for typing symbols used but not imported."""
import re
import os
from collections import defaultdict

BACKEND = r'D:\Avana-v2\backend'

TYPING_SYMBOLS = [
    'Optional', 'List', 'Dict', 'Set', 'Tuple', 'Any', 'Union', 'Callable',
    'Generator', 'Iterable', 'Iterator', 'Type', 'Sequence', 'Mapping',
    'MutableMapping', 'FrozenSet', 'TypeVar', 'Generic', 'Protocol',
    'Literal', 'Final', 'ClassVar', 'NamedTuple', 'TypedDict',
    'Awaitable', 'Coroutine', 'AsyncGenerator', 'AsyncIterable',
    'AsyncIterator', 'Match', 'Pattern', 'Self', 'NoReturn', 'Never',
    'TypeAlias', 'TypeGuard', 'Unpack', 'Annotated', 'overload', 'NewType'
]

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
                lines = fh.readlines()
        except:
            continue

        # Build set of imported typing symbols
        imported_typing = set()
        has_import_typing = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('#'):
                continue
            # from typing import Optional, List, ...
            m = re.match(r'^from\s+typing\s+import\s+(.+)$', stripped)
            if m:
                for part in m.group(1).split(','):
                    # Handle `import Optional as Opt` or just `import Optional`
                    sym = part.strip().split(' as ')[0].strip()
                    # Handle `import Optional, List` etc (already split by comma)
                    for s in sym.split():
                        s = s.strip().rstrip(',')
                        if s:
                            imported_typing.add(s)
            # import typing
            if re.match(r'^import\s+typing', stripped):
                has_import_typing = True

        # Scan for typing symbol usage
        for lineno, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            # Skip import lines
            if re.match(r'^(from\s+typing|import\s+typing)', stripped):
                continue
            # Skip lines with typing. prefix (qualified access)
            if 'typing.' in stripped:
                continue
            # Skip string literals
            in_single_str = False
            in_double_str = False
            for c in stripped:
                if c == "'" and not in_double_str:
                    in_single_str = not in_single_str
                elif c == '"' and not in_single_str:
                    in_double_str = not in_double_str
            if in_single_str or in_double_str:
                continue

            for sym in TYPING_SYMBOLS:
                if sym in imported_typing or has_import_typing:
                    continue
                # Look for symbol used in annotation-like contexts
                # Patterns: :Optional, ->Optional, =Optional, (Optional, ,Optional, [Optional
                # Or bare symbol used as type: `Optional[` or `Optional,` or `Optional)` 
                # Or in type alias: `= Optional[`
                pattern = r'(?::|->|=|\(|,|\[)\s*' + re.escape(sym) + r'\b'
                if re.search(pattern, stripped):
                    issues.append((relpath, sym, lineno, stripped.strip()))

print(f'Files scanned: {files_checked}')
print()

# Group by file
by_file = defaultdict(lambda: defaultdict(list))
for relpath, sym, lineno, line_text in issues:
    by_file[relpath][sym].append((lineno, line_text))

found_any = False
for relpath in sorted(by_file):
    if by_file[relpath]:
        found_any = True
        print(f'FILE: {relpath}')
        for sym in sorted(by_file[relpath]):
            lines_info = by_file[relpath][sym]
            print(f'  Missing import: {sym}')
            for ln, text in lines_info:
                print(f'    Line {ln}: {text}')
        print()

if not found_any:
    print('No files found with missing typing imports.')
