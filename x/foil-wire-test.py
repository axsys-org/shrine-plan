"""End-to-end editor protocol check using the real compiler and loopback TCP."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from foil_wire import Compiler, Server, ROOT
from eden_mounts import Mount
from mount_wire import MountWire

WISP = os.environ.get('WISP') or shutil.which('wisp')
if not WISP:
    raise SystemExit('Set WISP or enter nix develop')


def main():
    with tempfile.TemporaryDirectory(prefix='foil-wire-check-') as tmp:
        root = Path(tmp)
        src = root / 'src'
        src.mkdir()
        for folder in ('reaver', 'spec'):
            (src / folder).symlink_to(ROOT / 'src' / folder, target_is_directory=True)
        shutil.copytree(ROOT / 'src/foil', src / 'foil')
        dep = src / 'foil/editor_dependency.foil'
        dep.write_text('+ twice\n  \\ n=nat\n  ^ nat\n  | mul 2 n\n')
        fixture = src / 'foil/editor_fixture.foil'
        good = '''- sys/types
- editor_dependency
+ color
  + red :
  + blue :
  & #/red #/blue
+ answer
  ' A documented answer.
  ' ?= ((twice 3) 6)
  (twice 21)
'''
        fixture.write_text(good)
        mount = root / 'mount'
        mount.mkdir()
        (mount / 'main.foil').write_text('- editor_fixture\n+ mounted answer\n')
        mounted = Mount('fixture', mount, {'modules': {'apps/wire/main': 'main.foil'}})
        compiler = Compiler(WISP, src, [mounted], timeout=600)
        try:
            with Server(0, MountWire(compiler, [mounted])) as server:
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                port = server.server_address[1]
                def raw(data):
                    with socket.create_connection(('127.0.0.1', port), timeout=10) as sock:
                        sock.settimeout(600)
                        sock.sendall(data)
                        return json.loads(sock.makefile('rb').read())
                def req(op, module='editor_fixture', **kwargs):
                    started = time.monotonic()
                    result = raw(json.dumps(dict(op=op, module=module, **kwargs)).encode() + b'\n')
                    print(op, module, 'ok=' + str(result['ok']),
                          f'{time.monotonic() - started:.2f}s', flush=True)
                    return result
                def success(result):
                    assert result['ok'], result
                    return result
                try:
                    assert success(req('ping'))['server'] == 'foil-wire'
                    for invalid in (b'[]\n', b'{\n', b'{"op": []}\n', b'{"op":"wat"}\n',
                                    b'{"op":"compile","module":"../outside"}\n'):
                        assert not raw(invalid)['ok']
                    compiled = success(req('compile'))
                    assert compiled['lint_ok'], compiled
                    style = src / 'foil/editor_style.foil'
                    style.write_text('+ badName\n  1  \n')
                    findings = success(req('lint', module='editor_style'))['diags']
                    assert any(d.get('rule') == 'snake-case' and d['level'] == 'error'
                               and d['line'] == 1 and d['col'] > 0 for d in findings), findings
                    assert any(d.get('rule') == 'trailing-space' and d['level'] == 'warning'
                               and d['line'] == 2 and d['col'] == 4 for d in findings), findings
                    assert all(d['source'] == 'foil-lint' for d in findings), findings
                    assert not any(d.get('rule') in ('lapidary', 'ufcs-lift') for d in findings), findings
                    # Compile success does not discard style diagnostics.
                    styled = success(req('compile', module='editor_style'))
                    assert styled['lint_ok'] and any(d.get('rule') == 'snake-case' for d in styled['diags']), styled
                    # Lint does not require successful typechecking or valid imports.
                    style.write_text('- missing_module\n+ badName\n  missing_name\n')
                    assert any(d.get('rule') == 'snake-case'
                               for d in success(req('lint', module='editor_style'))['diags'])
                    broken = req('compile', module='editor_style')
                    assert not broken['ok'] and broken['lint_ok'], broken
                    assert any(d.get('rule') == 'snake-case' for d in broken['diags']), broken
                    style.write_text('+ bad_name\n  1\n')
                    fixed = success(req('lint', module='editor_style'))
                    assert not any(d.get('rule') in ('snake-case', 'trailing-space') for d in fixed['diags']), fixed
                    style.write_text('')
                    assert success(req('lint', module='editor_style'))['diags'] == []
                    style.write_text(')\n')
                    malformed = req('lint', module='editor_style')
                    assert not malformed['ok'] and malformed['diags'], malformed
                    assert malformed['diags'][0]['line'] == 1 and malformed['diags'][0]['col'] == 1, malformed
                    style.unlink()
                    assert not req('lint', module='editor_style')['ok']
                    assert success(req('eval', text='answer'))['value'] == '42'
                    assert 'color/read_str' in success(req('complete', prefix='color/'))['names']
                    assert success(req('eval', text='(maybe/is_some (color/read_str "red"))'))['value']
                    description = success(req('describe', name='answer'))
                    assert description['line'] == 7 and description['lede'] == 'A documented answer.', description
                    assert any('/editor_dependency/' in path for path in description['calls']), description
                    imported = success(req('describe', name='twice'))
                    assert imported['module'] == 'editor_dependency' and imported['line'] == 1, imported
                    assert Path(imported['file']).resolve() == dep.resolve(), imported
                    assert any('/editor_fixture/' in path for path in imported['called_by']), imported
                    success(req('describe', name='color.read_str'))
                    success(req('describe', name='maybe.some'))
                    assert success(req('doctest'))['passed'] == 1
                    assert success(req('eval', module='apps/wire/main', text='mounted'))['value'] == '42'
                    success(req('lint', module='apps/wire/main'))
                    # Changed dependencies invalidate callers even on an eval request.
                    dep.write_text(dep.read_text().replace('mul 2', 'mul 3'))
                    assert success(req('eval', text='answer'))['value'] == '63'
                    assert success(req('doctest'))['failed'] == 1
                    fixture.write_text(good + '+ broken\n  missing_name\n')
                    failure = req('compile')
                    assert not failure['ok'] and any(d['line'] > 0 for d in failure['diags']), failure
                    fixture.write_text(good)
                    assert success(req('eval', text='answer'))['value'] == '63'
                    dep.write_text('+ twice\n  missing_name\n')
                    failure = req('compile')
                    assert not failure['ok'] and failure['diags'][0]['module'] == 'editor_dependency', failure
                    dep.write_text('+ twice\n  \\ n=nat\n  ^ nat\n  | mul 2 n\n')
                    # Exercise the actual Neovim TCP client, including sequential requests.
                    if shutil.which('nvim'):
                        lua = root / 'client.lua'
                        lua.write_text('''vim.opt.runtimepath:prepend(vim.env.FOIL_NVIM)
require('foil').setup({wire_enabled=true, port=tonumber(vim.env.FOIL_PORT), timeout=600000})
local wire = require('foil.wire')
for _, request in ipairs({{op='ping'}, {op='eval', module='editor_fixture', text='answer'}}) do
  local ok, reply = wire.request_sync(request)
  assert(ok and reply.ok, vim.inspect(reply))
  if request.op == 'eval' then assert(reply.value == '42', vim.inspect(reply)) end
end
vim.cmd('edit ' .. vim.fn.fnameescape(vim.env.FOIL_FIXTURE))
local diag = require('foil.diag')
diag.compile()
assert(vim.wait(600000, function()
  return #vim.diagnostic.get(0, {namespace=diag.lint_ns}) > 0
end, 20), 'real compiler lint diagnostics did not reach Neovim')
assert(#vim.diagnostic.get(0, {namespace=diag.ns}) == 0, 'valid module has compiler errors')
assert(vim.diagnostic.get(0, {namespace=diag.lint_ns})[1].source == 'foil-lint')
vim.cmd('qa!')
''')
                        fixture.write_text(good + '+ badName\n  1  \n')
                        subprocess.run(['nvim', '--headless', '-u', 'NONE', '-i', 'NONE', '-n', '-l', str(lua)],
                                       env=dict(os.environ, FOIL_NVIM=str(ROOT / 'editor/foil-nvim'),
                                                FOIL_PORT=str(port), FOIL_FIXTURE=str(fixture)), check=True, timeout=600)
                    # Ownership changes alone invalidate the editor's cached context.
                    manifest = src / 'foil/modules.tsv'
                    inventory = manifest.read_text()
                    original = success(req('describe', module='stdlib/json', name='json'))
                    assert original['module'] == 'stdlib/json', original
                    manifest.write_text(inventory.replace(
                        'stdlib/json\tbase\tstdlib/base', 'stdlib/json\tbase\tmissing'))
                    changed = req('describe', module='stdlib/json', name='json')
                    assert not changed['ok'], changed
                    assert 'invalid-publication-owner' in changed.get('error', ''), changed
                    manifest.write_text(inventory)
                    restored = success(req('describe', module='stdlib/json', name='json'))
                    assert restored['module'] == original['module'], (original, restored)
                    success(req('compile', module='stdlib/runtime'))
                    assert 'grove/tag_kind/read_str' in success(req('complete', module='stdlib/runtime', prefix='grove/tag_kind/'))['names']
                finally:
                    server.shutdown()
                    thread.join()
        finally:
            compiler.close()
            print('Compiler log:', compiler.work / 'out.log', flush=True)
    print('FOIL-WIRE-CHECK-PASS', flush=True)


if __name__ == '__main__':
    main()
