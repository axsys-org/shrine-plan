import urllib.request, urllib.parse, json, pathlib, hashlib, datetime, time
import argparse
parser=argparse.ArgumentParser(description='Download every published Austin address point without geometry')
parser.add_argument('--output',default='.local-data/austin-addresses')
args=parser.parse_args()
p=pathlib.Path(args.output);p.mkdir(parents=True,exist_ok=True)
base='https://maps.austintexas.gov/gis/rest/Shared/Property/MapServer/0'
def query(**params):
 u=base+'/query?'+urllib.parse.urlencode(dict(f='json',**params))
 for attempt in range(4):
  try:
   d=json.load(urllib.request.urlopen(u,timeout=90));assert 'error' not in d,d;return d
  except Exception:
   if attempt==3:raise
   time.sleep(2)
with urllib.request.urlopen(base+'?f=json',timeout=90) as response:
 metadata=json.load(response)
(p/'layer.json').write_text(json.dumps(metadata,indent=2))
ids=query(where='1=1',returnIdsOnly='true')['objectIds'];ids=sorted(set(ids))
(p/'ids.json').write_text(json.dumps(ids))
started=datetime.datetime.now(datetime.timezone.utc).isoformat();total=0
with (p/'records.jsonl.partial').open('w') as out:
 for offset in range(0,len(ids),5000):
  part=ids[offset:offset+5000]
  d=query(where=f'OBJECTID >= {part[0]} AND OBJECTID <= {part[-1]}',outFields='*',returnGeometry='false',resultRecordCount=10000)
  rows=[x['attributes'] for x in d['features']]
  assert set(x['OBJECTID'] for x in rows)==set(part),(offset,len(rows))
  for row in sorted(rows,key=lambda x:x['OBJECTID']):out.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
  total+=len(rows)
  if offset%25000==0:print(total,'/',len(ids),flush=True)
(p/'records.jsonl.partial').rename(p/'records.jsonl')
sha=hashlib.sha256((p/'records.jsonl').read_bytes()).hexdigest()
manifest={'source':base,'started':started,'finished':datetime.datetime.now(datetime.timezone.utc).isoformat(),'records':total,'sha256':sha,'geometry':False,'scope':'Entire published City of Austin Addresses layer; not a city-limits filter','consistency':'Object ID set captured at start; records fetched in batches, not a transactional server snapshot'}
(p/'manifest.json').write_text(json.dumps(manifest,indent=2));print(json.dumps(manifest),flush=True)
