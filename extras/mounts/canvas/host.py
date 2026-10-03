"""Lifecycle hook for Canvas's authenticated local browser surface."""
import importlib.util
import json
import os
import plistlib
from pathlib import Path
import secrets
import shlex
import sys
import threading

def private(path, text):
    path = Path(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(text)

def install_launcher(applications, connection):
    """One normal macOS application opens the current world in the default browser."""
    app = Path(applications) / 'Grove Canvas.app'
    info = app / 'Contents/Info.plist'
    identifier = 'org.axsys.grove-canvas.local'
    if app.exists() and (not info.exists() or plistlib.loads(info.read_bytes()).get('CFBundleIdentifier') != identifier):
        raise ValueError('Existing Grove Canvas application belongs to another installation.')
    binary = app / 'Contents/MacOS/Grove Canvas'
    binary.parent.mkdir(parents=True, exist_ok=True)
    info.write_bytes(plistlib.dumps({
        'CFBundleIdentifier':identifier, 'CFBundleName':'Grove Canvas',
        'CFBundleDisplayName':'Grove Canvas', 'CFBundleExecutable':'Grove Canvas',
        'CFBundlePackageType':'APPL', 'CFBundleVersion':'1', 'LSUIElement':True,
    }))
    # Read the current private connection at launch; never bake a token into
    # the application bundle or rely on a stale browser tab's copied URL.
    binary.write_text('#!/bin/sh\n' +
        'canvas_url=$(/usr/bin/plutil -extract url raw -o - ' + shlex.quote(str(connection)) + ') || exit 1\n' +
        'case "$canvas_url" in\n' +
        '  http://127.0.0.1:*/canvas\\#session=*) exec /usr/bin/open "$canvas_url" ;;\n' +
        '  *) exit 1 ;;\n' +
        'esac\n')
    binary.chmod(0o755)
    return app

def prepare(root, work, check, cleanup, context):
    world = context.get('world')
    if not world:
        raise ValueError('Canvas requires --world and --protocol canvas/1; use the pinned native owner.')
    root, world = Path(root), Path(world)
    spec = importlib.util.spec_from_file_location('canvas_webhost', root / 'webhost.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    authority = secrets.token_hex(32)
    private(world / 'src/canvas-authority', authority)
    session = module.browser_session(world / 'browser-session.json')
    server = module.Server(root, 'http://127.0.0.1:' + str(context['port']), authority,
                           int(os.environ.get('CANVAS_PORT','8141')), session=session)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    def close():
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    cleanup.callback(close)
    url = server.origin + '/canvas#session=' + server.bootstrap
    private(world / 'canvas-admin.json', json.dumps({'url':url}))
    # Disposable acceptance worlds must not replace the user's current link.
    if not check and os.environ.get('CANVAS_EPHEMERAL') != '1':
        private(world.parent / 'canvas-current.json', json.dumps({'url':url,'world':str(world)}))
        private(world.parent / 'Grove Canvas.webloc', plistlib.dumps({'URL':url}).decode())
        if sys.platform == 'darwin':
            install_launcher(Path.home() / 'Applications', world.parent / 'canvas-current.json')
    private(world / 'canvas-agent.json', json.dumps({'url':server.origin, 'token':server.agent}))
    print(f'Canvas: {server.origin}/canvas; open Grove Canvas in Applications to connect a browser.', flush=True)
    return root, []
