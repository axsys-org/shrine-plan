import importlib.util, os, secrets, threading
from pathlib import Path

def prepare(root, work, check, cleanup, context):
    world = Path(context['world'])
    authority = secrets.token_hex(32)
    path = world / 'src/medium-authority'
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f: f.write(authority)
    if not (Path(root) / 'webhost.py').exists(): return root, []
    spec = importlib.util.spec_from_file_location('medium_webhost', Path(root) / 'webhost.py')
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    surface_name = os.environ.get('MEDIUM_SURFACE', 'proof')
    if surface_name not in ('proof', 'native'):
        raise ValueError('Unknown rendering boundary')
    surface = Path(root)/surface_name
    server = mod.Server(surface, world, context['port'], authority, int(os.environ.get('MEDIUM_PORT', '8161')))
    server.native_ready = context.get('native_ready')
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    cleanup.callback(server.server_close); cleanup.callback(server.shutdown)
    if surface_name == 'native':
        spec = importlib.util.spec_from_file_location('medium_native_author', Path(root) / 'native_agent.py')
        author = importlib.util.module_from_spec(spec); spec.loader.exec_module(author)
        server.native_author = author.Runner(world,context['port'])
        server.native_author.native_ready = context.get('native_ready')
        server.native_author.start()
        cleanup.callback(server.native_author.close)
    print('Native medium: ' + server.origin, flush=True)
    return root, []
