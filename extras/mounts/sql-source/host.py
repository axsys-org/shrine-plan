"""Own the SQL transport lifetime; native HTTP hands own every capture and retry."""
import json
import os
from pathlib import Path
import selectors
import subprocess


def prepare(root, work, check, cleanup, context):
    config = Path(os.environ['SHRINE_SQL_CONFIG']).resolve()
    settings = json.loads(config.read_text())
    work.mkdir(parents=True, exist_ok=True)
    log = cleanup.enter_context((work / 'transport.log').open('w'))
    child = subprocess.Popen(['node', str(root / 'source.mjs'), str(config)],
                             stdout=subprocess.PIPE, stderr=log, text=True)

    def stop():
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        child.stdout.close()
    cleanup.callback(stop)
    with selectors.DefaultSelector() as ready:
        ready.register(child.stdout, selectors.EVENT_READ)
        if not ready.select(min(context['timeout'], 30)):
            raise RuntimeError('SQL source did not become ready; inspect transport.log')
        line = child.stdout.readline()
    if not line:
        raise RuntimeError('SQL source failed; inspect transport.log')
    port = json.loads(line)['port']
    # This is a captured transport address, not a second work registry. The
    # stable configured token/port allow the existing URL inputs to reconnect.
    endpoints = {name: {'url': f'http://127.0.0.1:{port}/{settings["token"]}/{name}',
                        'parameters': spec.get('parameters', {})}
                 for name, spec in settings['queries'].items()}
    bag = work / 'bag'
    bag.mkdir(exist_ok=True)
    (bag / 'endpoint.json').write_text(json.dumps(endpoints, indent=2) + '\n')
    return bag, []
