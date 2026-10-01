#!/usr/bin/env python3
"""Adapt the legacy Goo fixtures into a single browsable Grove module."""
from pathlib import Path
import argparse
import json
import re
import unicodedata

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / 'goo' / 'examples'

class Parser:
    def __init__(self, text):
        self.tokens = []
        # Rex strings escape a quote by doubling it; apostrophe lines are comments.
        pattern = r'(?P<space>\s+)|(?P<comment>\'[^\n]*)|(?P<string>"(?:[^"]|"")*")|(?P<word>[^\s(){}\[\],:"]+)|(?P<punct>[(){}\[\],:])'
        pos = 0
        for match in re.finditer(pattern, text):
            if match.start() != pos:
                raise ValueError(f'Unexpected source at {pos}')
            pos = match.end()
            if match.lastgroup not in ('space', 'comment'):
                self.tokens.append((match.lastgroup, match.group()))
        if pos != len(text):
            raise ValueError(f'Unparsed source at {pos}')
        self.i = 0

    def peek(self, text):
        return self.i < len(self.tokens) and self.tokens[self.i][1] == text

    def pop(self, expected=None):
        token = self.tokens[self.i]
        self.i += 1
        if expected is not None and token[1] != expected:
            raise ValueError(f'Expected {expected}, got {token}')
        return token

    def value(self):
        if self.peek('{'):
            self.pop('{')
            fields = {}
            while not self.peek('}'):
                self.pop('[')
                key = self.pop()[1]
                self.pop(']')
                self.pop(':')
                fields[key] = self.value()
                if not self.peek('}'):
                    self.pop(',')
            self.pop('}')
            return fields
        kind, text = self.pop()
        if kind == 'string':
            return ('string', text[1:-1].replace('""', '"'))
        if text == 'escaped' and self.peek('('):
            self.pop('(')
            literal = self.value()
            self.pop(')')
            return ('string', json.loads('"' + literal[1] + '"'))
        return ('word', text)

    def node(self):
        if self.peek('('):
            self.pop('(')
            node = self.node()
            self.pop(')')
            return node
        name = self.pop()[1]
        args = []
        children = None
        if self.peek('('):
            self.pop('(')
            while not self.peek(')'):
                args.append(self.value())
                if not self.peek(')'):
                    self.pop(',')
            self.pop(')')
        if self.peek('{'):
            self.pop('{')
            children = []
            while not self.peek('}'):
                children.append(self.node())
            self.pop('}')
        return name, args, children

    def parse(self):
        nodes = []
        while self.i < len(self.tokens):
            nodes.append(self.node())
        return nodes

PUNCTUATION = str.maketrans({'·': ' / ', '—': ' - ', '–': '-', '→': '->', '←': '<-', '…': '...', '×': 'x', '’': "'", '‘': "'", '“': '"', '”': '"', '✓': '[yes]', '⚠': '[warning]', '€': 'EUR ', '£': 'GBP ', '°': ' deg ', '≤': '<=', '≥': '>=', '\u00a0': ' '})

def ascii_text(text):
    text = unicodedata.normalize('NFKD', text.translate(PUNCTUATION))
    text = ''.join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r'[^\x00-\x7f]+', '[Unicode]', text)
    return text

def quoted(text):
    return '"' + text.replace('"', '""') + '"'

def emit_value(value, changes):
    if isinstance(value, dict):
        return '{' + ', '.join('[' + k + ']: ' + emit_value(v, changes) for k, v in value.items()) + '}'
    kind, text = value
    if kind == 'string':
        adapted = ascii_text(text)
        if adapted != text:
            changes.append({'original': text, 'adapted': adapted})
        if any(c in adapted for c in '\n\r\t'):
            return 'escaped(' + quoted(json.dumps(adapted)[1:-1]) + ')'
        return quoted(adapted)
    if text.startswith('%'):
        return quoted(text[1:])
    return text

def emit_node(node, indent, changes):
    name, args, kids = node
    args = list(args)
    optional = None
    if args and isinstance(args[0], dict):
        config = dict(args[0])
        optional = config.pop('optional', None)
        args = ([config] if config else []) + args[1:]
    lines = []
    # Legacy optional annotations become explicit v2 optional subtrees.
    if optional and optional[1] != '0':
        lines.append(' ' * indent + 'opt(' + optional[1] + ') {')
        indent += 2
    head = name + ('(' + ', '.join(emit_value(a, changes) for a in args) + ')' if args else '')
    lines.append(' ' * indent + head + (' {' if kids is not None else ''))
    for kid in kids or []:
        lines.extend(emit_node(kid, indent + 2, changes))
    if kids is not None:
        lines.append(' ' * indent + '}')
    if optional and optional[1] != '0':
        lines.append(' ' * (indent - 2) + '}')
    return lines

def generate():
    metadata = {}
    for source in sorted(SOURCE.glob('*.json')):
        for item in json.loads(source.read_text()):
            metadata[item['name']] = item
    families = {}
    manifest = []
    for source in sorted(SOURCE.glob('*.goo')):
        match = re.match(r'(g\d{3})(?:-v[12])?-(.*)', source.stem)
        family = match[1] + '-' + match[2] if match else source.stem
        families.setdefault(family, []).append(source)
    lines = ['#import text=lib/grove/types/text', '#import lede=sys/lede', '',
             '\' Generated by generate.py; edit the original Goo fixtures, then regenerate.', '']
    for family, sources in sorted(families.items()):
        ident = family.replace('-', '_')
        lines += [ident + '_key =', '  @slot', '', ident + '_role =', '  @role', '  %/' + ident + '_key: text', '']
        for source in sources:
            changes = []
            nodes = Parser(source.read_text()).parse()
            info = metadata.get(source.stem, {})
            view = source.stem.replace('-', '_')
            # Unique slots keep all variants independently addressable.
            lines += ["' Source: ../goo/examples/" + source.name, "",
                      view + '_view =', '  @view', '  #on ; %/' + ident + '_role',
                      '  #for ; ' + quoted('/demo/goo/views/' + view), '  ! goo', '  item => {']
            for node in nodes:
                lines += emit_node(node, 4, changes)
            lines += ['  }', '']
            manifest.append({'source': source.name, 'object': '/app/examples/' + ident,
                             'view': view + '_view', 'settings': info.get('settings', {}),
                             'text_adaptations': changes})
        lines += [quoted('/' + ident) + ' =', '  @tree', '  lede: ' + quoted(ascii_text(family)),
                  '  %/' + ident + '_key: ' + quoted(family), '']
    lines += ['"/" =', '  @tree', '  lede: "Goo example gallery"', '']
    return '\n'.join(lines), json.dumps(manifest, ensure_ascii=False, indent=2) + '\n'

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()
    grove, manifest = generate()
    for name, content in [('examples.grove', grove), ('adaptations.json', manifest)]:
        path = HERE / name
        if args.check:
            assert path.read_text() == content, f'{name} needs regeneration'
        else:
            path.write_text(content)
    entries = json.loads(manifest)
    print(f'{len(entries)} views, {len({e["object"] for e in entries})} objects; {sum(bool(e["text_adaptations"]) for e in entries)} fixtures with adapted text')
