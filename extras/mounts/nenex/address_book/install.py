#!/usr/bin/env python3
"""Install/rehearse the address recipe through the existing namespace transport."""
import argparse
import json
from pathlib import Path
import runpy
import time
from model import projections, seed, slot, path

CLIENT = Path(__file__).resolve().parents[2] / 'cooperate/client.py'


def check(c, formulas):
    root = '/0x11/agent/nenex_assistant/address_check_' + str(time.time_ns())
    crm = root + '/crm'
    contacts = [{'path': crm + '/contacts/c' + str(i), 'properties': {'/name': 'Test person ' + str(i)}} for i in range(10)]
    records = [{'path': x['path'], 'slots': {'/name': x['properties']['/name'], '/untouched': 'keep'}} for x in contacts]
    directory = root + '/directory'
    data, links = seed(directory, crm, contacts, root + '/evidence')
    cells, outputs = projections(root + '/views', crm + '/contacts', directory, links, formulas)
    c.tool('write', records=records + data + cells, who='nenex_assistant')
    reads = c.tool('read', reads=[{'path': outputs['contacts'], 'care': 'y'},
                                {'path': directory + '/addresses/demo_office_1', 'care': 'x'}])['answers']
    rows = reads[0]['children']
    assert len(rows) == 10
    assert sum(slot('contact_address_label') in x['properties'] for x in rows) == 9
    assert all(x['properties']['/untouched'] == 'keep' for x in rows)
    assert 'Suite 100' in rows[0]['properties'][slot('contact_address_label')]
    old_pin = reads[1]['reference']
    # A change to a shared address must affect exactly its three linked contacts.
    edited = c.tool('write', records=[{'path': directory + '/addresses/demo_office_1', 'action': 'poke',
                    'slots': {slot('address_postal_code'): '00501', slot('address_unit'): 'Suite 200'}}],
                    who='nenex_assistant', then=[{'path': outputs['contacts'], 'care': 'y'},
                    {'path': old_pin, 'care': 'x'}, {'path': root + '/evidence/office_1', 'care': 'x'}])
    rows = edited['then'][outputs['contacts']]['children']
    assert sum('00501' in x['properties'].get(slot('contact_address_label'), '') for x in rows) == 3
    assert all('Suite 200' in x['properties'][slot('contact_address_label')] for x in rows[:3])
    assert edited['then'][old_pin]['properties'][slot('address_postal_code')] == '78701'
    assert edited['then'][root + '/evidence/office_1']['properties']['/unit'] == 'Suite 100'
    # A dangling association must not fabricate a contact address.
    association = links + '/c0_work'
    out = c.tool('write', records=[{'path': association, 'action': 'poke', 'slots': {
        slot('association_address'): path(directory + '/addresses/missing')}}], who='nenex_assistant',
        then=[{'path': outputs['contacts'], 'care': 'y'}])
    assert slot('contact_address_label') not in out['then'][outputs['contacts']]['children'][0]['properties']
    # Reads of projections must not be writable.
    try:
        c.tool('write', records=[{'path': outputs['contacts'], 'slots': {'bad': True}}], who='nenex_assistant')
    except RuntimeError:
        pass
    else:
        raise AssertionError('Derived write unexpectedly admitted')
    c.tool('write', records=[{'path': root, 'action': 'cull'}], who='nenex_assistant')
    print('PASS: shared-address propagation, optional/missing links, text postal codes, pinned history, preserved evidence/facets, read-only projection', flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', default='http://127.0.0.1:8131')
    p.add_argument('--check', action='store_true')
    p.add_argument('--install', action='store_true')
    p.add_argument('--crm', default='/0x11/app/nenex/w/ideas/conversations/axiomatic_crm')
    p.add_argument('--directory', default='/0x11/user/directory')
    p.add_argument('--batch-file', default='/tmp/nenex-address-records.json')
    args = p.parse_args()
    c = runpy.run_path(str(CLIENT))['Client'](args.base, timeout=180)
    names = ['lookup', 'join']
    reads = c.tool('read', reads=[{'path': '/0x11/weft/stdlib/' + name, 'care': 'x'} for name in names])['answers']
    formulas = {name: {'type': 'reference', 'value': read['reference']} for name, read in zip(names, reads)}
    if args.check:
        check(c, formulas)
    if not args.install:
        return
    preflight = c.tool('read', reads=[{'path': args.crm + '/contacts', 'care': 'y', 'limit': 100},
                                    {'path': args.directory, 'care': 'x'},
                                    {'path': '/0x11/gov/nenex_ui/contact_address', 'care': 'x'}])['answers']
    assert preflight[0]['exists'] and not preflight[0]['next']
    assert not preflight[1]['exists'], 'Directory already exists; inspect instead of overwriting'
    assert preflight[2]['exists'], 'Publish the Grove roles by rescanning nenex first'
    records, links = seed(args.directory, args.crm, preflight[0]['children'], args.crm + '/evidence/addresses_demo')
    cells, outputs = projections(args.crm + '/address_views', args.crm + '/contacts', args.directory, links, formulas)
    records += cells + [{'path': args.crm + '/address_views', 'slots': {
        '/sys/lede': 'CRM addresses — synthetic demonstration',
        '/sys/content': 'Shared address records and explicit workplace associations. Results are live cell projections. Generated addresses and associations are unverified.',
        '/directory': path(args.directory), '/contacts': path(outputs['contacts']), '/addresses': path(outputs['addresses'])}}]
    # Portable batch uses live stdlib references; executing install pins current definitions.
    portable = json.loads(json.dumps(records))
    for record in portable:
        value = record['slots'].get('/sys/weft')
        if value:
            formula = value['value'].rsplit('/', 1)[1]
            record['slots']['/sys/weft'] = {'type': 'reference', 'path': '/0x11/weft/stdlib/' + formula, 'care': 'x', 'case': 0}
    Path(args.batch_file).write_text(json.dumps({'records': portable, 'who': 'nenex_assistant'}, indent=2))
    result = c.tool('write', records=records, who='nenex_assistant', then=[{'path': outputs['contacts'], 'care': 'y', 'limit': 100}])
    rows = result['then'][outputs['contacts']]['children']
    assert len(rows) == len(preflight[0]['children'])
    assert sum(slot('contact_address_label') in x['properties'] for x in rows) == min(9, len(rows))
    print(json.dumps({'epoch': result['epoch'], 'contacts': len(rows), 'address_links': min(9, len(rows)),
                      'outputs': outputs, 'batch': args.batch_file}), flush=True)


if __name__ == '__main__':
    main()
