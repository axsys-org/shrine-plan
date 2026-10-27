"""The judging loop, once, as an agent would do it by hand: Cummins Power Generation's candidates, judged from what the
registries state, written back as `same` (both ways) or as the relation they turn out to be, each with its `why`.
    STRANGERS_BASE=http://127.0.0.1:8330 python3 judge_cummins.py"""
import sys, os, re, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'strangers'))
from world import W
R = '/0x11/user/registries'; rec = R + '/usaspending/recipients/lszhmmeg8481'
props = lambda p: {k.lstrip('/'): v for k, v in (W.read(p, 'x').get('properties') or {}).items() if not k.startswith('/sys')}
ref = lambda p: {'type': 'reference', 'value': '/h/x/0/%d%s' % (len(p.strip('/').split('/')), p)}
me = props(rec); writes = []
fac = R + '/echo/facilities/n110000426049'; f = props(fac)
if f.get('street', '').upper().startswith('1400 73RD') and str(f.get('zip')) == '55432' and '335312' in str(f.get('naics')):
    why = 'USAspending gives 1400 73RD AVE NE, 55432; ECHO 110000426049 is CUMMINS POWER GENERATION INC at 1400 73RD AVENUE NE, Fridley 55432, NAICS 333618 335312, SIC 3519 3621 3622; SAM registers CAGE 44940 at that address'
    writes.append({'path': rec + '/same/echo_n110000426049', 'slots': {'same': ref(fac), 'why': why, 'by': 'claude', 'judged': int(time.strftime('%Y%m%d'))}})
    writes.append({'path': fac + '/same/usaspending_lszhmmeg8481', 'slots': {'same': ref(rec), 'why': 'the recipient registered at this street and zip, NAICS 335312 on both', 'by': 'claude'}})
ed = R + '/edgar/n0000026172'; e = props(ed)
if e.get('name', '').upper().startswith('CUMMINS INC') and me.get('parent', '').upper().startswith('CUMMINS INC'):
    writes.append({'path': rec + '/parent_filing', 'slots': {'parent': ref(ed), 'why': "USAspending names CUMMINS INC. (UEI DTSXKA2BGMD9) as this recipient's parent; EDGAR CIK 26172 is CUMMINS INC, SIC 3510 Engines & Turbines, Indiana; a parent, not the same entity", 'by': 'claude'}})
iy = R + '/importyeti/cummins_power_generation'; i = props(iy)
if i.get('name', '').upper().startswith('CUMMINS POWER GENERATION') and '55432' in str(i.get('address', '')):
    writes.append({'path': rec + '/same/importyeti_cummins_power_generation', 'slots': {'same': ref(iy), 'why': "customs filings under CUMMINS POWER GENERATION INC. at Minneapolis 55432 (7033 Central Ave NE, a suite, not the plant); same name and zip as the registration; shipments are the registrant's imports", 'by': 'claude', 'confidence': 'name and zip, not the street'}})
print('judgements:', [w['path'].split('/registries/')[1] for w in writes])
if writes: print('epoch', W.tool('write', records=writes, who='claude').get('epoch'))
