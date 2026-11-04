"""The wake test's agent: it proves the bridge and nothing else. Woken by the host with the WAKE_*
environment, it writes one marker record under /<world>/agent/stub naming why it woke and which paths
changed, through the token route it was given, and exits. No reading, no judgment, no domain words."""
import json, os, sys, time, urllib.request

world, why, paths, wake = os.environ['WAKE_WORLD'], os.environ.get('WAKE_WHY', ''), os.environ.get('WAKE_PATHS', ''), os.environ.get('WAKE_WAKE', '')
url, token = os.environ['WAKE_MCP'], os.environ['WAKE_TOKEN']
record = {'path': f'/{world}/agent/stub/s{int(time.time() * 1000)}', 'slots': {'why': why, 'paths': paths, 'wake': wake, 'prompt_len': len(os.environ.get('WAKE_PROMPT', ''))}}
body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'mcp/write', 'arguments': {'records': [record]}}}).encode()
req = urllib.request.Request(url, body, {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token})
with urllib.request.urlopen(req, timeout=60) as r:
    reply = json.load(r)
res = reply.get('result', {})
if res.get('isError'):
    print('stub: refused', res, file=sys.stderr); sys.exit(2)
print('stub: wrote', record['path'], 'for', why)
