"""Small standard-library client for the native cooperation commands.

This client supplies MCP transport and bounded context retrieval. It does not
schedule agents, call a model, or duplicate server-side lifecycle checks.
"""
import argparse
import json
import re
import sys
import urllib.error
import urllib.request


class Refused(RuntimeError):
    """An operation was refused by the namespace admission boundary."""

    def __init__(self, reply):
        self.reply = reply
        detail = reply.get('reason') or reply.get('error')
        if not detail:
            detail = json.dumps(reply, ensure_ascii=False)
        super().__init__(str(detail))


class ContextLimit(RuntimeError):
    """A complete context would exceed the caller's declared budget."""


def reference(path, care='x', case=0):
    """Encode a pinned /h reference or a live namespace/derived path."""
    if not path.startswith('/'):
        raise ValueError('references must be absolute namespace paths')
    if path.startswith('/h/'):
        return {'type': 'reference', 'value': path}
    if care not in ('x', 'y', 'z'):
        raise ValueError('care must be x, y, or z')
    return {'type': 'reference', 'path': path, 'care': care, 'case': case}


def _name(value):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', value):
        raise ValueError('names must start with a letter or underscore and use letters, digits or _')
    return value


def _reference_inputs(context):
    return {'context/' + _name(label): value if isinstance(value, dict) else reference(value, 'z')
            for label, value in (context or {}).items()}


class Client:
    def __init__(self, base, node='0x11', timeout=120):
        self.base = base.rstrip('/')
        self.node = node.strip('/')
        self.timeout = timeout
        self.sequence = 0
        self.publisher = '/' + self.node + '/gov/cooperate'

    def tool(self, name, **arguments):
        self.sequence += 1
        request = urllib.request.Request(
            self.base + '/mcp',
            json.dumps({'jsonrpc': '2.0', 'id': self.sequence,
                        'method': 'tools/call',
                        'params': {'name': 'mcp/' + name, 'arguments': arguments}}).encode(),
            {'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            reply = json.load(response)
        if 'error' in reply:
            raise Refused(reply)
        result = reply.get('result') or {}
        value = result.get('structuredContent')
        if result.get('isError') or (isinstance(value, dict) and value.get('refused')):
            raise Refused(value if isinstance(value, dict) else result)
        if not isinstance(value, dict):
            raise RuntimeError('MCP response omitted structuredContent')
        return value

    def read(self, path, care='x', **options):
        return self.tool('read', path=path, care=care, **options)

    def apply(self, operation, target, inputs):
        return self.tool('apply', path=target,
                         operation=self.publisher + '/' + operation, inputs=inputs)

    def open(self, document, ident, content, *, context=None, parent=None, procedure=None):
        inputs = dict(id=_name(ident), content=content)
        inputs.update(_reference_inputs(context))
        for name, value in [('parent', parent), ('procedure', procedure)]:
            if value is not None:
                inputs[name] = value if isinstance(value, dict) else reference(value)
        return self.apply('open', document, inputs)

    def append(self, run, ident, kind, content, *, context=None, reply_to=None, artifact=None):
        inputs = dict(id=_name(ident), kind=kind, content=content)
        inputs.update(_reference_inputs(context))
        for name, value in [('reply_to', reply_to), ('artifact', artifact)]:
            if value is not None:
                inputs[name] = value if isinstance(value, dict) else reference(value)
        return self.apply('append', run, inputs)

    def finish(self, run, ident, content, *, artifact=None):
        inputs = dict(id=_name(ident), content=content)
        if artifact is not None:
            inputs['artifact'] = artifact if isinstance(artifact, dict) else reference(artifact)
        return self.apply('finish', run, inputs)

    def read_context(self, run, *, event=None, max_nodes=500, max_bytes=1024 * 1024):
        """Read all captured inputs, failing instead of silently truncating.

        Returns labelled arrays of MCP pages. Page boundaries and exact pinned
        references are preserved rather than reconstructed into a second model.
        The collection listing and every snapshot page count against the budget.
        """
        if max_nodes < 1 or max_bytes < 1:
            raise ValueError('context limits must be positive')
        root = run.rstrip('/')
        if event is not None:
            root += '/trace/' + _name(event)
        root += '/context'
        nodes = 0
        size = 0

        def pages(path, care):
            nonlocal nodes, size
            cursor = None
            seen = set()
            out = []
            while True:
                options = dict(limit=min(500, max(1, max_nodes - nodes)))
                if cursor is not None:
                    options['next'] = cursor
                page = self.read(path, care, **options)
                if 'error' in page:
                    raise Refused(page)
                nodes += int(page.get('nodes') or 1)
                size += len(json.dumps(page, ensure_ascii=False).encode())
                if nodes > max_nodes or size > max_bytes:
                    raise ContextLimit('complete context exceeds node or byte limit; increase the explicit budget')
                out.append(page)
                cursor = page.get('next')
                if not cursor:
                    return out
                marker = json.dumps(cursor, sort_keys=True)
                if marker in seen:
                    raise RuntimeError('MCP returned a repeated pagination cursor')
                seen.add(marker)
                if nodes >= max_nodes:
                    raise ContextLimit('context has more pages than the node budget permits')

        listing = pages(root, 'y')
        children = {}
        for page in listing:
            for child in page.get('children') or []:
                children[child['path']] = child
        captures = []
        for path in sorted(children):
            captures.append({'label': path.rsplit('/', 1)[-1], 'source': path,
                             'pages': pages('/x' + path, 'z')})
        return {'path': root, 'captures': captures, 'nodes': nodes, 'bytes': size}


def _contexts(values):
    result = {}
    for value in values:
        label, separator, path = value.partition('=')
        if not separator or not path:
            raise ValueError('--context must be NAME=ABSOLUTE_PATH_OR_PINNED_REFERENCE')
        label = _name(label)
        if label in result:
            raise ValueError('duplicate context label: ' + label)
        result[label] = reference(path, 'z')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='http://127.0.0.1:8131')
    parser.add_argument('--node', default='0x11')
    parser.add_argument('--timeout', type=float, default=120)
    commands = parser.add_subparsers(dest='command', required=True)
    opened = commands.add_parser('open', help='open document-local work with captured inputs')
    opened.add_argument('document')
    opened.add_argument('--id', required=True)
    opened.add_argument('--content', required=True)
    opened.add_argument('--parent')
    opened.add_argument('--procedure')
    opened.add_argument('--context', action='append', default=[], metavar='NAME=REFERENCE')
    appended = commands.add_parser('append', help='append a linked trace entry')
    appended.add_argument('run')
    appended.add_argument('--id', required=True)
    appended.add_argument('--kind', required=True, choices=['message', 'observation', 'tool-result', 'output'])
    appended.add_argument('--content', required=True)
    appended.add_argument('--reply-to')
    appended.add_argument('--artifact')
    appended.add_argument('--context', action='append', default=[], metavar='NAME=REFERENCE')
    finished = commands.add_parser('finish', help='finish only when captured dependencies are current')
    finished.add_argument('run')
    finished.add_argument('--id', required=True)
    finished.add_argument('--content', required=True)
    finished.add_argument('--artifact')
    context = commands.add_parser('context', help='read complete captured context within explicit limits')
    context.add_argument('run')
    context.add_argument('--event', help='read context captured by this trace entry')
    context.add_argument('--max-nodes', type=int, default=500)
    context.add_argument('--max-bytes', type=int, default=1024 * 1024)
    args = parser.parse_args(argv)
    client = Client(args.base, args.node, args.timeout)
    try:
        if args.command == 'open':
            result = client.open(args.document, args.id, args.content,
                                 context=_contexts(args.context), parent=args.parent, procedure=args.procedure)
        elif args.command == 'append':
            result = client.append(args.run, args.id, args.kind, args.content,
                                   context=_contexts(args.context), reply_to=args.reply_to, artifact=args.artifact)
        elif args.command == 'finish':
            result = client.finish(args.run, args.id, args.content, artifact=args.artifact)
        else:
            result = client.read_context(args.run, event=args.event,
                                         max_nodes=args.max_nodes, max_bytes=args.max_bytes)
    except (ValueError, Refused, ContextLimit, OSError, urllib.error.URLError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
