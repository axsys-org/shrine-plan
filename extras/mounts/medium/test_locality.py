import unittest
from locality import context

class LocalityTest(unittest.TestCase):
    def setUp(self):
        self.scene={'blocks':[
            {'id':'frame','part':'frame','rect':{'x':0,'y':0,'w':400,'h':300}},
            {'id':'bar','part':'shape','shape':'rectangle','parent':'frame','rect':{'x':40,'y':80,'w':100,'h':30},'mapping':{'width':'duration'}},
            {'id':'board','part':'board','rect':{'x':450,'y':10,'w':200,'h':250},'nativeCollection':'/tasks'},
            {'id':'far','part':'table','rect':{'x':2000,'y':0,'w':200,'h':300}},
            {'id':'other','part':'shape','workspace':'maker2','rect':{'x':30,'y':80,'w':30,'h':30}},
            {'id':'gone','part':'shape','archived':True,'rect':{'x':30,'y':80,'w':30,'h':30}},
        ]}
    def test_exact_handle_and_containment(self):
        got=context(self.scene,{'gesture':'drop','target':'bar','channel':'width','point':{'x':140,'y':95}})
        self.assertEqual(got['target']['mapping'],{'width':'duration'})
        self.assertEqual(got['channel'],'width')
        self.assertEqual(got['container']['id'],'frame')
        self.assertEqual([b['id'] for b in got['nearby']],['board'])
    def test_client_cannot_supply_native_facts(self):
        got=context(self.scene,{'target':'bar','mapping':{'width':'invented'},'nearby':[{'id':'fake'}],'channel':'execute','point':{'x':float('nan'),'y':0}})
        self.assertEqual(got['target']['mapping']['width'],'duration')
        self.assertIsNone(got['channel'])
        self.assertNotIn('fake',str(got))
    def test_nearby_changes_when_moved(self):
        interaction={'point':{'x':600,'y':100}}
        before=context(self.scene,interaction)
        self.scene['blocks'][2]['rect']['x']=3000
        after=context(self.scene,interaction)
        self.assertIn('board',[b['id'] for b in before['nearby']])
        self.assertNotIn('board',[b['id'] for b in after['nearby']])
    def test_scope_excludes_other_workspaces_and_archives(self):
        got=context(self.scene,{'target':'other','workspace':'maker2'})
        self.assertEqual(got['target']['id'],'other')
        self.assertEqual(got['nearby'],[])

if __name__=='__main__':unittest.main()
