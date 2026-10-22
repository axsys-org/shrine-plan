#!/usr/bin/env python3
"""Prepare and install the full Austin address layer as bounded native overlays."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import runpy
import sqlite3
import shutil
import time
from model import path, reference, slot

ROOT = '/0x11/user/austin_addresses'
LAW = '/0x11/gov/nenex_ui/austin_expand'
CLIENT = Path(__file__).resolve().parents[2] / 'cooperate/client.py'


def clean(value):
    return '' if value is None else ' '.join(str(value).split())


def normalize(row):
    ident = int(row['PLACE_ID'])
    if ident < 0:
        raise ValueError('Negative place ID')
    components = [clean(row.get(k)) for k in ('PREFIX_DIRECTION', 'STREET_NAME', 'STREET_TYPE', 'SUFFIX_DIRECTION')]
    street = ' '.join(x for x in components if x)
    street_id = 's_' + hashlib.sha256(json.dumps(components).encode()).hexdigest()[:24]
    number = ' '.join(x for x in [clean(row['ADDRESS']), clean(row.get('ADDRESS_FRACTION'))] if x)
    fields = [str(ident), number, street_id, street, clean(row['FULL_STREET_NAME']),
              clean(row['ADDRESS_TYPE']), clean(row.get('PARENT_PLACE_ID')),
              clean(row.get('SEGMENT_ID')), clean(row['OBJECTID'])]
    assert all('|' not in x and '~' not in x for x in fields), 'Reserved packed delimiter in source'
    return ident // 1000, street_id, street, '|'.join(fields)


def overlay(definition, case, source):
    return '/o/'+str(case)+'/'+str(len(definition.strip('/').split('/')))+definition+'/'+str(len(source.strip('/').split('/')))+source


def prepare(folder, c):
    lens_names=['/0x11/gov/nenex_ui/austin_lens','/0x11/gov/nenex_ui/austin_street_lens']
    lens_reads=c.tool('read',reads=[{'path':name,'care':'x'} for name in lens_names])['answers']
    assert all(x['exists'] for x in lens_reads), 'Publish the native address lenses first'
    cases=[int(x['reference'].split('/')[3]) for x in lens_reads]
    raw = folder / 'records.jsonl'
    manifest = json.loads((folder / 'manifest.json').read_text())
    digest = hashlib.file_digest(raw.open('rb'), 'sha256').hexdigest()
    assert digest == manifest['sha256'], 'Source archive changed'
    archive=folder/'archives'/digest
    archive.mkdir(parents=True,exist_ok=True)
    for filename in ('records.jsonl','manifest.json','layer.json','ids.json'):
        target=archive/filename
        if not target.exists():shutil.copyfile(folder/filename,target)
    raw=archive/'records.jsonl'
    assert hashlib.file_digest(raw.open('rb'),'sha256').hexdigest()==digest
    snapshot = 's_' + digest[:16] + '_v2'
    source = ROOT + '/snapshots/' + snapshot
    street_prefix=overlay(lens_names[1],cases[1],source+'/street_pages/p_x').rsplit('/',1)[0]
    pages = collections.defaultdict(list)
    streets = {}
    counts = collections.Counter()
    seen = set()
    db = sqlite3.connect(folder / 'index.sqlite')
    db.execute('DROP TABLE IF EXISTS addresses')
    db.execute('CREATE TABLE addresses(place_id INTEGER PRIMARY KEY,label TEXT,street_id TEXT,page INTEGER,address_type INTEGER,namespace_path TEXT)')
    for line in raw.open():
        row = json.loads(line)
        ident = row['PLACE_ID']
        assert ident not in seen, ('Duplicate place ID', ident)
        seen.add(ident)
        page, sid, label, packed = normalize(row)
        assert sid not in streets or streets[sid] == label, 'Street designation hash collision'
        streets[sid] = label
        pages[page].append((ident, packed))
        counts[row['ADDRESS_TYPE']] += 1
        db.execute('INSERT INTO addresses VALUES(?,?,?,?,?,?)', (ident,row['FULL_STREET_NAME'],sid,page,row['ADDRESS_TYPE'],overlay(lens_names[0],cases[0],source+'/pages/p_'+str(page))+'/place_'+str(ident)))
    assert len(seen) == manifest['records']
    assert all(len(rows) <= 1000 for rows in pages.values())
    db.execute('CREATE INDEX label_idx ON addresses(label)')
    db.commit();db.close()
    records = []
    def add(target, **slots):
        records.append({'path':target,'slots':slots})
    add(ROOT, **{'/sys/lede':'Austin address catalog', 'status':'loading',
        'source':manifest['source'], 'snapshot':path(source), 'source_records':len(seen),
        'ordinary_addresses':counts[1], 'other_address_points':len(seen)-counts[1],
        'page_count':len(pages), 'street_designations':len(streets),
        'scope':manifest['scope'], 'missing_fields':'Locality, ZIP code and unit are absent from this source; no occupancy inferred.',
        'browse':path(ROOT+'/pages'), 'source_archive':str(raw.resolve()), 'sha256':digest})
    add(source, **{'/sys/lede':'City of Austin Addresses source snapshot', **manifest,
        'sha256':digest, 'source_archive':str(raw.resolve()),
        'normalization':'austin_slots_v2', 'payload_encoding':'pipe fields, tilde rows; reserved delimiters refused', 'payload_columns':'PLACE_ID | number+fraction | street designation ID | street label | FULL_STREET_NAME | ADDRESS_TYPE | PARENT_PLACE_ID | SEGMENT_ID | OBJECTID',
        'raw_types':json.dumps(counts,sort_keys=True),
        'note':'Type 1 means Address. Other codes remain source classifications; code 16 is undocumented in the downloaded domain metadata.'})
    add(ROOT+'/pages', **{'/sys/lede':'Address pages by Place ID // 1000', 'page_count':len(pages),
        'path_rule':'Read the page result link, then append /place_<PLACE_ID>. The native /o lens resolves individual records.'})
    add(ROOT+'/streets', **{'/sys/lede':'Street designations from source components', 'count':len(streets),
        'browse':path(ROOT+'/street_pages'),
        'identity_basis':'Normalized prefix/name/type/suffix tuple; a designation, not a claim of physical street connectivity.'})
    street_pages=collections.defaultdict(list)
    for sid,label in sorted(streets.items()):
        street_pages[sid[2:4]].append(sid+'|'+label)
    for prefix,rows in sorted(street_pages.items()):
        raw_path=source+'/street_pages/p_'+prefix;view_path=ROOT+'/street_pages/p_'+prefix
        add(raw_path, **{slot('austin_payload'):'~'.join(rows),slot('austin_page_base'):path(overlay(lens_names[1],cases[1],raw_path)),
            slot('austin_page_source'):path(raw_path),slot('austin_streets'):path(street_prefix),
            'row_count':len(rows),'snapshot':path(source)})
        add(view_path, **{'/sys/lede':'Street designation bucket '+prefix,
            '/sys/weft':reference('/0x11/gov/nenex_ui/austin_street_expand','x'),
            '/sys/tack':reference(raw_path,'x'),'row_count':len(rows),'result':path(overlay(lens_names[1],cases[1],raw_path))})
    for page, rows in sorted(pages.items()):
        name='p_'+str(page); raw_path=source+'/pages/'+name; view_path=ROOT+'/pages/'+name
        payload='~'.join(line for _,line in sorted(rows))
        add(raw_path, **{slot('austin_payload'):payload, slot('austin_page_base'):path(overlay(lens_names[0],cases[0],raw_path)),
            slot('austin_page_source'):path(raw_path),slot('austin_streets'):path(street_prefix),
            'snapshot':path(source),'row_count':len(rows),'payload_sha256':hashlib.sha256(payload.encode()).hexdigest(),
            '/sys/lede':'Source page '+str(page)})
        add(view_path, **{'/sys/lede':'Place IDs '+str(page*1000)+'–'+str(page*1000+999),
            '/sys/weft':reference(LAW,'x'), '/sys/tack':reference(raw_path,'x'),
            'row_count':len(rows),'result':path(overlay(lens_names[0],cases[0],raw_path))})
    with (folder/'namespace.jsonl').open('w') as out:
        for record in records:out.write(json.dumps(record,ensure_ascii=False,separators=(',',':'))+'\n')
    report={'snapshot':snapshot,'records':len(seen),'ordinary_addresses':counts[1],
            'pages':len(pages),'streets':len(streets),'namespace_records':len(records),
            'max_page':max(map(len,pages.values())), 'source':source,'lenses':dict(zip(lens_names,cases))}
    (folder/'prepared.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)


def install(c,folder):
    report=json.loads((folder/'prepared.json').read_text())
    law=c.read(LAW,'x');assert law['exists'],'Native Grove overlay not published'
    records=[json.loads(x) for x in (folder/'namespace.jsonl').open()]
    for name,case in report['lenses'].items():
        assert int(c.read(name,'x')['reference'].split('/')[3])==case, 'Lens changed: prepare again before installation'
    # Retrying a batch after a transport failure is safe: records are deterministic.
    # A durable local cursor follows acknowledged batches. No automatic uncertain retry.
    cursor_file=folder/'installed.json'
    cursor=json.loads(cursor_file.read_text()) if cursor_file.exists() else {'next':0,'snapshot':report['snapshot']}
    assert cursor['snapshot']==report['snapshot']
    # Definitions are pinned for reproducibility; data pages are immutable per snapshot.
    laws={LAW:law['reference'],'/0x11/gov/nenex_ui/austin_street_expand':c.read('/0x11/gov/nenex_ui/austin_street_expand','x')['reference']}
    for record in records:
        if '/sys/weft' in record['slots']:
            definition=record['slots']['/sys/weft']['path']
            record['slots']['/sys/weft']={'type':'reference','value':laws[definition]}
    while cursor['next'] < len(records):
        start=cursor['next']; end=start; size=0
        while end < len(records) and end-start < 300:
            weight=len(json.dumps(records[end]).encode())
            if end>start and size+weight>700000:break
            size+=weight;end+=1
        answer=c.tool('write',records=records[start:end],who='nenex_assistant')
        cursor.update(next=end,epoch=answer['epoch'])
        cursor_file.write_text(json.dumps(cursor))
        print(json.dumps({'installed':end,'total':len(records),'epoch':answer['epoch']}),flush=True)
    c.tool('write',records=[{'path':ROOT,'action':'poke','slots':{'status':'imported_pending_verification','installed_namespace_records':len(records)}}],who='nenex_assistant')


def verify(c,folder):
    report=json.loads((folder/'prepared.json').read_text())
    manifest=json.loads((folder/'manifest.json').read_text())
    archive=folder/'archives'/manifest['sha256']/'records.jsonl'
    with archive.open('rb') as raw:
        assert hashlib.file_digest(raw,'sha256').hexdigest()==manifest['sha256'], 'Source archive changed'
    records=[json.loads(x) for x in (folder/'namespace.jsonl').open()]
    pages=[x for x in records if '/sys/weft' in x['slots'] and x['slots']['/sys/weft']['path']==LAW]
    # Verify every page binding and count without expanding the city.
    # Sampled native expansions check data/codec agreement; source archive SHA256
    # and per-payload digests are recorded for reproducible replay.
    bindings=[x for x in records if '/sys/weft' in x['slots']]
    verified=0
    verified_streets=0
    for start in range(0,len(bindings),100):
        subset=bindings[start:start+100]
        result=c.tool('read',reads=[{'path':x['path'],'care':'x'} for x in subset])['answers']
        assert len(result)==len(subset)
        for expected,actual in zip(subset,result):
            assert actual['exists']
            props=actual['properties']; slots=expected['slots']
            assert actual['path']==expected['path']
            assert int(props['/row_count'])==slots['row_count']
            assert props['/result']==slots['result']['value']
            source=slots['/sys/tack']['path']
            assert props['/sys/tack']=='/h/x/0/'+str(len(source.strip('/').split('/')))+source
            definition=slots['/sys/weft']['path']
            assert props['/sys/weft'].startswith('/h/x/') and props['/sys/weft'].endswith(definition)
            assert int(props['/sys/weft'].split('/')[3])>0, 'Presentation definition must be pinned'
            if definition==LAW:verified+=int(props['/row_count'])
            else:verified_streets+=int(props['/row_count'])
        print('Verified bindings',min(start+100,len(bindings)),'/',len(bindings),flush=True)
    assert verified==report['records']
    assert verified_streets==report['streets']
    picks=[pages[0],pages[len(pages)//2],pages[-1],max(pages,key=lambda x:x['slots']['row_count'])]
    originals={x['path']:x for x in records}
    for page in picks:
        result=c.read(page['slots']['result']['value'],'z',limit=500)
        children=list(result['children'])
        while result.get('next'):
            result=c.read(page['slots']['result']['value'],'z',limit=500,next=result['next'])
            children.extend(result['children'])
        children={x['path']:x for x in children if 'properties' in x}
        assert len(children)==page['slots']['row_count'], (page['path'],len(children),page['slots']['row_count'])
        source=page['slots']['/sys/tack']['path']
        expected={line.split('|')[0]:line.split('|') for line in originals[source]['slots'][slot('austin_payload')].split('~')}
        for child in children.values():
            props=child['properties'];ident=props[slot('address_place_id')];fields=expected[ident]
            assert props['/sys/about']==child['path']
            assert props['/sys/lede']==fields[4]
            assert props[slot('address_number')]==fields[1]
            assert props[slot('address_street_label')]==fields[3]
            assert props[slot('address_label')]==fields[4]
            for key,index in [('address_type',5),('address_source_parent_id',6),
                              ('address_source_segment_id',7),('address_source_object_id',8)]:
                assert props.get(slot(key),'')==fields[index]
            assert props[slot('address_source')]==source
            street_prefix=originals[source]['slots'][slot('austin_streets')]['value']
            assert props[slot('address_street')]==street_prefix+'/p_'+fields[2][2:4]+'/'+fields[2]
            assert slot('address_postal_code') not in props and slot('address_locality') not in props
        first=next(iter(children.values()))
        direct=c.tool('read',reads=[{'path':first['path'],'care':'x'}, {'path':first['properties'][slot('address_street')],'care':'x'}])['answers']
        assert direct[0]['properties']==first['properties'], 'Individual address must resolve'
        assert direct[1]['properties']['/sys/lede']==first['properties'][slot('address_street_label')]
    page=picks[0]
    outcome=c.tool('write',records=[{'path':ROOT,'action':'poke','slots':{'status':'ready','verified_records':verified,
        'source_archive':str(archive.resolve()),
        'verified_street_designations':verified_streets,
        'verification':'All address and street page bindings/counts checked; first, middle, last and largest address expansions compared field-by-field.',
        'example':page['slots']['result']}},
        {'path':report['source'],'action':'poke','slots':{'source_archive':str(archive.resolve())}},
        {'path':ROOT+'/streets','action':'poke','slots':{'browse':path(ROOT+'/street_pages')}}],who='nenex_assistant')
    result={'status':'ready','records':verified,'street_designations':verified_streets,
        'source_sha256':manifest['sha256'],'epoch':outcome['epoch'],
        'sampled_pages':[x['slots']['result']['value'] for x in picks],
        'example':page['slots']['result']['value']}
    (folder/'verified.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['prepare','install','verify','search'])
    p.add_argument('--folder',type=Path,default=Path('.local-data/austin-addresses'))
    p.add_argument('--base',default='http://127.0.0.1:8131')
    p.add_argument('--query',default='301 W 2ND')
    args=p.parse_args()
    if args.command=='search':
        db=sqlite3.connect(args.folder/'index.sqlite')
        for ident,label,page,kind,ns_path in db.execute('SELECT place_id,label,page,address_type,namespace_path FROM addresses WHERE label LIKE ? LIMIT 25',('%'+args.query+'%',)):
            print(json.dumps({'place_id':ident,'label':label,'source_type':kind,'path':ns_path}))
        return
    c=runpy.run_path(str(CLIENT))['Client'](args.base,timeout=240)
    if args.command=='prepare':return prepare(args.folder,c)
    (install if args.command=='install' else verify)(c,args.folder)


if __name__=='__main__':main()
