#!/usr/bin/env python3
"""Record or compare a read-only view around a manual kept-world stop/resume."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from quotes import World, BASE, VIEWS, verify

HERE = Path(__file__).resolve().parent
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('phase', choices=['before', 'after'])
p.add_argument('--server', default='http://127.0.0.1:8192')
p.add_argument('--output', type=Path, default=HERE / 'run/lifecycle')
a = p.parse_args()
w = World(a.server, a.output / a.phase)


def get(route, values, post=False):
    encoded = urlencode(values)
    req = Request(a.server + route + ('' if post else '?' + encoded),
                  data=encoded.encode() if post else None)
    with urlopen(req, timeout=240) as response:
        return json.load(response)


render = get('/goo/render', dict(target='/0x11/app/branchmap/exchange',
    slot='/sys/slot/content', width=900, textScale=1, direction='ltr'), True)
assert render['ok']
state = dict(exchange_text=[n.get('payload', '') for n in render['display']['nodes']],
             exchange_snapshot=render['snapshot'], quote=w.read('/x' + VIEWS + '/quote', 'y'),
             historical_offer=w.read('/h/x/1/5' + BASE + '/offers/fed_yes'),
             account_collection=get('/goo/source', dict(target='/x/0x11/app/branchmap/accounts', axis='z')),
             account_child=get('/goo/source', dict(target='/x/0x11/app/branchmap/accounts/1', axis='z')),
             account_child_read=w.read('/x/0x11/app/branchmap/accounts/1'))
(a.output / (a.phase + '.json')).write_text(json.dumps(state, indent=2) + '\n')
verify(w)
if a.phase == 'after':
    before = json.loads((a.output / 'before.json').read_text())
    w.expect('exchange text survives resume', state['exchange_text'], before['exchange_text'])
    w.expect('quote rows survive resume', state['quote']['children'], before['quote']['children'])
    w.expect('original source history survives resume', state['historical_offer'], before['historical_offer'])
    w.expect('resumed exchange retains Carol account', any('carol: 100.000000' in x for x in state['exchange_text']), True)
print('PASS:', a.phase, 'snapshot and quote checks')
