#!/usr/bin/env python3
"""Check the dependency layers of the Foil production source tree."""
from pathlib import Path
import re
import sys
from foil_modules import inventory, LAYERS

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ('tests/', 'test_fixtures/', 'fixtures/')


def imports(text):
    for number, line in enumerate(text.splitlines(), 1):
        match = re.match(r'^\s*-[ \t]+(.*)', line)
        if match:
            # Options apply to the import; they are not module names.
            body = re.sub(r'\[[^\]]*\]', '', match[1].split("'", 1)[0])
            for name in body.split():
                yield name, number


def check(root, entries=None):
    if entries is None:
        try:
            entries = inventory(root)
        except (OSError, ValueError) as error:
            return [str(error)]
    sources = {p.relative_to(root).with_suffix('').as_posix(): p
               for p in sorted(root.rglob('*.foil'))}
    errors = []
    errors.extend(f'{name}: inventory source is missing'
                  for name in entries if name not in sources)
    graph = {}
    ranks = {}
    for name, path in sources.items():
        if name.startswith(FIXTURES):
            continue
        rank = LAYERS.index(entries[name][0]) if name in entries else None
        if rank is None:
            errors.append(f'{name}: unclassified production module')
            continue
        ranks[name] = rank
        graph[name] = list(imports(path.read_text()))
    for name, dependencies in graph.items():
        for dependency, line in dependencies:
            where = f'{name}:{line}'
            if dependency not in sources:
                errors.append(f'{where}: missing import {dependency}')
            elif dependency.startswith(FIXTURES):
                errors.append(f'{where}: production imports fixture {dependency}')
            elif dependency not in ranks:
                errors.append(f'{where}: unclassified import {dependency}')
            elif ranks[dependency] > ranks[name]:
                errors.append(f'{where}: upward import {dependency}')
    visited, active = set(), []

    def visit(name):
        if name in active:
            errors.append('import cycle: ' + ' -> '.join(active[active.index(name):] + [name]))
            return
        if name in visited:
            return
        active.append(name)
        for dependency, _ in graph.get(name, []):
            if dependency in graph:
                visit(dependency)
        active.pop()
        visited.add(name)

    for name in graph:
        visit(name)
    return errors


if __name__ == '__main__':
    errors = check(ROOT / 'src/foil')
    for error in errors:
        print(error, file=sys.stderr)
    sys.exit(bool(errors))
