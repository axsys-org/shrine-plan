exec(open('work/behavior/check_native.py').read().split('try:')[0])
j=json.loads((w/'pure-programs/738a15c0c47448e0b6ff7eb9f9453183.json').read_text())['job']['draft']
try:
 t=time.monotonic();r=behaviors.prepare(s,j['source']+behaviors.BOOL_ADAPTER,[j['cases'][1]],probe=None);print('two-record check passed',round(time.monotonic()-t,2),flush=True)
except Exception as e: print('check failed',str(e)[:500],flush=True)
finally:s.server_close()
