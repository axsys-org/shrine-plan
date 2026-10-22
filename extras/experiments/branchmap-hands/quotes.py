#!/usr/bin/env python3
"""Seed and test a quote graph through MCP; all quote arithmetic runs in cells.

This is a separate quote-design experiment, not a second copy of the exchange
ledger and not an order-execution service. Python supplies observations, inputs,
and assertions. It never calculates a quote for the running application.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
BASE = '/0x11/user/branchmap_quotes'
VIEWS = BASE + '/views'
WHO = 'quote_probe'


class World:
    def __init__(self, server, output):
        self.server, self.output = server, output
        output.mkdir(parents=True, exist_ok=True)
        self.checks = []

    def call(self, name, allow_refusal=False, **arguments):
        envelope = dict(jsonrpc='2.0', id=time.time_ns(), method='tools/call',
                        params=dict(name='mcp/' + name, arguments=arguments))
        started = time.monotonic()
        with urlopen(Request(self.server + '/mcp', json.dumps(envelope).encode(),
                             {'Content-Type': 'application/json'}), timeout=240) as response:
            reply = json.load(response)
        with (self.output / 'calls.jsonl').open('a') as out:
            out.write(json.dumps(dict(request=envelope, response=reply,
                                     seconds=time.monotonic() - started)) + '\n')
        result = reply.get('result', {})
        expected_refusal = allow_refusal and result.get('structuredContent', {}).get('refused')
        if 'error' in reply or (result.get('isError') and not expected_refusal):
            raise RuntimeError(reply)
        return result['structuredContent']

    def read(self, path, care='x', **kwargs):
        return self.call('read', path=path, care=care, **kwargs)

    def write(self, records, **kwargs):
        return self.call('write', records=records, who=WHO, **kwargs)

    def expect(self, label, got, wanted):
        self.checks.append(dict(check=label, actual=got, expected=wanted, passed=got == wanted))
        self.save()
        assert got == wanted, (label, got, wanted)
        print('PASS:', label, flush=True)

    def save(self):
        (self.output / 'checks.json').write_text(json.dumps(self.checks, indent=2) + '\n')


def record(path, **slots):
    return dict(path=path, slots=slots)


def live(path, care='y'):
    return dict(type='reference', path=path, care=care, case=0)


def fields(tree):
    return {row['path'].rsplit('/', 1)[-1]: row.get('properties', {}) for row in tree.get('children', [])}


def seed(w):
    if w.read(BASE)['exists']:
        raise SystemExit('Quote namespace already exists. Use a fresh world or --verify; never silently reseed.')
    sample = json.loads((HERE.parent / 'branchmap/data/sample.json').read_text())
    # Select by source ID, not sample ordering; this is the original 0.14 snapshot.
    first = next(s for s in sample if s['market']['id'] == 'OqEUCA9tCN')
    raw = HERE.parent / 'branchmap/data/raw/OqEUCA9tCN.json'
    assert hashlib.sha256(raw.read_bytes()).hexdigest() == first['raw_sha256']
    observed_price = round(first['market']['probability'] * 1_000_000)
    records = [record(BASE, notes='Independent local quote scenario; no execution or external orders'),
               record(BASE + '/offers'), record(BASE + '/accounts'), record(BASE + '/requests'), record(VIEWS),
               record(BASE + '/sources'),
               record(BASE + '/sources/fed', url=first['source_api'], sha256=first['raw_sha256'], fetched=first['fetched_at']),
               record(BASE + '/offers/fed_yes', price_micros=observed_price, inventory=100, closed=False,
                      source=live(BASE + '/sources/fed', 'x')),
               record(BASE + '/offers/joint', inventory=100, closed=False,
                      notes='No observed joint quote; absence is intentional'),
               record(BASE + '/accounts/alice', cash_micros=100_000_000),
               record(BASE + '/accounts/poor', cash_micros=0)]
    for name, quantity, account, offer in [('valid', 10, 'alice', 'fed_yes'),
            ('too_large', 1000, 'alice', 'fed_yes'), ('no_cash', 1, 'poor', 'fed_yes'),
            ('zero', 0, 'alice', 'fed_yes'), ('fractional', 1.5, 'alice', 'fed_yes'),
            ('unquoted', 10, 'alice', 'joint')]:
        records.append(record(BASE + '/requests/' + name, quantity=quantity,
                              account=live(BASE + '/accounts/' + account, 'x'),
                              offer=live(BASE + '/offers/' + offer, 'x')))
    w.write(records)
    # Expectations are independent input records, created before reading the graph.
    qa = '/0x11/agent/' + WHO + '/qa'
    w.write([record(qa), record(qa + '/expect/valid'), record(qa + '/expect/valid/valid', cost_micros=1_400_000, remaining_micros=98_600_000)])
    names = ['follow', 'rename', 'each', 'where', 'validate', 'select', 'diff']
    stdlib = {name: dict(type='reference', value=w.read('/0x11/weft/stdlib/' + name)['reference']) for name in names}
    cells = []

    def cell(name, formula, source, **settings):
        cells.append(record(VIEWS + '/' + name, **{'sys/weft': stdlib[formula], 'sys/tack': live(source)}, **settings))

    cell('offered', 'follow', BASE + '/requests', slot='/offer', into='/offer', table=live(BASE + '/offers'))
    cell('funded', 'follow', '/x' + VIEWS + '/offered', slot='/account', into='/account', table=live(BASE + '/accounts'))
    source = '/x' + VIEWS + '/funded'
    for name, before, after in [('price', '/offer/price_micros', '/price_micros'),
                                ('stock', '/offer/inventory', '/inventory'),
                                ('open', '/offer/closed', '/closed'),
                                ('cash', '/account/cash_micros', '/cash_micros')]:
        cell(name, 'rename', source, **{'from': before, 'to': after})
        source = '/x' + VIEWS + '/' + name
    cell('cost', 'each', source, expr='quantity * price_micros', into='/cost_micros')
    cell('quote', 'each', '/x' + VIEWS + '/cost', expr='cash_micros - cost_micros', into='/remaining_micros')
    rule = ('quantity > 0 and quantity = round(quantity, 0) and quantity <= inventory '
            'and price_micros > 0 and price_micros < 1000000 and not closed and remaining_micros >= 0')
    cell('eligible', 'where', '/x' + VIEWS + '/quote', expr=rule)
    cell('rejected', 'validate', '/x' + VIEWS + '/quote', expr=rule)
    cell('amounts', 'select', '/x' + VIEWS + '/eligible', slots='/cost_micros /remaining_micros')
    cells.append(record(qa + '/check/valid', **{'sys/weft': stdlib['diff'],
        'sys/tack': live(qa + '/expect/valid'), 'other': live('/x' + VIEWS + '/amounts')}))
    w.write(cells)


def verify(w):
    quote = w.read('/x' + VIEWS + '/quote', 'y')
    rows = fields(quote)
    w.expect('ten shares cost 1.4 TOY', rows['valid'].get('/cost_micros'), '1400000')
    w.expect('quote leaves 98.6 TOY', rows['valid'].get('/remaining_micros'), '98600000')
    w.expect('negative remainder stays signed', rows['no_cash'].get('/remaining_micros'), '-140000')
    w.expect('only valid request is eligible', sorted(fields(w.read('/x' + VIEWS + '/eligible', 'y'))), ['valid'])
    w.expect('invalid and missing-price requests rejected', sorted(fields(w.read('/x' + VIEWS + '/rejected', 'y'))),
             ['fractional', 'no_cash', 'too_large', 'unquoted', 'zero'])
    w.expect('unquoted conjunction has no invented cost', '/cost_micros' in rows['unquoted'], False)
    context = w.read('/c/x' + VIEWS + '/cost').get('properties', {})
    w.expect('missing joint price is exposed as a hole', any(k.startswith('/sys/view/hole/') for k in context), True)
    qa = w.read('/x/0x11/agent/' + WHO + '/qa/check/valid').get('properties', {})
    w.expect('live expectation diff agrees', [qa.get('/added'), qa.get('/removed'), qa.get('/changed')], ['0', '0', '0'])
    (w.output / 'quote.json').write_text(json.dumps(quote, indent=2) + '\n')


def probe(w):
    offer = BASE + '/offers/fed_yes'
    before = w.read(offer)
    old_quote = w.read('/x' + VIEWS + '/quote', 'y')
    old_reference = old_quote['reference']
    w.write([dict(path=offer, action='poke', slots=dict(price_micros=200_000), if_case=int(before['reference'].split('/')[3]))])
    changed = w.read('/x' + VIEWS + '/quote', 'y')
    w.expect('price update traverses both joins and arithmetic', fields(changed)['valid'].get('/cost_micros'), '2000000')
    old_read = w.read(old_reference)
    (w.output / 'derived-identity.json').write_text(json.dumps(dict(before=old_quote, after=changed, old_reference_read=old_read), indent=2) + '\n')
    # The documented contract explicitly refuses a pinned read of a live cell.
    w.expect('old derived reference is unavailable, not a historical quote', old_read['exists'], False)
    stale = w.write([dict(path=offer, action='poke', slots=dict(price_micros=999_999), if_case=int(before['reference'].split('/')[3])),
                     record(BASE + '/stale_marker', value=1)], allow_refusal=True)
    w.expect('stale batch refused', stale['refused'], True)
    w.expect('stale batch has no partial marker', w.read(BASE + '/stale_marker')['exists'], False)
    w.write([dict(path=offer, **{'from': before['reference']})])
    verify(w)
    pinned = w.read(BASE + '/offers', 'y')['reference_y']
    frozen = w.read('/0x11/weft/stdlib/follow')['reference']
    w.write([record(VIEWS + '/pinned_offer', **{'sys/weft': dict(type='reference', value=frozen),
       'sys/tack': live(BASE + '/requests'), 'slot': '/offer', 'into': '/offer',
       'table': dict(type='reference', value=pinned)})])
    w.write([dict(path=offer, action='poke', slots=dict(price_micros=200_000))])
    w.expect('explicitly pinned secondary input stays at old price',
             fields(w.read('/x' + VIEWS + '/pinned_offer', 'y'))['valid'].get('/offer/price_micros'), '140000')
    w.write([dict(path=offer, **{'from': before['reference']})])
    refs = w.read(BASE, 'z', referencing=offer)
    (w.output / 'referencing.json').write_text(json.dumps(refs, indent=2) + '\n')
    w.expect('backlink discovery includes the valid request offer slot',
             any(m['path'] == BASE + '/requests/valid' and m['slot'] == '/offer' for m in refs['matches']), True)
    bad = w.call('read', path=BASE + '/requests', formula='each', settings=dict(expr='quantity / 0', into='/broken'))
    w.expect('division by zero returns a formula fault', '/sys/view/fault' in bad.get('context', {}), True)
    w.expect('world remains responsive after formula fault', w.read(BASE)['exists'], True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--server', default='http://127.0.0.1:8192')
    p.add_argument('--verify', action='store_true', help='Read-only verification, including after restart')
    p.add_argument('--output', type=Path, default=HERE / 'run/quote-check')
    args = p.parse_args()
    w = World(args.server, args.output)
    if not args.verify:
        seed(w)
    verify(w)
    if not args.verify:
        probe(w)
    print('All', len(w.checks), 'checks passed; receipts:', args.output)


if __name__ == '__main__':
    main()
