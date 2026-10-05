#!/usr/bin/env python3
"""Exercise native arrangement identities, content checks and undo in a new world.

No model fixtures, browser implementation, or independent type checker. Uses a
named disposable drop-fit world, and leaves receipts for diagnosis.
"""
import argparse
import json
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world', type=Path, required=True)
    parser.add_argument('--port', type=int, required=True)
    args = parser.parse_args()
    world = args.world.resolve()
    if not world.name.startswith('grove-drop-fit-'):
        raise SystemExit('Use a disposable grove-drop-fit world.')
    authority = (world / 'src/medium-authority').read_text()
    checks = []

    def call(operation, body, event=None):
        data = urllib.parse.urlencode(dict(credential=authority, principal='administrator',
            operation=operation, expected='0', event=event or uuid.uuid4().hex,
            body=json.dumps(body, ensure_ascii=False))).encode()
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{args.port}/medium-native', data, timeout=120) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    def check(name, condition, detail=None):
        checks.append(dict(name=name, passed=bool(condition), detail=detail))
        print(('PASS ' if condition else 'FAIL ') + name, flush=True)
        if not condition:
            raise AssertionError(detail or name)

    def block(id, text):
        return dict(id=id, kind='card', parent='', revision=1,
                    rect=dict(x=16,y=16,w=240,h=120),
                    content=[dict(id=id+'-text', kind='text', text=text)])

    try:
        code, state = call('fit/read', {})
        check('read native arrangement', code == 200, state)
        check('test starts empty', state['blocks'] == [])
        a, b = block('a','Fix brakes · Sam · Fri'), block('b','New chain · Ana · Mon')
        event = uuid.uuid4().hex
        request = dict(block=a, expected=None)
        code, first = call('fit/block', request, event)
        check('first block is native content', code == 200 and first['blocks'][0] == a, first)
        code, duplicate = call('fit/block', request, event)
        check('delivery replay is idempotent', code == 200 and duplicate == first, duplicate)
        code, _ = call('fit/block', dict(block=b, expected=None), event)
        check('event identity cannot acquire another meaning', code == 409)
        code, _ = call('fit/block', dict(block=b, expected=None))
        check('second block stored', code == 200)
        revised = {**a, 'revision':2, 'rect':dict(x=320,y=16,w=240,h=120)}
        change = uuid.uuid4().hex
        code, current = call('fit/block', dict(block=revised, expected=1), change)
        check('unrelated block does not invalidate draft', code == 200, current)
        code, _ = call('fit/block', dict(block=revised, expected=1))
        check('real target conflict is rejected', code == 409)
        check('content survives movement byte for byte', current['blocks'][0]['content'] == a['content'])
        code, undone = call('fit/undo', dict(event=change))
        check('undo restores original geometry and content', code == 200 and undone['blocks'] == [a,b], undone)
        rev = undone['revision']
        code, _ = call('fit/prepare', dict(revision=rev,reading=dict(content=['a-text'],unplaced=[])))
        check('fit cannot lose supplied content', code == 422)
        code, _ = call('fit/prepare', dict(revision=rev,reading=dict(content=['a-text','b-text'],unplaced=['a-text'])))
        check('fit cannot duplicate content', code == 422)
        code, _ = call('fit/prepare', dict(revision=rev,reading=dict(content=['a-text','invented'],unplaced=[])))
        check('fit cannot invent content identities', code == 422)
        code, proposal = call('fit/prepare', dict(revision=rev,reading=dict(content=['a-text'],unplaced=['b-text'])))
        check('explicit unplaced content survives a proposal', code == 200 and proposal['state']=='proposed', proposal)
        code, after = call('fit/read', {})
        check('proposal does not activate or alter content', code == 200 and after == undone)
        text = dict(t='Text')
        for source, target, expected in [('out','in','bind'),('event','intent','bind'),('in','out','hole')]:
            code, result = call('fit/check-wire', dict(
                **{'from':dict(dir=source,type=text)},to=dict(dir=target,type=text)))
            check(source+' → '+target+' has a defined result', code == 200 and result['r']==expected,result)
        code, result = call('fit/check-wire', {'from':dict(dir='out',type={}), 'to':dict(dir='in',type={})})
        check('malformed shapes do not bind', code == 200 and result['r']=='hole',result)
    finally:
        (world/'fit-native-checks.json').write_text(json.dumps(checks,indent=2)+'\n')


if __name__ == '__main__':
    main()
