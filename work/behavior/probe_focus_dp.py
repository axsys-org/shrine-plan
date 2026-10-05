exec(open('work/behavior/check_native.py').read().split('try:')[0])
j=json.loads((w/'pure-programs/3c520de19299443b956b804879ecb608.json').read_text())['job']['draft']
c,frame=s.call('read');frame=workshop_host.typed_collections.project(frame)
rows=behaviors.row_values(frame,'/0x11/app/medium/c774e88fb51af4ae5a962a00f052eb9fc');rows=[r for r in rows if r.get('duration') and isinstance(r.get('depends_on'),list)]
adapter=behaviors.BOOL_ADAPTER.replace('remaining=row[json] rows results=', 'remaining=row[json] rows.keep((\\ item (equal[json] (view/field "id" item) (view/field "id" input)))) results=')
try:
 t=time.monotonic();r=behaviors.prepare(s,j['source']+adapter,[],probe={'rows':rows,'id':rows[0]['id']});print('eight-record single predicate passed',round(time.monotonic()-t,2),behaviors.output(r),flush=True)
 Path('work/behavior/focus-native.json').write_text(json.dumps(r,indent=2))
except Exception as e: print('probe failed',str(e)[:500],flush=True)
finally:s.server_close()
