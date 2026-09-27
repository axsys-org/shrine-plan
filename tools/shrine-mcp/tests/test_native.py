import copy
import unittest
from fixtures import *

class NativeTests(unittest.TestCase):
    def test_helm_compatibility_entrypoint(self):
        w=world()
        code='''-  sept [order=10]
-  shrine_types [order=20]
-  shrine [order=30]
-  lain [order=40]
-  helm [order=50]
+  compatibility
  ^  nat
  =  [h=helm ds=row[duty]] (helm/boot sov/new)
  =  > t (task/vine ['example] (writ/make myth/new))
  =  [a=helm b=row[duty] c=rsvp d=maybe[iota]] (helm/exec .none t h)
  =  [e=helm f=row[duty] g=rsvp i=maybe[iota] fx=row[move]] (helm/exec_effects .none t h)
  (equal [a b c d] [e f g i])
'''
        compiled=checked(w.compile(code,exports=['compatibility']))
        self.assertEqual(checked(w.evaluate('compatibility',module=compiled['module']))['render'],'1')

    def test_actual_compile_install_crew_and_cascade(self):
        w=world(); c=custom()
        checked(w.write('poke','/inputs',{'n':7}))
        self.assertEqual(fields_of(w.exact('/projection'))['n'],7)
        prior=w.exact('/projection')['case']
        checked(w.write('poke','/inputs',{'noise':93}))
        self.assertEqual(w.exact('/projection')['case'],prior)
        checked(w.write('make','/projection/child',{'question':'Unfinished native work'}))
        self.assertTrue(w.exact('/projection/child'))
        checked(w.write('make','/replacement',{'n':21}))
        checked(w.write('poke','/projection',slots=[{'key':['sys','crew'],'value':c['exports']['demo/crew2']}]))
        self.assertEqual(w.exact('/projection')['behaviors'],['/forms/custom'])
        before=w.exact('/projection')['case']
        checked(w.write('poke','/inputs',{'n':99}))
        self.assertEqual(w.exact('/projection')['case'],before)
        checked(w.write('poke','/replacement',{'n':22}))
        self.assertEqual(fields_of(w.exact('/projection'))['n'],22)

    def test_arbitrary_native_values_and_opaque_slots(self):
        w=world(); value=checked(w.evaluate('[1 2 3]'))['value']
        checked(w.write('make','/value-test',slots=[{'key':['a/b'],'value':value},{'key':['a','b'],'value':False}]))
        record=w.exact('/value-test')
        slots={tuple(s['key']):s for s in record['slots']}
        self.assertNotEqual(slots[('a/b',)]['value'],False)
        self.assertIs(slots[('a','b')]['value'],False)
        checked(w.write('make','/value-copy',slots=[{'key':['retained'],'value':slots[('a/b',)]['ref']}]))
        self.assertEqual(w.exact('/value-copy')['slots'][0]['render'],slots[('a/b',)]['render'])
        r=checked(w.evaluate('(add n 1)',inputs={'n':checked(w.evaluate('41'))['value']}))
        self.assertEqual(r['render'],'42')
        numeric=['numbers',{'tag':'u','value':123}]
        checked(w.write('make',numeric,{'v':'preserved'}))
        self.assertEqual(w.read(numeric)['records'][0]['path_segments'],numeric)

    def test_whole_native_record_and_world_reference_guard(self):
        w=world()
        record=checked(w.evaluate("(myth/sing ['hello] (pails/t \"native\"))"))['value']
        checked(w.write('make','/whole-record',record=record))
        self.assertEqual(fields_of(w.exact('/whole-record'))['hello'],'native')
        foreign=copy.deepcopy(record); foreign['$native']['world']='another-world'
        with self.assertRaises(ValueError):w.write('make','/foreign',record=foreign)

    def test_invalid_wire_input_preserves_native_continuation(self):
        w=world();seq=w.sequence
        w.native.proc.stdin.write('{malformed\n');w.native.proc.stdin.flush()
        response=w.native.responses.get(timeout=5)
        self.assertFalse(response['ok'])
        self.assertEqual(w.sequence,seq)
        self.assertTrue(w.evaluate('42')['ok'])

    def test_guards_missing_forms_and_failed_compilation(self):
        w=world(); c=custom()
        record=w.exact('/forms/custom')
        self.assertFalse(w.write('poke','/forms/custom',{},expected_case=record['case']+1)['ok'])
        bad=w.compile('+  invalid\n  ^  nat\n  missing_name\n')
        self.assertFalse(bad['ok'])
        self.assertEqual(w.exact('/forms/custom')['case'],record['case'])
        missing=checked(w.evaluate("(kook [['missing 'form]])"))['value']
        r=w.write('make','/missing-form-user',slots=[{'key':['sys','limb'],'value':missing}])
        self.assertFalse(r['ok'])
        self.assertFalse(w.exact('/missing-form-user'))
        self.assertFalse(w.compile('-  lain\n+  wrong_type\n  ^  form\n  7\n')['ok'])

    def test_pinned_record_input_and_historical_scope(self):
        w=world(); checked(w.write('make','/historical',{'n':31}))
        first=w.exact('/historical')
        checked(w.write('poke','/historical',{'n':90}))
        evaluated=checked(w.evaluate("original.nat_at(['n] 0)",inputs={'original':{'$record':{'path':['historical'],'case':first['case']}}}))
        self.assertEqual(evaluated['render'],'31')
        self.assertEqual(fields_of(w.read('/historical',case=first['case'])['records'][0])['n'],31)
        self.assertTrue(w.exact(evaluated['receipt']['path']))

    def test_request_identity_and_restart(self):
        w=world(); checked(w.write('make','/restart-value',{'v':3},request_id='restart-write'))
        duplicate=w.write('make','/restart-value',{'v':3},request_id='restart-write')
        self.assertTrue(duplicate['duplicate'])
        with self.assertRaises(ValueError): w.write('make','/restart-value',{'v':4},request_id='restart-write')
        w.native.close()
        from native import NativeProcess
        w.native=NativeProcess(w.directory/'native',WISP,w.directory/'engine',SEED)
        self.assertEqual(w.native.ready['sequence'],w.sequence)
        self.assertEqual(fields_of(w.exact('/restart-value'))['v'],3)
        self.assertTrue(w.exact('/forms/custom'))

    def test_zz_crash_before_native_commit_keeps_failed_attempt(self):
        import fixtures
        from native import now
        from records import digest
        w=world(); sequence=w.sequence
        payload={'op':'make','path':['must_not_replay'],'slots':[]}
        entry={'kind':'begin','id':'crash-attempt','sequence':sequence+1,'at':now(),
            'work':None,'signature':digest(payload),'payload':{**payload,'sequence':sequence+1}}
        w._append(entry)
        with w.events_log.open('ab') as f:f.write(b'{"torn":')
        directory=w.directory;w.close()
        fixtures._world=World(directory,WISP,SEED)
        recovered=fixtures._world
        self.assertEqual(recovered.sequence,sequence+1)
        self.assertFalse(recovered.completed['crash-attempt'][1]['ok'])
        self.assertFalse(recovered.exact('/must_not_replay'))
        self.assertTrue(list(directory.glob('torn-tail-*')))

if __name__=='__main__':unittest.main()

class CascadeTests(unittest.TestCase):
    def test_nonsettling_cycle_is_reported(self):
        w=world()
        source='''-  sept [order=10]
-  shrine_types [order=20]
-  lain [order=30]
+  cyclic
  +  hear
    \\  b=bowl cur=myth changed=row[dep]
    ^  yell
    (yell [] cur.put(['n] (pails/n cur.nat_at(['n] 0).inc)))
  +  form
    ^  form
    def_form.set_hear(cyclic/hear)
'''
        c=checked(w.compile(source,exports=['cyclic/form']))
        checked(w.write('make','/forms/cyclic',{'form':c['exports']['cyclic/form']}))
        binding=checked(w.evaluate("(kook [['forms 'cyclic]])"))['value']
        for name,other in [('a','b'),('b','a')]:
            crew=checked(w.evaluate("(cpail (mop/sing[path dep lt_pith] ['peer] (dep .x ['cycle '"+other+"])))"))['value']
            activation=w.write('make','/cycle/'+name,{'/sys/limb':binding,'/sys/crew':crew})
        result=activation if not activation['ok'] else w.write('poke','/cycle/a',{'n':40})
        self.assertFalse(result['ok']);self.assertEqual(result['error'],'native_cascade_limit')
        # Explicitly retire the test's invalid wiring so later tasks can proceed.
        empty=checked(w.evaluate('(cpail (mop/empty))'))['value']
        w.write('poke','/cycle/a',{'/sys/crew':empty})
        w.write('poke','/cycle/b',{'/sys/crew':empty})
