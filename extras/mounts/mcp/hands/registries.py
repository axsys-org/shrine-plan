"""The registries hand: public registries of real things, written into the world as records that keep their own
identifiers and assert only what the registry asserts.  Nothing is joined here; a match between registries is written
as a candidate (a tentative edge the overlay draws grey), and only a judgement written later makes it a `same`.

    /user/registries/usaspending/recipients/<uei>      {name, uei, duns, parent, parent_uei, street, city, state, zip, kinds, source}
    /user/registries/usaspending/awards/<id>           {id, recipient -> recipient, agency, amount, description, naics, place_state, source}
    /user/registries/usaspending/subawards/<id>        {id, prime -> award, prime_recipient, subawardee, amount, date, description, source}
    /user/registries/usaspending/.../mentions          {<slug>: -> a plant or facility the description names}   tentative
    /user/registries/usaspending/recipients/<uei>/candidates  {<slug>: -> an ECHO facility, LEI, CIK or importer that may be this recipient}
    /user/registries/echo/facilities/<registry_id>     {name, street, city, state, zip, naics, sic, latitude, longitude, source}
    /user/registries/gleif/<lei>                       {name, city, postal, country, status, parent -> gleif/<lei>, source}
    /user/registries/edgar/<cik>                       {name, sic, sic_description, ein, state_of_incorporation, city, state, source}
    /user/registries/importyeti/<slug>                 {name, address, shipments, last_shipment, names, addresses, source}
    /user/registries/importyeti/<slug>/suppliers/<n>   {name, country, shipments}
    /user/registries/eia/plants/<plant_id>             {name, city, state, zip, operator, operator_id, units, latitude, longitude, source}
    /user/registries/mep/opportunities/<number>        {name, number, due, build_america_buy_america, listed, source}   what needs making

    python3 registries.py <base> [--node 0x11] [--naics 335312] [--since 2024-10-01] [--top 25] [--importers 4] [--pudl DIR]
"""
import argparse, json, os, re, sys, time, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib.util
_spec = importlib.util.spec_from_file_location('hand_base', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hand.py'))
_hand = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_hand)
World = _hand.World

UA = 'shrine registries hand (research; ian@axiomatic.systems)'
def get(url, headers=None, data=None, timeout=60):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None,
                                 headers={'User-Agent': UA, 'Accept': 'application/json', **({'Content-Type': 'application/json'} if data is not None else {}), **(headers or {})})
    return json.load(urllib.request.urlopen(req, timeout=timeout))

def slug(s, n=48):
    s = re.sub(r'[^a-z0-9]+', '_', str(s).lower()).strip('_')
    return (s or 'x')[:n]
def seg(s, n=48):
    """A path segment the world accepts: lowercase letters, digits and underscore, starting with a letter; the
    original identifier stays in a slot."""
    s = slug(s, n)
    return s if s[:1].isalpha() else 'n' + s[:n - 1]
def ref(path, care='x'):
    return {'type': 'reference', 'value': '/h/%s/0/%d%s' % (care, len(path.strip('/').split('/')), path)}

class Writer:
    def __init__(self, world, who):
        self.w, self.who, self.batch, self.n, self.written = world, who, [], 0, set()
    def put(self, path, slots):
        slots = {k: v for k, v in slots.items() if v not in (None, '', [], {})}
        if path in self.written or not slots: return
        self.written.add(path); self.batch.append({'path': path, 'slots': slots, 'action': 'set'})
        if len(self.batch) >= 60: self.flush()
    def flush(self):
        if not self.batch: return
        try: self.w.tool('write', records=self.batch, who=self.who); self.n += len(self.batch)
        except Exception as e:
            for r in self.batch:
                try: self.w.tool('write', records=[r], who=self.who); self.n += 1
                except Exception as e2: print('  refused', r['path'], str(e2)[:120])
        self.batch = []

# ---- USAspending: who the government pays, and what they pass on
USA = 'https://api.usaspending.gov/api/v2'
def usaspending(root, wr, naics, since, top):
    period = [{'start_date': since, 'end_date': '2026-09-30'}]
    filters = {'naics_codes': {'require': [naics]}, 'time_period': period, 'award_type_codes': ['A', 'B', 'C', 'D']}
    recips = get(USA + '/search/spending_by_category/recipient/', data={'filters': filters, 'limit': top, 'page': 1})['results']
    print('usaspending: %d recipients for NAICS %s since %s' % (len(recips), naics, since))
    recipients = {}
    for r in recips:
        if not r.get('uei'): continue
        prof = {}
        try: prof = get(USA + '/recipient/%s/' % r['recipient_id'])
        except Exception as e: print('  profile failed', r.get('name'), str(e)[:80])
        loc = prof.get('location') or {}
        path = root + '/usaspending/recipients/' + seg(r['uei'])
        recipients[r['uei']] = dict(path=path, name=prof.get('name') or r['name'], state=loc.get('state_code'), city=loc.get('city_name'), parent=prof.get('parent_name'), parent_uei=prof.get('parent_uei'))
        wr.put(path, {'name': prof.get('name') or r['name'], 'uei': r['uei'], 'duns': prof.get('duns'), 'parent': prof.get('parent_name'), 'parent_uei': prof.get('parent_uei'),
                      'street': loc.get('address_line1'), 'city': loc.get('city_name'), 'state': loc.get('state_code'), 'zip': loc.get('zip'),
                      'kinds': ', '.join(prof.get('business_types') or []), 'obligated': round(float(r.get('amount') or 0)),
                      'source': 'https://www.usaspending.gov/recipient/%s/latest' % r['recipient_id']})
    # parents that are themselves recipients get a reference, not a name
    for uei, rec in recipients.items():
        if rec['parent_uei'] in recipients and rec['parent_uei'] != uei:
            wr.put(rec['path'] + '/parent_of_record', {'parent': ref(recipients[rec['parent_uei']]['path'])})
    fields = ['Award ID', 'Recipient Name', 'Recipient UEI', 'Awarding Agency', 'Award Amount', 'Description', 'Place of Performance State Code', 'NAICS Code', 'generated_internal_id']
    awards = get(USA + '/search/spending_by_award/', data={'filters': filters, 'fields': fields, 'limit': 100, 'page': 1, 'sort': 'Award Amount', 'order': 'desc'})['results']
    award_paths = {}
    for a in awards:
        uei = a.get('Recipient UEI')
        if uei not in recipients: continue
        path = root + '/usaspending/awards/' + seg(a['Award ID'])
        award_paths[a['Award ID']] = path
        wr.put(path, {'name': a['Award ID'], 'id': a['Award ID'], 'recipient': ref(recipients[uei]['path']), 'agency': a.get('Awarding Agency'), 'amount': round(float(a.get('Award Amount') or 0)),
                      'description': (a.get('Description') or '')[:600], 'naics': a.get('NAICS Code') or naics, 'place_state': a.get('Place of Performance State Code'),
                      'source': 'https://www.usaspending.gov/award/' + (a.get('generated_internal_id') or '')})
    print('usaspending: %d awards written' % len(award_paths))
    sfields = ['Sub-Award ID', 'Sub-Awardee Name', 'Sub-Award Amount', 'Sub-Award Date', 'Prime Recipient Name', 'Prime Award ID', 'Sub-Award Description', 'prime_award_internal_id']
    subs = get(USA + '/search/spending_by_award/', data={'filters': filters, 'fields': sfields, 'subawards': True, 'limit': 100, 'page': 1, 'sort': 'Sub-Award Amount', 'order': 'desc'})['results']
    subawards = []
    for s in subs:
        path = root + '/usaspending/subawards/' + seg(s['Sub-Award ID'])
        slots = {'name': '%s to %s' % (s['Sub-Award ID'], s.get('Sub-Awardee Name') or '?'), 'id': s['Sub-Award ID'], 'subawardee': s.get('Sub-Awardee Name'), 'prime_recipient': s.get('Prime Recipient Name'), 'amount': round(float(s.get('Sub-Award Amount') or 0)),
                 'date': int(str(s.get('Sub-Award Date') or '0').replace('-', '')[:8] or 0), 'description': (s.get('Sub-Award Description') or '')[:600],
                 'source': 'https://www.usaspending.gov/award/%s' % s.get('prime_award_internal_id')}
        if s.get('Prime Award ID') in award_paths: slots['prime'] = ref(award_paths[s['Prime Award ID']])
        wr.put(path, slots); subawards.append((path, slots))
    print('usaspending: %d subawards written' % len(subawards))
    return recipients, subawards

# ---- EPA ECHO: where regulated facilities are
ECHO = 'https://echodata.epa.gov/echo/echo_rest_services'
def echo_for(root, wr, recipients):
    found = {}
    for uei, rec in recipients.items():
        words = [w for w in re.split(r'[^A-Za-z0-9]+', rec['name']) if len(w) > 2 and w.upper() not in ('INC', 'LLC', 'CORP', 'THE', 'AND', 'CORPORATION', 'COMPANY', 'CO', 'LTD')][:2]
        if not words or not rec.get('state'): continue
        try:
            q = get(ECHO + '.get_facilities?output=JSON&p_fn=%s&p_st=%s' % (urllib.parse.quote(' '.join(words)), rec['state']))['Results']
            qid = q.get('QueryID')
            if not qid or int(q.get('QueryRows') or 0) == 0: continue
            fs = (get(ECHO + '.get_qid?output=JSON&qid=%s&pageno=1' % qid)['Results'].get('Facilities') or [])[:12]
        except Exception as e:
            print('  echo failed', rec['name'], str(e)[:80]); continue
        cands = {}
        for f in fs:
            path = root + '/echo/facilities/' + seg(f['RegistryID'])
            wr.put(path, {'name': f.get('FacName'), 'street': f.get('FacStreet'), 'city': f.get('FacCity'), 'state': f.get('FacState'), 'zip': f.get('FacZip'),
                          'naics': f.get('FacNAICSCodes'), 'sic': f.get('FacSICCodes'), 'latitude': f.get('FacLat'), 'longitude': f.get('FacLong'),
                          'programs': ', '.join(k[:-4] for k in ('AIRFlag', 'NPDESFlag', 'RCRAFlag', 'SDWISFlag', 'GHGFlag', 'TRIFlag') if f.get(k) and f.get(k) != 'N'),
                          'source': 'https://echo.epa.gov/detailed-facility-report?fid=' + f['RegistryID']})
            found[f['RegistryID']] = (path, f)
            cands['echo_' + seg(f['RegistryID'])] = ref(path)
        if cands: wr.put(rec['path'] + '/candidates', cands)
    print('echo: %d facilities written' % len(found))
    return found

# ---- GLEIF: legal entities and their parents
def gleif_for(root, wr, recipients):
    seen = {}
    def lei_record(lei):
        if lei in seen: return seen[lei]
        try: d = get('https://api.gleif.org/api/v1/lei-records/' + lei, headers={'Accept': 'application/vnd.api+json'})['data']
        except Exception: return None
        e = d['attributes']['entity']; addr = e.get('legalAddress') or {}
        path = root + '/gleif/' + seg(lei)
        slots = {'name': e['legalName']['name'], 'city': addr.get('city'), 'postal': addr.get('postalCode'), 'country': addr.get('country'), 'status': e.get('status'), 'lei': lei, 'source': 'https://search.gleif.org/#/record/' + lei}
        rel = (d.get('relationships') or {}).get('direct-parent', {}).get('links', {}).get('lei-record')
        if rel:
            try:
                parent = get(rel, headers={'Accept': 'application/vnd.api+json'})['data']['id']
                if lei_record(parent): slots['parent'] = ref(root + '/gleif/' + seg(parent))
            except Exception: pass
        wr.put(path, slots); seen[lei] = path; return path
    for uei, rec in recipients.items():
        try:
            hits = get('https://api.gleif.org/api/v1/fuzzycompletions?field=entity.legalName&q=' + urllib.parse.quote(rec['name']), headers={'Accept': 'application/vnd.api+json'})['data'][:3]
        except Exception as e:
            print('  gleif failed', rec['name'], str(e)[:80]); continue
        cands = {}
        for h in hits:
            lei = ((h.get('relationships') or {}).get('lei-records') or {}).get('data', {}).get('id')
            if lei and lei_record(lei): cands['gleif_' + seg(lei)] = ref(root + '/gleif/' + seg(lei))
        if cands: wr.put(rec['path'] + '/candidates', cands)
    print('gleif: %d entities written' % len(seen))

# ---- SEC EDGAR: public companies by name, with SIC, EIN and state of incorporation
def edgar_for(root, wr, recipients):
    try: tickers = get('https://www.sec.gov/files/company_tickers.json')
    except Exception as e:
        print('  edgar tickers failed', str(e)[:80]); return
    by_token = {}
    for t in tickers.values():
        by_token.setdefault(slug(t['title']).split('_')[0], []).append(t)
    n = 0
    for uei, rec in recipients.items():
        first = slug(rec['name']).split('_')[0]
        cands = {}
        for t in by_token.get(first, [])[:2]:
            cik = '%010d' % int(t['cik_str'])
            try: d = get('https://data.sec.gov/submissions/CIK%s.json' % cik)
            except Exception: continue
            path = root + '/edgar/' + seg(cik); biz = (d.get('addresses') or {}).get('business') or {}
            wr.put(path, {'name': d.get('name'), 'sic': d.get('sic'), 'sic_description': d.get('sicDescription'), 'ein': d.get('ein'), 'state_of_incorporation': d.get('stateOfIncorporation'),
                          'city': biz.get('city'), 'state': biz.get('stateOrCountry'), 'tickers': ', '.join(d.get('tickers') or []), 'cik': cik, 'source': 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=' + cik})
            cands['edgar_' + seg(cik)] = ref(path); n += 1
            time.sleep(0.15)
        if cands: wr.put(rec['path'] + '/candidates', cands)
    print('edgar: %d companies written' % n)

# ---- ImportYeti: who ships to whom, from customs manifests, through Firecrawl (the site refuses plain fetches)
def importyeti_for(root, wr, recipients, limit):
    key = os.environ.get('FIRECRAWL_API_KEY') or ''
    if not key: print('importyeti: no FIRECRAWL_API_KEY, skipped'); return
    done = 0
    for uei, rec in list(recipients.items()):
        if done >= limit: break
        s = slug(re.sub(r'\b(inc|llc|corp|corporation|co|ltd|company)\b\.?', '', rec['name'].lower())).replace('_', '-')
        url = 'https://www.importyeti.com/company/' + s
        try:
            d = get('https://api.firecrawl.dev/v1/scrape', headers={'Authorization': 'Bearer ' + key}, data={'url': url, 'formats': ['markdown'], 'onlyMainContent': True}, timeout=90)
            md = (d.get('data') or {}).get('markdown') or ''
        except Exception as e:
            print('  importyeti failed', s, str(e)[:80]); continue
        if 'Total Sea Shipments' not in md: continue
        done += 1
        m = lambda pat: (re.search(pat, md) or [None, None])[1]
        total = m(r'Total Sea Shipments\s*([\d,]+)'); last = m(r'Last Shipment Spotted\s*([\d/]+)')
        names = m(r'imports under (\d+) names'); addrs = m(r'(\d+) addresses')
        addr = m(r'Address\n\n([^\n]+)')
        path = root + '/importyeti/' + seg(s)
        wr.put(path, {'name': rec['name'], 'address': addr, 'shipments': int(total.replace(',', '')) if total else None, 'last_shipment': last, 'names': int(names) if names else None, 'addresses': int(addrs) if addrs else None, 'source': url})
        # suppliers: a markdown table, one row per supplier:
        # | [Name](.../supplier/<slug>)<br>[City](...), [Country](.../location/supplier/<country>/country) |  | 2,076<br>categories | description<br>HS Codes: ( [8483.10](...) ... ) |
        i = 0
        for line in md.split('\n'):
            mm = re.match(r'\| \[([^\]]{2,100})\]\(https://www\.importyeti\.com/supplier/([a-z0-9-]+)\)(.*?)\|\s*\|\s*([\d,]+)(?:<br>([^|]*))?\|([^|]*)\|', line)
            if not mm: continue
            name, sl, where, count, cats, desc = mm.groups()
            country = (re.findall(r'\[([^\]]+)\]\(https://www\.importyeti\.com/location/supplier/[a-z-]+/country\)', where) or [''])[0]
            hs = re.findall(r'\[(\d{4}\.\d{2})\]', desc or '')
            text = re.sub(r'<br>.*$', '', (desc or '').strip())[:200]
            i += 1
            wr.put(path + '/suppliers/' + seg(sl), {'name': name.strip(), 'country': country, 'shipments': int(count.replace(',', '')), 'kinds': ', '.join(c.strip() for c in (cats or '').split('<br>') if c.strip() and c.strip() != 'Other'),
                                                    'hs_codes': ', '.join(hs), 'goods': text, 'source': 'https://www.importyeti.com/supplier/' + sl})
            if i >= 20: break
        wr.put(rec['path'] + '/candidates', {'importyeti_' + seg(s): ref(path)})
        print('importyeti:', rec['name'], total, 'shipments,', i, 'suppliers')

# ---- NIST MEP supplier scouting: what needs making, as the demand side; open opportunities, through Firecrawl
MEP = 'https://www.nist.gov/mep/mep-national-network-open-supplier-scouting-opportunities'
def mep_opportunities(root, wr):
    key = os.environ.get('FIRECRAWL_API_KEY') or ''
    if not key: print('mep: no FIRECRAWL_API_KEY, skipped'); return
    try:
        d = get('https://api.firecrawl.dev/v1/scrape', headers={'Authorization': 'Bearer ' + key}, data={'url': MEP, 'formats': ['markdown'], 'onlyMainContent': True}, timeout=90)
        md = (d.get('data') or {}).get('markdown') or ''
    except Exception as e:
        print('  mep failed', str(e)[:80]); return
    updated = (re.search(r'Updated:\s*([A-Za-z]+\.? \d+, \d{4})', md) or [None, None])[1]
    n = 0
    for line in md.split('\n'):
        mm = re.match(r'\| (\d{4}-\d+) \| ([^|]+?) \| (\d{1,2}/\d{1,2}/\d{2}) \|', line)
        if not mm: continue
        number, item, due = mm.groups()
        m, dd, yy = due.split('/')
        baba = item.startswith('BABA')
        wr.put(root + '/mep/opportunities/' + seg(number), {'name': re.sub(r'^BABA:?\s*', '', item).strip(), 'number': number, 'due': int('20%s%02d%02d' % (yy, int(m), int(dd))),
                                                              'build_america_buy_america': baba, 'listed': updated, 'source': MEP})
        n += 1
    print('mep: %d open scouting opportunities written (listed %s)' % (n, updated))

# ---- EIA-860 (through PUDL): the plants a description names
def eia_mentions(root, wr, subawards, pudl):
    try:
        import pyarrow.parquet as pq
    except ImportError:
        print('eia: pyarrow missing, skipped'); return
    ents = pq.read_table(os.path.join(pudl, 'core_eia__entity_plants.parquet')).to_pandas()
    sp = pq.read_table(os.path.join(pudl, 'core_eia860__scd_plants.parquet')).to_pandas().sort_values('report_date').drop_duplicates('plant_id_eia', keep='last')
    uts = pq.read_table(os.path.join(pudl, 'core_eia__entity_utilities.parquet')).to_pandas().set_index('utility_id_eia')['utility_name_eia'].to_dict()
    gens = pq.read_table(os.path.join(pudl, 'core_eia860__scd_generators.parquet')).to_pandas()
    names = [(n, pid) for n, pid in zip(ents['plant_name_eia'], ents['plant_id_eia']) if isinstance(n, str) and len(n.split()) >= 2 and len(n) >= 8]
    written = 0
    for path, slots in subawards:
        text = (slots.get('description') or '').lower()
        hits = {}
        for n, pid in names:
            if n.lower() in text:
                e = ents[ents['plant_id_eia'] == pid].iloc[0]; row = sp[sp['plant_id_eia'] == pid]
                uid = int(row['utility_id_eia'].iloc[0]) if len(row) and str(row['utility_id_eia'].iloc[0]) != 'nan' else None
                ppath = root + '/eia/plants/' + seg(str(int(pid)))
                units = int((gens[gens['plant_id_eia'] == pid]['report_date'] == gens[gens['plant_id_eia'] == pid]['report_date'].max()).sum()) if len(gens[gens['plant_id_eia'] == pid]) else None
                wr.put(ppath, {'name': n, 'city': e.get('city'), 'state': e.get('state'), 'zip': e.get('zip_code'), 'operator': uts.get(uid), 'operator_id': uid, 'units': units,
                               'latitude': float(e['latitude']) if str(e.get('latitude')) != 'nan' else None, 'longitude': float(e['longitude']) if str(e.get('longitude')) != 'nan' else None,
                               'source': 'https://data.catalyst.coop/pudl/core_eia__entity_plants?plant_id_eia=' + str(int(pid))})
                hits['eia_' + str(int(pid))] = ref(ppath); written += 1
        if hits: wr.put(path + '/mentions', hits)
    print('eia: %d plant mentions written' % written)

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('base'); p.add_argument('--node', default='0x11'); p.add_argument('--naics', default='335312'); p.add_argument('--since', default='2024-10-01')
    p.add_argument('--top', type=int, default=25); p.add_argument('--importers', type=int, default=4); p.add_argument('--pudl', default='')
    a = p.parse_args()
    w = World(a.base, a.node); root = '/' + a.node + '/user/registries'; wr = Writer(w, 'registries')
    wr.put(root, {'name': 'registries', 'description': 'public registries of real things, each record keeping its own identifiers; candidates are unjudged matches'})
    recipients, subawards = usaspending(root, wr, a.naics, a.since, a.top); wr.flush()
    for stage in (lambda: echo_for(root, wr, recipients), lambda: gleif_for(root, wr, recipients), lambda: edgar_for(root, wr, recipients),
                  lambda: importyeti_for(root, wr, recipients, a.importers), lambda: mep_opportunities(root, wr),
                  lambda: (eia_mentions(root, wr, subawards, a.pudl) if a.pudl else None)):
        try: stage()
        except Exception as e: print('stage failed:', type(e).__name__, str(e)[:160])
        wr.flush()
    print('written', wr.n, 'records')
