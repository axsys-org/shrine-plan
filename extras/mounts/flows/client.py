"""Import source snapshots and invoke the native Semidoc flow harness.

Python handles files and the existing MCP transport. Compilation, composition,
preview, conflict checks and document writes run in native Foil.
"""
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import runpy
import uuid
from urllib.parse import quote
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
_transport = runpy.run_path(str(HERE.parent / 'cooperate' / 'client.py'))
Client = _transport['Client']
reference = _transport['reference']


class SourceForm(HTMLParser):
    """The existing Nenex source form carries the complete escaped source."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.active = False
        self.found = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == 'textarea' and dict(attrs).get('id') == 'page-source':
            self.active = self.found = True

    def handle_endtag(self, tag):
        if tag == 'textarea':
            self.active = False

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)


def validate_bundle(bundle):
    """Accept a replay only when the source bytes still match its captured hashes."""
    sources = bundle['sources']
    if not isinstance(sources, dict) or not 1 <= len(sources) <= 64:
        raise ValueError('bundle must contain between 1 and 64 named sources')
    for name, source in sources.items():
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', name):
            raise ValueError('invalid source name: ' + name)
        if set(source) != {'location', 'title', 'digest', 'format', 'content'} or not all(
                isinstance(value, str) for value in source.values()):
            raise ValueError('incomplete source envelope: ' + name)
        raw = source['content'].encode('utf-8')
        if not source['location'] or not 0 < len(raw) <= 131072:
            raise ValueError('invalid source size or location: ' + name)
        if hashlib.sha256(raw).hexdigest() != source['digest']:
            raise ValueError('source digest mismatch: ' + name)
    encoded = json.dumps(sources, ensure_ascii=False, sort_keys=True).encode('utf-8')
    if len(encoded) > 1500000:
        raise ValueError('source inventory exceeds the client materialization budget')
    if hashlib.sha256(encoded).hexdigest() != bundle['digest']:
        raise ValueError('bundle digest mismatch')
    return bundle


def prepare(repo=REPO, manifest=HERE / 'sources.json'):
    """Read the entire declared inventory before making any remote changes."""
    repo = Path(repo).resolve()
    entries = json.loads(Path(manifest).read_text(encoding='utf-8'))
    if not isinstance(entries, dict) or not 1 <= len(entries) <= 64:
        raise ValueError('manifest must contain between 1 and 64 named sources')
    sources = {}
    for name, entry in sorted(entries.items()):
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', name):
            raise ValueError('invalid source name: ' + name)
        path = (repo / entry['path']).resolve()
        if not path.is_relative_to(repo):
            raise ValueError('source escapes repository: ' + entry['path'])
        raw = path.read_bytes()
        if not 0 < len(raw) <= 131072:
            raise ValueError('source must contain 1..131072 bytes: ' + entry['path'])
        sources[name] = dict(location=entry['path'], title=entry.get('title', name),
                             digest=hashlib.sha256(raw).hexdigest(),
                             format=path.suffix.lstrip('.') or 'text',
                             content=raw.decode('utf-8'))
    encoded = json.dumps(sources, ensure_ascii=False, sort_keys=True).encode('utf-8')
    if len(encoded) > 1500000:
        raise ValueError('source inventory exceeds the client materialization budget')
    return validate_bundle({'digest': hashlib.sha256(encoded).hexdigest(), 'sources': sources})


class FlowClient(Client):
    def __init__(self, base, node='0x11', timeout=180):
        if not re.fullmatch(r'0x[0-9a-f]+', node):
            raise ValueError('node must be a hexadecimal publisher identity')
        super().__init__(base, node, timeout)
        self.publisher = '/' + node + '/gov/flows'

    def import_sources(self, bundle):
        validate_bundle(bundle)
        root = '/' + self.node + '/user/flow_sources/s_' + bundle['digest']
        for name, source in bundle['sources'].items():
            self.apply('import_source', root + '/' + name, source)
        return root

    def author(self, target, source, *, expected=0):
        return self.apply('author', target, {'source': source, 'expected': expected})

    def publish(self, author, name):
        current = self.read(author)
        if not current.get('exists'):
            raise ValueError('authoring document does not exist: ' + author)
        version = int(current['reference'].split('/')[3])
        self.apply('publish', author, {'id': name, 'expected': version})
        return author + '/flows/' + name

    def preview(self, definition, destination, bindings, *, ident=None, writer=None):
        ident = ident or 'run_' + uuid.uuid4().hex
        inputs = {'id': ident, 'destination': {'type': 'path', 'value': destination},
                  'writer': reference(writer or self.publisher + '/nenex')}
        inputs.update({'input/' + name: value if isinstance(value, dict) else reference(value, 'z')
                       for name, value in bindings.items()})
        self.apply('preview', definition, inputs)
        return definition + '/work/' + ident

    def commit(self, run):
        return self.apply('commit', run, {})

    def observe(self, feed, source):
        return self.apply('observe', feed, {'source': reference(source, 'z')})

    def follow(self, controller, definition, destination, bindings, *, writer=None, provider=None):
        inputs = {'definition': reference(definition),
                  'destination': {'type': 'path', 'value': destination},
                  'writer': reference(writer or self.publisher + '/nenex')}
        if provider:
            inputs['provider'] = reference(provider)
        inputs.update({'input/' + name: value if isinstance(value, dict) else reference(value, 'z')
                       for name, value in bindings.items()})
        self.apply('follow', controller, inputs)
        return controller

    def set_enabled(self, controller, enabled):
        return self.apply('set_enabled', controller, {'enabled': enabled})

    def source_failed(self, feed, reason):
        return self.apply('source_failed', feed, {'reason': reason[:1500]})

    def submit_revision(self, request, source, note, expected=None):
        if expected is None:
            draft = self.read(request + '/draft')
            expected = int(draft['reference'].split('/')[3])
        return self.apply('submit_revision', request,
                          {'source': source, 'note': note, 'expected': expected})

    def source(self, author):
        # MCP renders text above 8 KiB as a reference. The normal source editor
        # supplies the whole source in one response, without a debugger mount.
        if not author.startswith('/' + self.node + '/'):
            raise ValueError('source export must address this local publisher')
        with urlopen(self.base + '/nenex?path=' + quote(author, safe=''), timeout=self.timeout) as response:
            html = response.read(2097153)
        if len(html) > 2097152:
            raise ValueError('source form exceeds the export limit')
        form = SourceForm()
        form.feed(html.decode('utf-8'))
        if not form.found or form.active:
            raise ValueError('the selected page has no complete source form')
        return ''.join(form.parts)


def save_bundle(path, bundle):
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def input_bindings(parser, items):
    bindings = {}
    for item in items:
        name, sep, value = item.partition('=')
        if not sep or not value or name in bindings:
            parser.error('each input must be a unique NAME=PATH')
        bindings[name] = value
    return bindings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='http://127.0.0.1:8138')
    parser.add_argument('--node', default='0x11')
    sub = parser.add_subparsers(dest='command', required=True)
    inventory = sub.add_parser('prepare', help='validate local inputs and save a replayable source bundle')
    inventory.add_argument('--repo', type=Path, default=REPO)
    inventory.add_argument('--manifest', type=Path, default=HERE / 'sources.json')
    inventory.add_argument('--output', type=Path, required=True)
    build = sub.add_parser('handbook', help='publish the authored flow and preview, commit or maintain the handbook')
    build.add_argument('--repo', type=Path, default=REPO)
    build.add_argument('--manifest', type=Path, default=HERE / 'sources.json')
    build.add_argument('--source', type=Path, default=HERE / 'handbook.semidoc')
    build.add_argument('--author', help='existing authoring page wins; source file seeds only a missing page')
    build.add_argument('--destination')
    build.add_argument('--commit', action='store_true')
    build.add_argument('--id', help='explicit retry identity for this preview')
    build.add_argument('--bundle', type=Path, help='save the exact imported sources for replay')
    build.add_argument('--from-bundle', type=Path, help='replay captured sources instead of reading the filesystem')
    build.add_argument('--maintain', action='store_true', help='attach a native maintenance hand')
    build.add_argument('--feed')
    build.add_argument('--controller')
    build.add_argument('--provider', default='codex',
                       help='native provider path, codex (default), or manual')
    submit = sub.add_parser('submit-revision', help='complete a native concept revision')
    submit.add_argument('request')
    submit.add_argument('--source', type=Path, required=True,
                        help='one Semidoc section, or an exported native draft')
    submit.add_argument('--note', required=True, help='what changed and the evidence used')
    submit.add_argument('--expected', type=int, help='draft version captured before editing')
    publish = sub.add_parser('publish')
    publish.add_argument('author')
    publish.add_argument('name')
    preview = sub.add_parser('preview')
    preview.add_argument('definition')
    preview.add_argument('destination')
    preview.add_argument('--input', action='append', default=[], metavar='NAME=PATH')
    preview.add_argument('--id')
    commit = sub.add_parser('commit')
    commit.add_argument('run')
    export = sub.add_parser('export', help='save the canonical namespace Semidoc source before stopping a development world')
    export.add_argument('author')
    export.add_argument('output', type=Path)
    follow = sub.add_parser('follow', help='attach a reusable native maintenance hand')
    follow.add_argument('controller')
    follow.add_argument('definition')
    follow.add_argument('destination')
    follow.add_argument('--input', action='append', default=[], metavar='NAME=PATH')
    follow.add_argument('--provider', help='native provider path; omitted for manual completion')
    observe = sub.add_parser('observe', help='publish one complete source collection to a live feed')
    observe.add_argument('feed')
    observe.add_argument('source')
    for name in ('pause', 'resume', 'detach'):
        sub.add_parser(name).add_argument('controller')
    args = parser.parse_args()
    if args.command == 'handbook':
        args.maintain = args.maintain or not args.commit
        if args.maintain and args.commit:
            parser.error('choose --maintain or --commit')
    if args.command == 'prepare':
        bundle = prepare(args.repo, args.manifest)
        args.output.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'bundle': str(args.output.resolve()), 'digest': bundle['digest'],
                          'sources': len(bundle['sources'])}))
        return
    client = FlowClient(args.base, args.node)
    if args.command == 'publish':
        print(client.publish(args.author, args.name))
    elif args.command == 'preview':
        bindings = input_bindings(parser, args.input)
        print(client.preview(args.definition, args.destination, bindings, ident=args.id))
    elif args.command == 'commit':
        print(json.dumps(client.commit(args.run)))
    elif args.command == 'export':
        args.output.write_text(client.source(args.author), encoding='utf-8')
        print(str(args.output.resolve()))
    elif args.command == 'submit-revision':
        print(json.dumps(client.submit_revision(args.request, args.source.read_text(),
                                                args.note, args.expected)))
    elif args.command == 'follow':
        print(client.follow(args.controller, args.definition, args.destination, input_bindings(parser, args.input),
                            provider=args.provider))
    elif args.command == 'observe':
        print(json.dumps(client.observe(args.feed, args.source)))
    elif args.command in ('pause', 'resume'):
        print(json.dumps(client.set_enabled(args.controller, args.command == 'resume')))
    elif args.command == 'detach':
        print(json.dumps(client.apply('detach', args.controller, {})))
    else:
        bundle = (validate_bundle(json.loads(args.from_bundle.read_text(encoding='utf-8')))
                  if args.from_bundle else prepare(args.repo, args.manifest))
        if args.bundle:
            args.bundle.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding='utf-8')
        author = args.author or '/' + args.node + '/app/nenex/w/handbook_flow'
        destination = args.destination or '/' + args.node + '/app/nenex/w/handbook'
        # Readiness before imports, and never overwrite an existing authored page.
        if not client.read(client.publisher + '/publish').get('exists'):
            raise ValueError('the server needs the flows mount')
        if not client.read(author).get('exists'):
            source = args.source.read_text(encoding='utf-8').replace('/0x11/gov/flows/', client.publisher + '/')
            client.author(author, source)
        sources = client.import_sources(bundle)
        definition = client.publish(author, 'handbook')
        if args.maintain:
            feed = args.feed or '/' + args.node + '/user/flow_sources/handbook_live'
            controller = args.controller or author + '/work/maintenance'
            client.observe(feed, sources)
            provider = ('/' + args.node + '/io/codex/work_provider' if args.provider == 'codex'
                        else None if args.provider == 'manual' else args.provider)
            client.follow(controller, definition, destination, {'sources': '/x' + feed}, provider=provider)
            print(json.dumps({'controller': controller, 'feed': feed,
                              'reader': args.base + '/nenex?path=' + quote(destination, safe=''),
                              'status': client.read(controller).get('properties', {}).get('/sys/content')}, indent=2), flush=True)
            return
        run = client.preview(definition, destination, {'sources': sources}, ident=args.id)
        if args.commit:
            client.commit(run)
        print(json.dumps({'author': author, 'definition': definition, 'sources': sources,
                          'run': run, 'preview': '/x' + run + '/result',
                          'destination': destination, 'committed': args.commit,
                          'reader': args.base + '/nenex?path=' + quote(destination, safe=''),
                          'editor': args.base + '/nenex?path=' + quote(author, safe='') + '#source'}, indent=2))


if __name__ == '__main__':
    main()
