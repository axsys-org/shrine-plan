#!/usr/bin/env python3
"""Read-only debugger regression against an explicitly owned disposable runtime.

Never accepts a bare URL or a user snapshot. Start a fresh runtime with
debug-grove-runtime.py, then pass its manifest. Timings are observations, not
cross-machine pass thresholds; namespace mutation and contract drift are errors.
"""
import argparse
import concurrent.futures
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import socket
import statistics
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from namespace_identity import parse_node_identity


class Document(HTMLParser):
    def __init__(self, body):
        super().__init__()
        self.workspace, self.children, self.events = {}, [], []
        self.cases, self.case_links = {}, []
        self.descriptor, self.descriptor_text = None, []
        self.in_descriptor = False
        assert b'data-grove-contract="debugger/v1"' in body
        self.feed(body.decode())
        assert self.descriptor is not None, 'Missing Grove read descriptor'
        data = self.descriptor
        assert data['version'] == 1 and data['path'] == self.workspace['data-path']
        assert data['scope'] == self.workspace['data-scope']
        assert data['writable'] == (self.workspace['data-writable'] == 'true')
        collection = data['collection']
        assert collection['childCount'] == self.workspace['data-child-count']
        if self.workspace['data-slot-count']:
            assert collection['slotCount'] == self.workspace['data-slot-count']
        assert collection['epoch'] == (self.workspace.get('data-read-epoch') or None)
        self.children = [child['path'] for child in data['children']]
        assert len(data['previewSlots']) <= 3
        assert all(len(slot['text'].encode()) <= 180 for slot in data['previewSlots'])

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if attrs.get('id') == 'debug-workspace':
            self.workspace = attrs
        if tag == 'template' and attrs.get('id') == 'debug-read-descriptor':
            assert self.descriptor is None and not self.in_descriptor
            self.in_descriptor = True
        if tag == 'a' and 'debug-event' in attrs.get('class', '').split():
            self.events.append((attrs['data-reference'], attrs['href']))
        if tag == 'ui-accordion-item' and 'data-care' in attrs:
            self.cases[attrs['data-care']] = attrs['data-case-total']
        if tag == 'a' and 'wb-case-link' in attrs.get('class', '').split():
            self.case_links.append(attrs['href'])

    def handle_data(self, data):
        if self.in_descriptor:
            self.descriptor_text.append(data)

    def handle_endtag(self, tag):
        if tag == 'template' and self.in_descriptor:
            self.descriptor = json.loads(''.join(self.descriptor_text))
            self.in_descriptor = False


def check(manifest):
    runtime_path = Path(__file__).with_name('debug-grove-runtime.py')
    spec = importlib.util.spec_from_file_location('grove_runtime', runtime_path)
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    owned = runtime.owned(Path(manifest))
    _, node = parse_node_identity(owned['node'])
    authority = '/' + node
    local_key, system_key = 'v1/x:' + node[2:], 'v1/ts:737973'
    foreign = '0x02' if node != '0x02' else '0x03'
    hello = '/debug' + authority + '/hello'
    application = '/debug' + authority + '/gov/debug'
    assert owned['port'] not in (8138, 51571), 'Never profile a protected namespace'
    output = Path(tempfile.mkdtemp(prefix='read-regression-', dir=owned['work']))
    requests, checkpoints = [], []
    report = dict(runtime=owned['id'], origin=owned['origin'], requests=requests,
                  checkpoints=checkpoints, passed=False)

    def get(path, expected=200):
        start = time.perf_counter()
        try:
            response = urllib.request.urlopen(owned['origin'] + path, timeout=20)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            body = response.read()
            assert response.status == expected, (path[:300], response.status, body[:300])
            assert int(response.headers['Content-Length']) == len(body)
            if path.startswith('/debug-read/'):
                assert response.headers.get_content_type() == 'application/json'
                assert len(body) <= 131072
        requests.append(dict(path=path, status=response.status, bytes=len(body),
                             ms=round(1000 * (time.perf_counter() - start), 3)))
        return body

    def physical(path_key, collection='children', **options):
        return '/debug-read/physical?' + urllib.parse.urlencode(
            dict(pathKey=path_key, collection=collection, **options), safe='/:')

    def error(path, status, reason):
        assert json.loads(get(path, status)) == dict(version=1, error=reason)

    def checkpoint(label):
        data = json.loads(get('/debug-read/physical?pathKey=v1/x:' + node[2:] + '/ts:696f/ts:68747470&collection=children&limit=1'))
        point = dict(label=label, epoch=data['epoch'], retained=data['total'])
        checkpoints.append(point)
        assert not checkpoints[:-1] or (point['epoch'], point['retained']) == (
            checkpoints[0]['epoch'], checkpoints[0]['retained']), checkpoints

    def journal(limit=2, before=None, path=None):
        path = path or '/debug' + authority + '/log'
        query = dict(limit=limit, **({} if before is None else dict(before=before)))
        doc = Document(get(path + '?' + urllib.parse.urlencode(query)))
        data, prefix = doc.workspace, authority + '/log/'
        assert data['data-path'] == authority + '/log' and data['data-paging'] == 'journal'
        assert data['data-page-before'] == (before or '') and data['data-page-limit'] == str(limit)
        epoch, total = data['data-page-epoch'], data['data-child-count']
        assert epoch.isdecimal() and total.isdecimal() and epoch == checkpoints[0]['epoch']
        assert total == report.setdefault('journalTotal', total)
        assert len(doc.children) <= min(limit, int(total))
        assert all(child.startswith(prefix) and child[len(prefix):].isdecimal() for child in doc.children)
        keys = [int(child[len(prefix):]) for child in doc.children]
        assert keys == sorted(set(keys), reverse=True)
        assert all(key <= int(epoch) and (before is None or key < int(before)) for key in keys)
        assert doc.events == [(child, '/debug' + child) for child in doc.children]
        next_before = data['data-page-next-before']
        assert not next_before or (len(keys) == limit and next_before == str(keys[-1]))
        if before is None:
            assert len(keys) == min(limit, int(total))
            assert bool(next_before) == (int(total) > limit)
        return doc

    try:
        checkpoint('before')
        # Physical pages and scoped documents must agree on each authority's clock.
        authorities = {}
        for root, key in ((authority, local_key), ('/sys', system_key)):
            page = json.loads(get(physical(key, limit=1)))
            assert page['version'] == 1 and page['resolution'] == 'physical'
            assert page['pathKey'] == key and page['displayPath'] == root
            assert page['epoch'].isdecimal() and page['total'].isdecimal()
            assert page['collection'] == 'children' and page['limit'] == 1 and page['after'] is None
            assert len(page['entries']) <= 1 and page['complete'] is (page['next'] is None)
            assert page['next'] is None or page['next'] == page['entries'][-1]['key']
            doc = Document(get('/debug' + root + '?scope=workspace&epoch=' + page['epoch']))
            assert doc.workspace['data-path'] == root
            assert doc.workspace['data-read-epoch'] == page['epoch']
            assert doc.workspace['data-writable'] == ('true' if root == authority else 'false')
            assert all(child.startswith(root + '/') for child in doc.children)
            wrong_epoch = str(int(page['epoch']) + 1)
            error(physical(key, epoch=wrong_epoch), 409, 'epoch_conflict')
            error('/debug' + root + '?scope=workspace&epoch=' + wrong_epoch, 409, 'epoch_conflict')
            authorities[root] = page
        assert authorities[authority]['epoch'] == checkpoints[0]['epoch']
        for root, key, other in ((authority, local_key, '/sys'), ('/sys', system_key, authority)):
            if authorities[root]['epoch'] != authorities[other]['epoch']:
                error(physical(key, epoch=authorities[other]['epoch']), 409, 'epoch_conflict')
        report['authorityEpochs'] = {root: page['epoch'] for root, page in authorities.items()}
        composed = Document(get('/debug?scope=outline&epoch=0'))
        assert set(composed.children) == {'/sys', authority} and len(composed.children) == 2
        assert composed.workspace['data-read-epoch'] == '0'
        error(physical('v1'), 422, 'authority_required')
        error(physical('v1/x:' + foreign[2:]), 404, 'unknown_authority')
        error('/debug/' + foreign + '/log?scope=workspace', 404, 'unknown_authority')
        for name in ('x', 'o', 'h'):
            error(physical('v1/ts:' + name.encode().hex()), 422, 'derived_path')
        for path, status, reason in (('/' + foreign + '/hello', 404, 'unknown_authority'),
                                    ('/x/hello', 422, 'derived_path'),
                                    ('/o/hello', 422, 'derived_path'),
                                    ('/h/x/1/1/hello', 422, 'derived_path')):
            error('/debug-read/value?' + urllib.parse.urlencode(dict(
                path=path, slot='/sys/lede', epoch=checkpoints[0]['epoch'], offset=0, limit=1)), status, reason)
        # Keep both decoded identities at the 8192-byte budget, including other node widths.
        depth, remainder = divmod(8192 - len(local_key), 3)
        maximum = local_key + '/f:' * (depth - remainder) + '/rd:' * remainder
        assert len(maximum.encode()) == 8192
        error(physical(maximum, 'slots', epoch=checkpoints[0]['epoch'], after=maximum), 404, 'path_missing')
        report['maximumPhysicalMs'] = requests[-1]['ms']
        checkpoint('after-transport-edges')
        # Source history must never be presented as a derived output's history.
        source = Document(get(hello + '?scope=workspace'))
        assert int(source.cases['x']) >= 1 and source.case_links
        derived_target = '/h/x/1/2' + authority + '/hello'
        derived = Document(get('/debug' + derived_target + '?scope=workspace'))
        assert derived.workspace['data-path'] == derived_target
        assert derived.workspace['data-writable'] == 'false'
        assert derived.workspace['data-slot-count'] != '0', 'Historical record must still resolve'
        assert derived.cases == dict(x='', y='', z='') and not derived.case_links
        # Independently inspect a descendant within an exact historical frontier.
        parent = Document(get('/debug' + authority + '/app?scope=workspace'))
        assert int(parent.cases['y']) >= 1
        descendant_target = '/h/y/' + parent.cases['y'] + '/2' + authority + '/app/debug'
        descendant = Document(get('/debug' + descendant_target + '?scope=workspace'))
        assert descendant.workspace['data-path'] == descendant_target
        assert descendant.workspace['data-slot-count'] != '0'
        assert descendant.cases == dict(x='', y='', z='') and not descendant.case_links
        report['derivedHistoryChecked'] = [derived_target, descendant_target]
        checkpoint('after-derived-history')
        latest, first = journal(), journal(limit=1)
        assert first.children == latest.children[:1]
        if first.workspace['data-page-next-before']:
            older = journal(limit=1, before=first.workspace['data-page-next-before'])
            assert first.children + older.children == latest.children
            assert older.workspace['data-child-count'] == latest.workspace['data-child-count']
        else:
            assert first.children == latest.children
        assert not journal(before='0').children
        legacy = journal(path='/debug/log')
        assert (legacy.workspace, legacy.children) == (latest.workspace, latest.children)
        system_log = Document(get('/debug/sys/log?scope=workspace'))
        assert system_log.workspace['data-path'] == '/sys/log' and not system_log.workspace['data-paging']
        get('/debug/sys/log?limit=1', 400)
        get('/debug' + authority + '/log?before=01', 400)
        report['journalRowsChecked'] = len(latest.children)
        for _ in range(21):
            get(hello)
        checkpoint('after-documents')
        for path in (application, '/debug', '/debug' + authority + '/app', '/debug/sys'):
            for scope in ('', 'workspace', 'outline', 'preview'):
                body = get(path + ('?scope=' + scope if scope else ''))
                assert b'data-grove-contract="debugger/v1"' in body
                if scope:
                    assert b'<script' not in body and b'id="debug-sidebar"' not in body
                if scope != 'preview':
                    assert b'id="debug-path-preview"' not in body
        # A cursor never silently traverses a different snapshot.
        get('/debug' + authority + '?scope=workspace&epoch=0', 409)
        get('/debug?scope=workspace&epoch=0')
        get('/debug?scope=invalid', 400)
        checkpoint('before-disconnect')
        with socket.create_connection(('127.0.0.1', owned['port']), timeout=3) as connection:
            connection.sendall(('GET ' + application + '?scope=workspace HTTP/1.0\r\nHost: localhost\r\n\r\n').encode())
            time.sleep(.02)
        # The following read is a mailbox barrier, not a claim of preemption.
        checkpoint('after-disconnect')
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(lambda _: get(application + '?scope=workspace'), range(3)))
        checkpoint('final')
        repeated = journal()
        assert (repeated.workspace, repeated.children) == (latest.workspace, latest.children)
        for root, key in ((authority, local_key), ('/sys', system_key)):
            assert json.loads(get(physical(key, limit=1))) == authorities[root]
        report['helloMedianMs'] = statistics.median(
            row['ms'] for row in requests if row['path'] == hello)
        report['passed'] = True
    finally:
        (output / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(dict(output=str(output), passed=report['passed'],
                              requests=len(requests), checkpoints=checkpoints,
                              helloMedianMs=report.get('helloMedianMs'))), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest')
    check(parser.parse_args().manifest)
