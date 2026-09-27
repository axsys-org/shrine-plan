import json
from pathlib import Path
import tempfile
import unittest
from fixtures import *
from observe import IO

class ObservationTests(unittest.TestCase):
    def test_native_request_and_replaceable_external_realization(self):
        w=world();io=IO(w);directory=Path(tempfile.mkdtemp())
        request_form=checked(w.evaluate('shadow_io/form'))['value']
        checked(w.write('make','/forms/physical_request',{'form':request_form}))
        c=checked(w.compile(REALIZE,exports=['realize/form']))
        checked(w.write('make','/forms/realization',{'form':c['exports']['realize/form']}))
        binding=checked(w.evaluate("(kook [['forms 'realization]])"))['value']
        checked(w.write('make','/realization',{'/sys/limb':binding,'origin_work':'/work/realization'}))
        verifier=checked(w.compile(VERIFY_FILE,exports=['verified']))
        for n in (1,2):
            file=directory/str(n)
            source=io.source('realization-'+str(n),'filesystem',{'path':str(file),'text':True},outbound=True)
            result=checked(w.write('poke','/realization',{'driver':source['path'],'operation':'write',
                'arguments':{'text':'native realization verified'},'episode':str(n)}))
            self.assertTrue(w.exact('/requests/realized'))
            self.assertFalse(file.exists())
            self.assertEqual(result['effects'][0]['path'],'/io/dispatch')
            self.assertTrue(io.dispatch('/requests/realized')['dispatched'])
            observed=io.sample(source['path']);snapshot=w.exact(observed['subject_record'])
            verified=checked(w.evaluate('(verified observed)',module=verifier['module'],inputs={
                'observed':{'$record':{'path':observed['subject_record'],'case':snapshot['case']}}}))
            self.assertEqual(verified['render'],'1')
            self.assertEqual(fields_of(w.exact('/realization'))['origin_work'],'/work/realization')
            self.assertFalse(io.dispatch('/requests/realized')['dispatched'])
        self.assertEqual((directory/'1').read_text(),(directory/'2').read_text())

    def test_binary_text_is_artifact_and_direct_invalid_text_is_actionable(self):
        w=world();io=IO(w);sequence=w.sequence
        with self.assertRaisesRegex(ValueError,'NUL'):
            w.write('make','/bad-text',{'v':'a\0b'})
        self.assertEqual(sequence,w.sequence)
        receipt=io.observe({'source':'binary-fixture','subject':'tool-output','value':'a\0b',
            'availability':'available','coverage':'complete'})
        observed=fields_of(w.exact(receipt['path']))
        self.assertNotIn('value',observed)
        self.assertEqual(json.loads(Path(observed['value_artifact']['path']).read_text()),'a\0b')

    def test_observations_preserve_raw_scope_and_noop(self):
        w=world(); io=IO(w)
        p=Path(tempfile.mkdtemp())/'config.txt';p.write_text('one')
        src=io.source('observation-fixture','filesystem',{'path':str(p),'text':True})
        a=io.sample(src['path']); head=a['subject_record']; before=w.exact(head)['case']
        io.sample(src['path']);self.assertEqual(w.exact(head)['case'],before)
        p.unlink();gone=io.sample(src['path'])
        self.assertEqual(fields_of(w.exact(head))['availability'],'deleted')
        self.assertEqual(fields_of(w.exact(a['path']))['availability'],'available')
        original={'source':'external-db','subject':'row:17','value':{'n':3},'availability':'available','coverage':'partial'}
        first=io.observe(original,event_id='partial-fixture')
        again=io.observe(original,event_id='partial-fixture');self.assertTrue(again['duplicate'])
        with self.assertRaises(ValueError):io.observe({**original,'value':4},event_id='partial-fixture')
        io.observe({**original,'value':None,'availability':'unavailable','coverage':'unknown'})
        self.assertEqual(fields_of(w.exact(first['path']))['coverage'],'partial')

    def test_request_is_committed_before_execution_and_report_is_not_fulfillment(self):
        w=world();io=IO(w)
        p=Path(tempfile.mkdtemp())/'realized.txt'
        source=io.source('outbound-fixture','filesystem',{'path':str(p)},outbound=True)
        form=checked(w.evaluate('shadow_io/form'))['value']
        checked(w.write('make','/forms/request',{'form':form}))
        binding=checked(w.evaluate("(kook [['forms 'request]])"))['value']
        checked(w.write('make','/requests/write',fields={'driver':source['path'],'operation':'write',
            'arguments':{'text':'native intent','expected_sha256':None},'status':'PENDING','episode':'one',
            '/sys/limb':binding}))
        self.assertFalse(p.exists())
        result=io.dispatch('/requests/write');self.assertTrue(result['dispatched'])
        self.assertEqual(p.read_text(),'native intent')
        request=fields_of(w.exact('/requests/write'))
        self.assertEqual(request['status'],'REPORTED');self.assertNotIn('fulfilled',request)
        self.assertFalse(io.dispatch('/requests/write')['dispatched'])
        observed=io.sample(source['path']);self.assertTrue(w.exact(observed['path']))
        checked(w.write('poke','/requests/write',{'report_attempt':'old','reported_outcome':'failure'}))
        self.assertEqual(fields_of(w.exact('/requests/write'))['reported_outcome'],'success')
        cold=io.source('observation-only','filesystem',{'path':str(p)})
        checked(w.write('make','/requests/denied',{'driver':cold['path'],'operation':'write','arguments':{'text':'no'},'status':'PENDING','/sys/limb':binding}))
        self.assertFalse(io.dispatch('/requests/denied')['dispatched'])
        self.assertEqual(p.read_text(),'native intent')

    def test_changed_request_cannot_accept_stale_completion(self):
        w=world()
        form=checked(w.evaluate('shadow_io/form'))['value']
        checked(w.write('make','/forms/request-stale',{'form':form}))
        binding=checked(w.evaluate('(kook [[($ts "forms") ($ts "request-stale")]])'))['value']
        checked(w.write('make','/requests/stale',{'driver':'/source','operation':'run','arguments':{'n':1},
            'status':'PENDING','episode':'one','/sys/limb':binding}))
        checked(w.write('poke','/requests/stale',{'claim':'attempt-one'}))
        checked(w.write('poke','/requests/stale',{'arguments':{'n':2}}))
        checked(w.write('poke','/requests/stale',{'report_attempt':'attempt-one','reported_outcome':'success'}))
        self.assertEqual(fields_of(w.exact('/requests/stale'))['status'],'NEEDS_REVIEW')
        self.assertNotIn('reported_outcome',fields_of(w.exact('/requests/stale')))

    def test_native_outward_effect_survives_adapter(self):
        w=world()
        code='''-  sept [order=10]
-  shrine_types [order=20]
-  lain [order=30]
+  outward
  +  talk
    \\  b=bowl cur=myth add=myth
    ^  yell
    (yell [[['io 'custom] (writ/make add)]] cur)
  +  form
    ^  form
    def_form.set_talk(outward/talk)
'''
        c=checked(w.compile(code,exports=['outward/form']))
        checked(w.write('make','/forms/outward',{'form':c['exports']['outward/form']}))
        binding=checked(w.evaluate("(kook [['forms 'outward]])"))['value']
        checked(w.write('make','/emitter',{'/sys/limb':binding}))
        value=checked(w.evaluate('[7 8 9]'))['value']
        r=checked(w.write('poke','/emitter',{'arbitrary':value}))
        self.assertEqual(r['effects'][0]['path'],'/io/custom')
        self.assertIn('$native',r['effects'][0]['native'])
        self.assertTrue(w.evaluate('effect',inputs={'effect':r['effects'][0]['native']})['ok'])

if __name__=='__main__':unittest.main()
