import unittest
import json
from fixtures import *
from observe import IO
from context import Connections

class ContextIdentityTests(unittest.TestCase):
    def test_foreign_and_historical_references_do_not_borrow_local_understanding(self):
        def record(path, case=1, **fields):
            return {'path':path,'case':case,'slots':[{'key':[k],'value':v} for k,v in fields.items()]}
        c=Connections('here')
        c.update(record('/evidence',case=2,statement='Current local evidence',anchors=[{'path':'/unrelated'}]))
        c.update(record('/unrelated',statement='Must not follow an older evidence version here'))
        c.update(record('/work',used=[{'path':'/evidence','case':1},
            {'path':'/evidence','case':2,'world':'elsewhere'},
            {'path':'/evidence','external_world':'/archive/old-world'}]))
        items=c.context(['/work'])['items']
        self.assertEqual(len(items),3)
        self.assertEqual({i['availability'] for i in items},{'historical_reference','external_world'})
        self.assertTrue(all(i['category']=='reference_only' and not i['summary'] for i in items))
        self.assertTrue(all(i['path']=='/evidence' for i in items))
        local=c.context(['/evidence'])['items']
        self.assertFalse(any(e.get('external') and e.get('direction')=='reverse' for i in local for e in i['route']))
        c.update(record('/work',used=[{'path':'/evidence','world':'here','case':2}]))
        items=c.context(['/work'])['items']
        self.assertEqual(items[0]['summary']['statement'],'Current local evidence')
        self.assertTrue(any(i['path']=='/unrelated' for i in items))

    def test_missing_namespace_spines_do_not_displace_connected_questions(self):
        c=Connections()
        c.update({'path':'/deep/work','case':1,'slots':[{'key':['anchors'],'value':[{'path':'/missing'}]},
            {'key':['related'],'value':[{'path':'/deep/question'}]}]})
        c.update({'path':'/deep/question','case':1,'slots':[{'key':['question'],'value':'Unfinished'}]})
        first=c.context(['/deep/work'],limits={'items':1})
        self.assertEqual(first['items'][0]['path'],'/deep/question')
        self.assertEqual(first['items'][0]['category'],'potentially_relevant_unfinished')
        rest=c.context(['/deep/work'],cursor=first['cursor'])['items']
        self.assertEqual([i['path'] for i in rest],['/missing'])
        self.assertEqual(rest[0]['availability'],'unavailable')
        self.assertTrue(c.context(['/deep'])['items']) # explicit parent browsing remains useful

class UnderstandingTests(unittest.TestCase):
    def test_unfinished_work_and_reorganization_are_navigable(self):
        w=world()
        checked(w.write('make','/engineering/work/first',{'objective':'Understand input validity','subjects':[{'path':'/inputs'}]}))
        checked(w.write('make','/engineering/question',{'question':'Which failures invalidate this claim?',
            'anchors':[{'path':'/inputs'}],'origin_work':[{'path':'/engineering/work/first'}],
            'related':[{'path':'/engineering/sibling'}],'applicability':'UNESTABLISHED'}))
        fresh=Connections()
        for event in w.events_list:fresh.ingest(event)
        found=fresh.context(['/inputs'])['items']
        q=next(i for i in found if i['path']=='/engineering/question')
        self.assertEqual(q['category'],'potentially_relevant_unfinished')
        self.assertTrue(q['route'])
        for action in ('generalizes','specializes','derived_from'):
            checked(w.write('make','/engineering/'+action,{'question':'Proposed successor; broader scope remains unresolved',
                action:[{'path':'/engineering/question','case':w.exact('/engineering/question')['case']}]}))
        old=w.exact('/engineering/question')
        checked(w.write('poke','/engineering/question',{'applicability':'RETIRED','successors':[{'path':'/engineering/generalizes'}]}))
        self.assertEqual(fields_of(w.read('/engineering/question',case=old['case'])['records'][0])['applicability'],'UNESTABLISHED')
        self.assertNotIn('CURRENT',fields_of(w.exact('/engineering/generalizes')).values())

    def test_scoped_evidence_native_reconsideration_and_recovery(self):
        w=world();io=IO(w)
        outcome=io.execute('process',{},'run',{'argv':['python3','-c','assert 2 + 3 == 5']})
        self.assertEqual(outcome['reported_outcome'],'success')
        evidence=io.observe({'source':'tests','subject':'arithmetic','kind':'execution','value':outcome,
            'availability':'available','coverage':'complete'})
        ep='['+' '.join("($ts "+json.dumps(x)+")" for x in evidence['path'][1:].split('/'))+']'
        code='''-  sept [order=10]
-  shrine_types [order=20]
-  lain [order=30]
-  shadow_forms [order=40]
+  lesson
  +  talk
    \\  b=bowl cur=myth add=myth
    ^  yell
    ?  (eq add.txt_at(['action]) "assess")
       (yell [] (shadow_forms/establish "arithmetic at observed basis" [['evidence]] [] b cur))
    (shadow_forms/statement_talk ['notices] b cur add)
  +  form
    ^  form
    def_form.set_talk(lesson/talk).set_hear((shadow_forms/reconsider ['notices]))
  +  crew
    ^  cpail
    =  > c (mop/sing[path dep lt_pith] ['evidence] (dep .x EVIDENCE))
    (cpail c.put(['basis] (dep .x ['lesson_basis])))
  +  binding
    ^  kook
    (kook [['forms 'lesson]])
'''.replace('EVIDENCE',ep)
        c=checked(w.compile(code,exports=['lesson/form','lesson/crew','lesson/binding']))['exports']
        checked(w.write('make','/forms/lesson',{'form':c['lesson/form']}))
        checked(w.write('make','/lesson_basis',{'input_revision':1}))
        checked(w.write('make','/lesson',{'statement':'The checked arithmetic holds in this scope','applicability':'UNESTABLISHED',
            'evidence':[evidence],'/sys/limb':c['lesson/binding'],'/sys/crew':c['lesson/crew']}))
        checked(w.write('poke','/lesson',{'action':'assess'}))
        self.assertEqual(fields_of(w.exact('/lesson'))['applicability'],'CURRENT')
        first=w.exact('/lesson')
        r=checked(w.write('poke','/lesson_basis',{'input_revision':2}))
        self.assertEqual(fields_of(w.exact('/lesson'))['applicability'],'NEEDS_REVIEW')
        self.assertTrue(w.exact('/notices/lesson'))
        self.assertEqual(fields_of(w.read('/lesson',case=first['case'])['records'][0])['applicability'],'CURRENT')
        checked(w.write('poke','/lesson',{'action':'assess'}))
        self.assertEqual(fields_of(w.exact('/lesson'))['applicability'],'CURRENT')
        checked(w.write('poke','/lesson',{'related':[{'path':'/unrelated'}]}))
        self.assertEqual(fields_of(w.exact('/lesson'))['applicability'],'CURRENT')
        self.assertEqual(fields_of(w.exact(evidence['path']))['value'],outcome)

    def test_soft_tags_do_not_install_dependencies(self):
        w=world();checked(w.write('make','/tagged/a',{'question':'Potential relationship','tags':['shared']}))
        checked(w.write('make','/tagged/b',{'statement':'Independent','tags':['shared']}))
        before=w.exact('/tagged/a')['case']
        checked(w.write('poke','/tagged/b',{'changed':True}))
        self.assertEqual(w.exact('/tagged/a')['case'],before)
        self.assertFalse(w.exact('/tagged/a')['crew'])
        items=w.connections.context(['/tagged/b'],include_tags=True)['items']
        self.assertTrue(any(i['path']=='/tagged/a' and any(e['relation']=='shared_tag' for e in i['route']) for i in items))

if __name__=='__main__':unittest.main()
