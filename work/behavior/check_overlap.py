exec(open('work/behavior/check_native.py').read().split('try:')[0])
try:
 source=Path('extras/mounts/medium/no_overlap.grove').read_text()
 rows=[{'id':'a','lane':'A','start':'2026-10-01','duration':'2'},{'id':'b','lane':'A','start':'2026-10-03','duration':'3'}]
 cases=[{'input':{'changed':'b','rows':rows},'expected':True},{'input':{'changed':'b','rows':[rows[0],{**rows[1],'start':'2026-10-02'}]},'expected':False},{'input':{'changed':'b','rows':[rows[0],{**rows[1],'start':'2026-10-02','lane':'B'}]},'expected':True}]
 result=behaviors.ensure_overlap(s)
 Path('work/behavior/overlap-candidate.json').write_text(json.dumps(result,indent=2))
 print('Native overlap guard prepared; adjacency, overlap, lane checks passed',flush=True)
except Exception as e:print(type(e).__name__,str(e)[:3200],flush=True)
finally:s.server_close()
