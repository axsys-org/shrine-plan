#!/usr/bin/env python3
"""Validate reaver.slots/v2 and generate the shared Foil vocabulary."""
import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / 'slots/system.slots.json'


def load(path):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError(f'duplicate JSON member: {key}')
            out[key] = value
        return out
    doc = json.loads(path.read_text(), object_pairs_hook=unique)
    if not isinstance(doc, dict) or set(doc) != {'format', 'slots'} or doc['format'] != 'reaver.slots/v2':
        raise ValueError('expected reaver.slots/v2 with format and slots fields')
    if not isinstance(doc['slots'], list) or not doc['slots']:
        raise ValueError('slots must be a nonempty array')
    seen = set()
    for slot in doc['slots']:
        if not isinstance(slot, dict) or set(slot) != {'path', 'title', 'summary'}:
            raise ValueError(f'invalid slot fields: {slot}')
        key = slot['path']
        if not isinstance(key, str) or not re.fullmatch(r'/sys(?:/[a-z][a-z0-9_]*)+', key):
            raise ValueError(f'invalid canonical system slot path: {key}')
        if key in seen:
            raise ValueError(f'duplicate slot: {key}')
        seen.add(key)
        for field in ['title', 'summary']:
            if not isinstance(slot[field], str) or not slot[field].strip() or '\n' in slot[field] or '\r' in slot[field]:
                raise ValueError(f'{key}: {field} must be nonempty single-line text')
    for key in seen:
        if any(other.startswith(key + '/') for other in seen):
            raise ValueError(f'slot is also a namespace prefix: {key}')
    return sorted(doc['slots'], key=lambda slot: slot['path'])


def declarations(slots, aliases=False):
    lines = []
    prior = []
    for slot in slots:
        parts = slot['path'].split('/')[2:]
        shared = 0
        while shared < min(len(prior), len(parts) - 1) and prior[shared] == parts[shared]:
            shared += 1
        for depth in range(shared, len(parts)):
            lines.append('  ' * depth + '+ ' + parts[depth])
        indent = '  ' * len(parts)
        if not aliases:
            lines.extend([indent + "' " + slot['title'], indent + "' " + slot['summary']])
        lines.extend([indent + '^ path', indent + ("'" + slot['path'])])
        prior = parts
    return '\n'.join(lines) + '\n'


def outputs(slots):
    banner = "' Generated from slots/system.slots.json by x/slot_catalog.py; edit the catalog.\n"
    system = '- sys/types\n\n' + banner + declarations(slots)
    # Foil's transitive imports do not retain a direct import's at= prefix.
    # Emit the same catalog constants under a namespace instead of importing
    # sys/slots, whose bare form/res/etc. would shadow application types.
    facade = '- sys/shrine\n\n' + banner + '+ system_vocabulary\n'
    facade += ''.join('  ' + line + '\n' for line in declarations(slots, True).splitlines())
    facade += '''  + locate
    ' Dynamic families use the same fixed system authority.
    \\ suffix=path
    ^ path
    | row/weld[iota] suffix ['sys]
  + source_slot
    \\ name=iota
    ^ path
    | system_vocabulary/locate ['fs 'source name]
'''
    def cord(value):
        return '"' + value.replace('"', '""') + '"'
    seeds = '- pact\n\n' + banner + '''+ slot_documentation
  + entries
    ^ row[[path str str]]
    ['''
    seeds += '\n     '.join("['" + slot['path'] + ' ' + cord(slot['title']) + ' ' + cord(slot['summary']) + ']'
                            for slot in slots)
    seeds += ''']
  + cards
    ^ axal[myth]
    = entries slot_documentation/entries
    | entries.fold (axal/new[myth] .none)
      \\ out [name title summary]
      | out.put name ((myth/sing bond/lede (pails/t title)).put(bond/help (lore "" [summary] [])))
'''
    return {ROOT / 'src/foil/sys/slots.foil': system,
            ROOT / 'src/foil/system_vocabulary.foil': facade,
            ROOT / 'src/foil/slot_documentation.foil': seeds}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='validate catalog and reject stale generated Foil')
    args = parser.parse_args()
    try:
        slots = load(CATALOG)
        stale = []
        for path, text in outputs(slots).items():
            if args.check:
                if not path.exists() or path.read_text() != text:
                    stale.append(str(path.relative_to(ROOT)))
            else:
                path.write_text(text)
        if stale:
            raise ValueError('stale generated files: ' + ', '.join(stale) + '; run python3 x/slot_catalog.py')
    except (ValueError, TypeError, OSError) as error:
        print(error, file=sys.stderr)
        return 1
    print(f'{len(slots)} documented system slots; generated declarations ' + ('verified' if args.check else 'updated'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
