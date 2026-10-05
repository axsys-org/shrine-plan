"""Transport gates for the small proof; native and browser execution tested separately."""
import http.cookiejar,importlib.util,json,tempfile,threading,time,unittest,urllib.request,urllib.error
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('proof_host',ROOT/'webhost.py');host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)
class Proof(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.server=host.Server(ROOT/'proof',self.tmp.name,1,'test-authority',0)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()
    def test_native_styles_and_fonts_are_served(self):
        for path in ['/','/app.js','/interaction.mjs','/style.css',*host.transport.GOO_ASSETS]:
            with urllib.request.urlopen(self.server.origin+path) as r:
                self.assertEqual(r.status,200,path);self.assertGreater(len(r.read()),0,path)
    def test_conditional_frames_still_read_native_owner_and_require_session(self):
        opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        with self.assertRaises(urllib.error.HTTPError) as denied:opener.open(self.server.origin+'/api/read')
        self.assertEqual(denied.exception.code,401)
        opener.open(urllib.request.Request(self.server.origin+'/connect',b'{}',{'Origin':self.server.origin})).close()
        frame=self.frame()
        with patch.object(self.server,'call',return_value=(200,frame)) as native:
            with opener.open(self.server.origin+'/api/read') as r:etag=r.headers['ETag']
            conditional=urllib.request.Request(self.server.origin+'/api/read',headers={'If-None-Match':etag})
            with self.assertRaises(urllib.error.HTTPError) as unchanged:opener.open(conditional)
            self.assertEqual(unchanged.exception.code,304)
            self.assertEqual(unchanged.exception.read(),b'')
            frame['expected']='2'
            with opener.open(conditional) as changed:
                self.assertEqual(changed.status,200)
                self.assertNotEqual(changed.headers['ETag'],etag)
                self.assertEqual(json.load(changed)['expected'],'2')
            self.assertEqual(native.call_count,3)
    def test_stale_pointing_cannot_be_sent_to_author_as_current_evidence(self):
        frame=self.frame();frame['nodes'][0].update(expected='2',displayed='2')
        with patch.object(self.server,'call',return_value=(200,frame)),patch.object(host.model,'run') as author:
            result=self.server.gesture({'selected':{'subject':frame['nodes'][0]['id'],
                'occurrence':'exact-native-view:2','basis':{'expected':'1','displayed':'1'}},'text':'Change this'})
            for _ in range(100):
                if list(Path(self.tmp.name).glob('authoring/attempt-*.json')):break
                time.sleep(.01)
            self.assertEqual(self.server.jobs[result['id']]['status'],'error')
            self.assertIn('presentation changed',self.server.jobs[result['id']]['message'])
            author.assert_not_called()
    def test_no_cross_origin_mutation(self):
        req=urllib.request.Request(self.server.origin+'/api',b'{}',{'Origin':'https://unrelated.invalid','Content-Type':'application/json'})
        with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(req)
        self.assertEqual(error.exception.code,403)
    def test_native_images_do_not_grant_script_or_network_origins(self):
        with urllib.request.urlopen(self.server.origin+'/') as response:
            policy=response.headers['Content-Security-Policy']
        self.assertIn("img-src 'self' data:",policy)
        self.assertIn("script-src 'self';",policy)
        self.assertIn("connect-src 'self';",policy)
        self.assertNotIn('unsafe-eval',policy)
    def frame(self):
        n={'id':'/0x11/app/medium/a','label':'A','pattern':'a','source':'','inputs':[]}
        return {'nodes':[n],'expected':'1','features':['literal-properties']}
    def test_proof_uses_one_author_without_router_or_jev(self):
        frame=self.frame();candidate={'intent':'Still open','edits':[]};done=threading.Event()
        def run(*a):done.set();return candidate,{'model':'test-only'}
        with patch.object(self.server,'call',return_value=(200,frame)),patch.object(host.model,'run',side_effect=run) as author:
            result=self.server.gesture({'selected':{'subject':frame['nodes'][0]['id']},'text':'Test'})
            self.assertTrue(done.wait(2))
            for _ in range(100):
                if self.server.jobs[result['id']]['status']=='done':break
                time.sleep(.01)
            self.assertEqual(self.server.jobs[result['id']]['status'],'done');self.assertEqual(author.call_count,1)
            # Wait for the bounded factual receipt so the temporary dir is not removed early.
            for _ in range(100):
                if list(Path(self.tmp.name).glob('authoring/attempt-*.json')):break
                time.sleep(.01)
    def test_proof_target_is_native_identity_and_reasoning_is_bounded(self):
        frame=self.frame();target=frame['nodes'][0]['id']
        context={'proof':True,'frame':frame,'gesture':{'selected':{'subject':target}}}
        with patch.object(host.model,'completion',return_value=({'content':'{"intent":"Open", "edits":[]}'},{})) as completion:
            host.model.run(context,[],threading.Event(),self.tmp.name)
        options=completion.call_args.kwargs
        edit=options['response_format']['json_schema']['schema']['properties']['edits']
        self.assertEqual(edit['maxItems'],1)
        self.assertEqual(edit['items']['properties']['target']['enum'],[target])
        self.assertEqual(options['reasoning'],{'effort':'minimal'})
    def test_construction_author_may_only_use_supplied_native_addresses(self):
        frame=self.frame();frame['features'] += ['native-definition-actions','definition-scope']
        target=frame['nodes'][0]['id'];new='/0x11/app/medium/new'
        context={'proof':True,'frame':frame,'new_subjects':[new],
                 'gesture':{'selected':{'subject':target}}}
        with patch.object(host.model,'completion',return_value=({'content':'{"intent":"Open", "edits":[]}'},{})) as completion:
            host.model.run(context,[],threading.Event(),self.tmp.name)
        options=completion.call_args.kwargs
        edits=options['response_format']['json_schema']['schema']['properties']['edits']
        self.assertEqual(edits['items']['properties']['target']['enum'],[target,new])
        self.assertEqual(edits['maxItems'],2)
        self.assertEqual(options['reasoning'],{'effort':'medium'})
        unauthorized={'intent':'Rejected','edits':[{'target':'/0x11/elsewhere'}]}
        with patch.object(host.model,'completion',return_value=({'content':json.dumps(unauthorized)},{})):
            with self.assertRaisesRegex(RuntimeError,'outside this construction boundary'):
                host.model.run(context,[],threading.Event(),self.tmp.name)

    def test_explicit_intent_overrides_exact_precedent(self):
        f=self.frame();inputs=[{'subject':'a','slots':[],'occurrence':''}]
        pending={'id':'p','label':'Connection','relation':True,'inputs':inputs}
        known={'id':'k','label':'Known','relation':True,'inputs':inputs,'authored':True,'ready':True,'pattern':'definition'}
        f['nodes'] += [pending,known]
        self.assertIsNotNone(host.model.exact_connection(f,{'selected':{'subject':'p'}}))
        self.assertIsNone(host.model.exact_connection(f,{'selected':{'subject':'p'},'text':'Different meaning'}))
        pending['description']='Different meaning'
        self.assertIsNone(host.model.exact_connection(f,{'selected':{'subject':'p'}}))
    def test_author_context_keeps_native_source_and_actions_without_pixel_html(self):
        frame=self.frame();node=frame['nodes'][0]
        node.update(source='native source',view={'html':'pixel-specific artifact',
            'occurrences':[{'id':'action-id','control':'1.0','kind':'action'}]})
        context={'proof':True,'frame':frame,'gesture':{'selected':{'subject':node['id']}}}
        with patch.object(host.model,'completion',return_value=({'content':'{"intent":"Open", "edits":[]}'},{})) as completion:
            host.model.run(context,[],threading.Event(),self.tmp.name)
        sent=completion.call_args.args[0][1]['content']
        self.assertIn('native source',sent);self.assertIn('action-id',sent)
        self.assertNotIn('pixel-specific artifact',sent)
        self.assertIn('html',node['view'])
    def test_ambiguous_precedents_are_not_silently_selected(self):
        inputs=[{'subject':'a','slots':[],'occurrence':''}]
        f={'nodes':[{'id':'p','relation':True,'inputs':inputs}]+[{'id':str(i),'label':'Same name','relation':True,'inputs':inputs,'authored':True,'ready':True,'pattern':str(i)} for i in range(2)]}
        self.assertIsNone(host.model.exact_connection(f,{'selected':{'subject':'p'}}))
if __name__=='__main__':unittest.main()
