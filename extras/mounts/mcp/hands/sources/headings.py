"""Headings: a markdown or text file whose structure is its headings, nested by level. Lazy: the skeleton is every
heading as a path (its slug under the slugs of the headings above it); a region is the heading's `title`, its
`level` and `line`, and `words` and `body` (a digest) of what is under it up to the next heading of any level (a
nested heading is a region of its own). The prose itself stays in the file; a `text` slot put on a region is
written back under its heading and leaves the world again."""
import hashlib
import re


eager = False


def slug(text):
    key = re.sub(r'[^A-Za-z0-9_]+', '_', text.strip()).strip('_').lower() or 'untitled'
    return key if re.match(r'[a-z]', key) else 'h_' + key


def read(source):
    with open(source['where'], encoding='utf-8') as f:
        return f.read()


def marker(source):
    return 'sha256 ' + hashlib.sha256(read(source).encode()).hexdigest()[:16]


def headings(text):
    """(path, level, line, title, body) for every heading, in order."""
    lines = text.split('\n')
    found = []
    stack = []
    for i, line in enumerate(lines):
        m = re.match(r'^(#{1,6})\s+(.*?)\s*#*\s*$', line)
        if not m:
            continue
        level, title = len(m.group(1)), m.group(2)
        while stack and stack[-1][1] >= level:
            stack.pop()
        path = '/'.join([s[0] for s in stack] + [slug(title)])
        stack.append((slug(title), level))
        found.append([path, level, i + 1, title])
    for n, h in enumerate(found):
        end = found[n + 1][2] - 1 if n + 1 < len(found) else len(lines)
        h.append('\n'.join(lines[h[2]:end]).strip('\n'))
    return found


def skeleton(source):
    return [h[0] for h in headings(read(source))]


def regions(source, paths):
    wanted = set(paths)
    return {path: {'title': title, 'level': level, 'line': line, 'words': len(body.split()), 'body': hashlib.sha256(body.encode()).hexdigest()[:16]}
            for path, level, line, title, body in headings(read(source)) if path in wanted}


def write(source, path, slots):
    """Put a region's text (and title) back under its heading, and nothing else: the lines between the heading and
    the next heading are replaced, the rest of the file is kept byte for byte."""
    text = read(source)
    lines = text.split('\n')
    found = headings(text)
    for n, (p, level, line, title, body) in enumerate(found):
        if p != path:
            continue
        end = found[n + 1][2] - 1 if n + 1 < len(found) else len(lines)
        head = '#' * level + ' ' + str(slots.get('title', title))
        new_body = str(slots['text']).split('\n') if 'text' in slots else lines[line:end]
        tail = [''] if end < len(lines) and new_body and new_body[-1] != '' else []
        lines[line - 1:end] = [head] + new_body + tail
        break
    with open(source['where'], 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
