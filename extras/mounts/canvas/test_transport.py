"""Transport regressions; native domain acceptance lives in tests.foil."""
import json
import http.cookiejar
import os
from pathlib import Path
import plistlib
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from types import SimpleNamespace
from unittest.mock import Mock
from webhost import Server, Handler, browser_session
from host import install_launcher
from mcp import Adapter

class TransportTests(unittest.TestCase):
    def setUp(self):
        self.server=Server(Path(__file__).parent,'http://127.0.0.1:1','private-authority')
        self.calls=[]
        def call(principal, operation, expected, event, body):
            self.calls.append((principal,operation,expected,event,body))
            return 200,b'{"transport_probe":true}'
        self.server.call=call
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
    def send(self,path,payload=None,headers=None):
        request=urllib.request.Request(self.server.origin+path,
            None if payload is None else json.dumps(payload).encode(),headers or {})
        try:
            with urllib.request.urlopen(request) as response:return response.status,response.read(),response.headers
        except urllib.error.HTTPError as error:
            with error:return error.code,error.read(),error.headers
    def admin(self):return {'Cookie':self.server.cookie_name+'='+self.server.admin,'Origin':self.server.origin}
    def agent(self):return {'Authorization':'Bearer '+self.server.agent}
    def test_read_requires_authority(self):
        self.assertEqual(self.send('/api')[0],401)
        self.assertEqual(self.calls,[])
    def test_bootstrap_sets_httponly_cookie(self):
        code,_,headers=self.send('/session',{'token':self.server.bootstrap},{'Origin':self.server.origin})
        self.assertEqual(code,200);self.assertIn('HttpOnly',headers['Set-Cookie'])
        self.assertIn(self.server.cookie_name+'=',headers['Set-Cookie'])
        self.assertIn('Max-Age=7776000',headers['Set-Cookie'])
        self.assertIn('SameSite=Strict',headers['Set-Cookie'])
    def test_bootstrap_rejects_wrong_origin(self):
        self.assertEqual(self.send('/session',{'token':self.server.bootstrap},{'Origin':'https://untrusted.invalid'})[0],403)
    def test_admin_mutation_requires_origin(self):
        self.assertEqual(self.send('/api',{'operation':'publish'},{'Cookie':self.server.cookie_name+'='+self.server.admin})[0],403)
        self.assertEqual(self.calls,[])
    def test_agent_cannot_publish(self):
        self.assertEqual(self.send('/api',{'operation':'publish'},self.agent())[0],403)
        self.assertEqual(self.calls,[])
    def test_agent_cannot_operate(self):
        self.assertEqual(self.send('/api',{'operation':'reserve'},self.agent())[0],403)
        self.assertEqual(self.send('/api',{'operation':'perform'},self.agent())[0],403)
        self.assertEqual(self.send('/api',{'operation':'construct'},self.agent())[0],403)
    def test_native_presentations_keep_principal_and_exact_target(self):
        body={'target':'/0x11/app/workspace/123'}
        self.assertEqual(self.send('/api',{'operation':'present','body':body},self.agent())[0],200)
        self.assertEqual(self.calls,[('agent','present','0','',body)])
    def test_shared_goo_assets_do_not_enable_explorer_routes(self):
        for route in ('/static/goo-reference.css','/static/goo-fonts.css','/static/goo-Sans400.ttf'):
            self.assertEqual(self.send(route)[0],200)
        self.assertEqual(self.send('/grove/dev',headers=self.admin())[0],404)
        self.assertEqual(self.calls,[])
    def test_principal_cannot_be_forged(self):
        self.assertEqual(self.send('/api',{'operation':'stage','principal':'administrator','expected':'9','event':'event','body':{}},self.agent())[0],200)
        self.assertEqual(self.calls[0][0],'agent')
    def test_stable_targets_are_forwarded_unchanged(self):
        body={'person':'/0x11/app/canvas/people/alex','equipment':'/0x11/app/canvas/equipment/camera_a'}
        self.send('/api',{'operation':'reserve','expected':'81','event':'stable','body':body},self.admin())
        self.assertEqual(self.calls,[('administrator','reserve','81','stable',body)])
    def test_large_request_rejected(self):
        self.assertEqual(self.send('/api',{'operation':'stage','body':{'text':'x'*70000}},self.admin())[0],413)
    def test_source_is_authenticated(self):self.assertEqual(self.send('/source')[0],401)
    def test_inspection_modules_are_served_as_javascript_without_authority(self):
        for route in ('/canvas-inspector.js','/inspection-state.mjs'):
            code,body,headers=self.send(route)
            self.assertEqual(code,200)
            self.assertEqual(headers['Content-Type'],'text/javascript')
            self.assertGreater(len(body),0)
        self.assertEqual(self.calls,[])
    def test_unknown_asset_cannot_read_files(self):self.assertEqual(self.send('/../host.py',headers=self.admin())[0],404)

class MCPTests(unittest.TestCase):
    def setUp(self):self.adapter=Adapter('/not-a-real-connection')
    def message(self,method,params=None):return self.adapter.handle(dict(jsonrpc='2.0',id=1,method=method,params=params or {}))
    def init(self):
        self.message('initialize',{'protocolVersion':'2025-06-18'})
        self.adapter.handle(dict(jsonrpc='2.0',method='notifications/initialized'))
    def test_initialization_required(self):self.assertIn('error',self.message('tools/list'))
    def test_surface_has_no_publication(self):
        self.init();tools=self.message('tools/list')['result']['tools']
        self.assertEqual([t['name'] for t in tools],['read','source','eval','continue_candidate'])
    def test_presentation_eval_is_ephemeral_native_operation(self):
        self.init();calls=[]
        self.adapter.call=lambda envelope:(calls.append(envelope) or False,{'installed':False})
        args=dict(target='/0x11/app/workspace/a',view='/0x11/gov/example/edit',revision='3',publication='7',source='edit =\n  @view')
        result=self.message('tools/call',dict(name='eval',arguments=args))
        self.assertFalse(result['result']['structuredContent']['installed'])
        self.assertEqual(calls,[dict(operation='evaluate',expected='0',body={'kind':'presentation',**args})])
        self.assertIn('error',self.message('tools/call',dict(name='eval',arguments={**args,'principal':'administrator'})))
        self.assertIn('error',self.message('tools/call',dict(name='eval',arguments={**args,'source':'é'*5000})))
    def test_publish_not_a_continuation(self):
        self.init();self.assertIn('error',self.message('tools/call',dict(name='continue_candidate',arguments=dict(operation='publish',expected='1',event='e',body={}))))
    def test_native_findings_return_unmodified(self):
        self.init();data={'commitments':[{'kind':'failed','statement':'retain exception'}]}
        self.adapter.call=lambda _: (False,data)
        self.assertEqual(self.message('tools/call',dict(name='read'))['result']['structuredContent'],data)
    def test_source_requires_pinned_revision(self):
        self.init();calls=[]
        self.adapter.call=lambda envelope:(calls.append(envelope) or False,{'files':[]})
        arguments={'target':'/0x11/gov/canvas/edit','revision':'3'}
        self.message('tools/call',dict(name='source',arguments=arguments))
        self.assertEqual(calls,[dict(operation='source',expected='0',body=arguments)])
        self.assertIn('error',self.message('tools/call',dict(name='source',arguments={'target':arguments['target']})))
    def test_mcp_subject_read_uses_the_canvas_native_projection(self):
        self.init();calls=[]
        def call(envelope):
            calls.append(envelope);return False,{'protocol':'canvas-surface/1','subject':envelope['body']['target']}
        self.adapter.call=call
        target='/0x11/app/workspace/opaque-id'
        result=self.message('tools/call',dict(name='read',arguments={'target':target}))
        self.assertEqual(result['result']['structuredContent']['subject'],target)
        self.assertEqual(calls,[{'operation':'present','expected':'0','body':{'target':target}}])
        self.assertIn('error',self.message('tools/call',dict(name='read',arguments={'operation':'perform'})))

class DisconnectTests(unittest.TestCase):
    def test_abandoned_response_never_reexecutes_or_reports_native_failure(self):
        for phase in ('headers','body'):
            with self.subTest(phase=phase):
                handler=Handler.__new__(Handler)
                handler.server=SimpleNamespace(call=Mock(return_value=(200,b'{"committed":true}')))
                handler.send_response=Mock();handler.send_header=Mock()
                handler.end_headers=Mock(side_effect=BrokenPipeError() if phase=='headers' else None)
                handler.wfile=SimpleNamespace(write=Mock(side_effect=ConnectionResetError()))
                handler.forward('administrator',{'operation':'perform','expected':'2','body':{}})
                handler.server.call.assert_called_once()
                handler.send_response.assert_called_once_with(200)
                self.assertTrue(handler.close_connection)

class BrowserSessionTests(unittest.TestCase):
    def test_session_survives_restart_and_other_ports_cannot_overwrite_it(self):
        jar=http.cookiejar.CookieJar()
        opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        servers=[]
        def start(session):
            server=Server(Path(__file__).parent,'http://127.0.0.1:1','authority',session=session)
            server.call=lambda *args:(200,b'{"connected":true}')
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            servers.append((server,thread));return server
        def connect(server):
            request=urllib.request.Request(server.origin+'/session',json.dumps({'token':server.bootstrap}).encode(),{'Origin':server.origin})
            with opener.open(request) as response:self.assertEqual(response.status,200)
        def read(server):
            with opener.open(server.origin+'/api') as response:self.assertEqual(response.status,200)
        try:
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'browser-session.json'
                session=browser_session(path)
                self.assertEqual(path.stat().st_mode & 0o777,0o600)
                original=start(session);connect(original)
                other=start(browser_session(Path(directory)/'other.json'));connect(other)
                self.assertNotEqual(original.cookie_name,other.cookie_name)
                read(original);read(other)
                resumed=start(browser_session(path))
                self.assertEqual(resumed.admin,original.admin)
                self.assertEqual(resumed.cookie_name,original.cookie_name)
                read(resumed)  # No second bootstrap, even on a different port.
                self.assertEqual(len(jar),2)
        finally:
            for server,thread in servers:
                server.shutdown();server.server_close();thread.join()

    def test_invalid_or_exposed_existing_session_is_not_silently_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'session.json';browser_session(path)
            original=path.read_bytes();path.chmod(0o644)
            with self.assertRaises(ValueError):browser_session(path)
            self.assertEqual(path.read_bytes(),original)
            path.chmod(0o600);path.write_text('{"version":999}')
            with self.assertRaises(ValueError):browser_session(path)
            self.assertEqual(path.read_text(),'{"version":999}')

    def test_session_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as directory:
            actual=Path(directory)/'real.json';browser_session(actual)
            link=Path(directory)/'link.json';link.symlink_to(actual)
            with self.assertRaises(OSError):browser_session(link)

    def test_launcher_reads_current_connection_without_containing_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'current connection.json'
            path.write_text('{"url":"http://127.0.0.1:8141/canvas#session=private-marker"}')
            app=install_launcher(Path(directory)/'Applications',path)
            info=plistlib.loads((app/'Contents/Info.plist').read_bytes())
            script=app/'Contents/MacOS'/info['CFBundleExecutable']
            self.assertTrue(os.access(script,os.X_OK))
            self.assertIn(str(path),script.read_text())
            self.assertIn('/usr/bin/open "$canvas_url"',script.read_text())
            self.assertNotIn('private-marker',script.read_text())
            self.assertEqual(install_launcher(app.parent,path),app)

    def test_launcher_does_not_replace_an_unrelated_application(self):
        with tempfile.TemporaryDirectory() as directory:
            app=Path(directory)/'Grove Canvas.app';app.mkdir()
            with self.assertRaises(ValueError):install_launcher(Path(directory),Path(directory)/'connection')

if __name__=='__main__':unittest.main()
