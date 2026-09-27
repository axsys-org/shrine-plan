"""Thin Shrine client for this application. Rules and durable state live in Foil/NS."""
from pathlib import Path
import os, sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, os.environ.get('SHRINE_BRIDGE', str(ROOT.parent/'shrine-mcp')))
from client import Client
from records import checked, fields_of, digest

SHRINE = Client(os.environ.get('SHRINE_CONNECTION', str(Path.home()/'.local/share/shrine/v5/connection.json')))
WORK = '/campus/work/build'

def browser_seed():
    """Optional personal observations are kept outside version control."""
    import json
    path = Path(os.environ.get('CANVAS_BROWSER_SEED', str(Path.home()/'.local/share/shrine/canvas/browser-seed.json')))
    if not path.exists(): path = ROOT/'browser-seed.example.json'
    return json.loads(path.read_text())

def read(path, recursive=False):
    rows, after = [], ''
    while True:
        result = SHRINE.call('read', path=path, recursive=recursive, limit=100, after=after)
        rows.extend({**fields_of(r), '_path':r['path'], '_case':r['case']} for r in result['records'])
        if not result['more']: return rows
        after = result['next_after']

def one(path):
    rows = read(path)
    return rows[0] if rows else {}

def write(path, fields, case=None, create=False):
    args = {'op':'make' if create else 'poke','path':path,'fields':fields,'work':WORK}
    if case is not None: args['expected_case'] = case
    return checked(SHRINE.call('write', **args))

def upsert(path, fields):
    old = one(path)
    return write(path, fields, old.get('_case',0), not old)

def pin(expression):
    return checked(SHRINE.call('eval', expression=expression, work=WORK))['value']

def observe(subject, value, *, availability='available', coverage='partial', revision=None):
    envelope = {'source':'stevens-canvas','subject':subject,'availability':availability,
                'coverage':coverage,'value':value,'work':WORK}
    if revision is not None: envelope['revision'] = revision
    return SHRINE.call('observe', envelope=envelope)
