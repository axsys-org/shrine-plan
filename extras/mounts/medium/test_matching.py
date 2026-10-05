import unittest
import matching

class StructuralMatching(unittest.TestCase):
    def node(self,fields):
        return {'id':'/unfamiliar','properties':[dict(label=name,slot='/'+name,type=kind,role=role,choices=choices)for name,kind,role,choices in fields]}
    def test_role_coverage_and_field_renaming(self):
        n=self.node([('title','Text','title',[]),('status','Enum','group',['To do','Doing','Done']),('assignee','Ref','ref',[]),('start','Date','start',[]),('duration','Duration','duration',[]),('depends_on','Many','',[])])
        self.assertEqual([(x['part'],x['score'])for x in matching.enumerate_collection(n)],[('board',1.3),('table',1.15),('list',1.15)])
        for i,f in enumerate(n['properties']):f['label']='field'+str(i)
        self.assertEqual([x['score']for x in matching.enumerate_collection(n)],[1.3,1.15,1.15])
    def test_adapter_keeps_its_two_dependencies_and_inverse(self):
        n=self.node([('who','Text','title',[]),('room','Enum','group',['A','B']),('from','Date','start',[]),('to','Date','end',[])])
        needs=[('start',('Date',),'start',True),('duration',('Duration',),'duration',True),('row',('Enum','Ref'),'row',True),('title',('Text',),'title',False)]
        c=matching.enumerate_shape(n['properties'],needs)[0]
        self.assertEqual((c['score'],c['blanks']),(1.43,2));self.assertEqual(c['bindings'][1]['uses'],['/from','/to'])
    def test_missing_shapes_are_not_substituted(self):
        n=self.node([('caption','Text','title',[])])
        self.assertEqual(matching.enumerate_shape(n['properties'],[('geometry',('Place',),'geo',True)]),[])
    def test_model_skip_and_ai_off_ambiguity(self):
        self.assertEqual(matching.decision_mode([]),'hole')
        self.assertEqual(matching.decision_mode([{'score':1.6,'blanks':0}]),'local')
        self.assertEqual(matching.decision_mode([{'score':1.6,'blanks':1}]),'model')
        self.assertEqual(matching.decision_mode([{'score':1.55,'blanks':0},{'score':1.55,'blanks':0}],False),'hole')
