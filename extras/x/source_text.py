"""Print the schema compiler's normalized Rex as editable Foil source.

Render each child once. The generic Rex printer cannot recover statement layout
from normalized clear nodes, and trying both flat and vertical layouts recursively
is prohibitively expensive for generated nested matches.
"""
from functools import lru_cache


def indent(text):
    return '\n'.join('  ' + line for line in text.split('\n'))


def surface(node):
    kind, *parts = node
    if kind == 'leaf':
        return kind, *parts
    if kind == 'juxt':
        return 'juxt', tuple(surface(child) for child in parts[0])
    color, rune, children = parts
    children = tuple(surface(child) for child in children)
    if color == 'clear':
        # The schema compiler emits scalar byte casts in expression positions.
        # (^ ...) is reflection in source syntax; str/from_atom is the same
        # representation-preserving cast and remains valid inside calls.
        if rune == '^' and len(children) == 2 and children[0] == ('leaf', 'word', 'str'):
            return 'bracket', 'paren', (('tight', '/', (('leaf', 'word', 'str'), ('leaf', 'word', 'from_atom'))), children[1])
        if not rune:
            return 'group', children
        if rune == '=' and (len(children) > 2 or (children and children[0][:2] == ('tight', '='))):
            return 'open', rune, children
        if rune in ('=', '/', '.', './'):
            return 'tight', rune, children
        return 'open', rune, children
    if not rune:
        return 'bracket', color, children
    if rune in ('=', '/', '.', './'):
        return 'bracket', color, (('tight', rune, children),)
    return 'bracket', color, (('open', rune, children),)


def cat(parts):
    result = ''
    for part in parts:
        column = len(result.rsplit('\n', 1)[-1])
        result += part.replace('\n', '\n' + ' ' * column)
    return result


@lru_cache(maxsize=None)
def print_node(node):
    kind, *parts = node
    if kind == 'leaf':
        shape, text = parts
        if shape == 'slug':
            return '\n'.join("' " + line for line in text.split('\n'))
        if shape in ('cord', 'tape'):
            return '"' + text.replace('"', '""') + '"'
        if shape in ('page', 'span'):
            return "'''" + text + "'''"
        return text
    if kind == 'group':
        return '\n'.join(print_node(child) for child in parts[0])
    if kind == 'juxt':
        children = parts[0]
        # A continuation binding can carry a statement cast. Parenthesizing
        # ^ would change it to type reflection, so keep its indented body.
        if len(children) == 2 and children[1][0] == 'open':
            return print_node(children[0]) + '\n' + indent(print_node(children[1]))
        return cat(part for i, child in enumerate(parts[0])
                   for part in ([' ', tight(child)] if i and child[0] != 'bracket' else [tight(child)]))
    if kind == 'tight':
        rune, children = parts
        if len(children) == 1:
            return cat([rune, tight(children[0])])
        return cat([part for i, child in enumerate(children) for part in ([rune, tight(child)] if i else [tight(child)])])
    if kind == 'bracket':
        color, children = parts
        opening, closing = {'paren': ('(', ')'), 'brack': ('[', ']'), 'curly': ('{', '}')}[color]
        return cat([opening, *[part for i, child in enumerate(children) for part in ([' ', tight(child)] if i else [tight(child) if len(children) > 1 else print_node(child)])], closing])
    rune, children = parts
    printed = [print_node(child) for child in children]
    if not printed:
        return rune
    if len(printed) == 1 and '\n' not in printed[0] and children[0][0] not in ('open', 'group'):
        return rune + ' ' + printed[0]
    # An open rune owns its indented children, including multiline conditions.
    return cat([rune + ' ', printed[0]]) + ('\n' + indent('\n'.join(printed[1:])) if len(printed) > 1 else '')


def tight(node):
    text = print_node(node)
    return cat(['(', text, ')']) if node[0] in ('open', 'group') else text


def render(tree):
    try:
        return print_node(surface(tree))
    finally:
        print_node.cache_clear()
