"""Transport/context contracts; live native acceptance remains separate."""
import importlib.util
import json
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('medium_model',Path(__file__).with_name('model.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class ModelBoundary(unittest.TestCase):
    def test_author_projection_keeps_current_executable_checks_and_exact_values(self):
        picture='data:image/svg+xml;utf8,<svg>'+('test '*1000)+'</svg>'
        node={'id':'/a','source':'current exact Foil with arbitrary checks','fields':[
            {'slot':'/picture','value':picture},{'slot':'/amount','value':'17'},
            {'slot':'/private-document','value':'x'*5000}],
            'view':{'html':'derived HTML','occurrences':[{'id':'native-action','reads':['/amount']}]}}
        context={'frame':{'nodes':[node],'provenance':[{'request':{
            'source':'old Foil','inputs':[{'subject':'/a','slots':['/amount']}],'intent':'keep this decision'}}]},
            'gesture':{'selected':{'subject':'/a','slots':[]}}}
        result=m.author_context(context);actual=result['frame']['nodes'][0]
        self.assertEqual(actual['source'],node['source'])
        self.assertEqual(actual['fields'][1:],node['fields'][1:])
        self.assertNotIn('value',actual['fields'][0])
        self.assertIn('omitted',actual['fields'][0]['value_summary']['coverage'])
        self.assertEqual(actual['view']['occurrences'],node['view']['occurrences'])
        history=result['frame']['provenance'][0]['request']
        self.assertEqual(history['inputs'],context['frame']['provenance'][0]['request']['inputs'])
        self.assertEqual(history['intent'],'keep this decision')
        self.assertIn('omitted_historical_source',history['source'])
        self.assertEqual(node['fields'][0]['value'],picture)
        self.assertEqual(node['view']['html'],'derived HTML')
        context['gesture']['selected']['slots']=['/picture']
        self.assertEqual(m.author_context(context)['frame']['nodes'][0]['fields'][0]['value'],picture)

    def test_context_keeps_dependency_cone_not_other_history(self):
        nodes=[{'id':i,'label':i,'source':'source '+i,'pattern':i,
                'inputs':[{'subject':j} for j in deps]} for i,deps in
               [('a',[]),('b',['a']),('c',['b']),('unrelated',[])]]
        scoped=m.scoped_frame({'nodes':nodes,'events':[{'id':'old','kind':'act','body':'{"target":"unrelated"}'}],'expected':'3'},
                              {'selected':{'subject':'b'}})
        self.assertEqual([n['id'] for n in scoped['nodes']],['a','b','c'])
        self.assertNotIn('events',scoped)
        self.assertNotIn('source',scoped['catalog'][0])
        self.assertEqual(scoped['affected_consumers'],['c'])

    def test_operational_typing_carries_holes_and_exact_provenance(self):
        typing={'definition':{'address':'/defs/d','case':'17'},'role':{'fields':[{'slot':'/opaque/42','type':{'address':'/codec/count','case':'4'}}]}}
        node={'id':'a','label':'Unimportant label','pattern':'/defs/d','source':'native executable contract','inputs':[{'subject':'b','slots':['/opaque/42'],'occurrence':'0'}],'open':['0'],'typing':typing}
        peer={'id':'b','label':'Another label','pattern':'/defs/b','source':'native b','inputs':[]}
        frame={'nodes':[node,peer], 'events':[
            {'id':'pull','basis':'12','kind':'detach','body':'{"target":"a","index":"0"}'},
            {'id':'unrelated','kind':'act','body':'{"target":"elsewhere"}'}]}
        context=m.scoped_frame(frame,{'selected':{'subject':'a'}})
        types=m.operational_context(context)
        self.assertEqual(types['subjects'][0]['typing'],typing)
        self.assertEqual(types['subjects'][0]['open'],['0'])
        self.assertEqual(types['subjects'][0]['inputs'][0]['subject'],'b')
        self.assertEqual([e['event'] for e in types['provenance']],['pull'])
        self.assertIn('not complete',types['provenance_coverage'])

    def test_reused_pattern_brings_its_actual_source_into_context(self):
        nodes=[{'id':'instance','label':'Use','pattern':'/defs/p','source':'','inputs':[]},
               {'id':'definition','label':'Definition','pattern':'/defs/p','source':'EXACT SOURCE','inputs':[]}]
        context=m.scoped_frame({'nodes':nodes},{'selected':{'subject':'instance'}})
        self.assertEqual([n['id'] for n in context['nodes']],['instance','definition'])

    def test_definition_context_includes_instances_and_their_consumers(self):
        nodes=[{'id':i,'label':i,'source':'source' if i=='definition' else '',
                'pattern':pattern,'inputs':[{'subject':d} for d in deps]}
               for i,pattern,deps in [('definition','/defs/p',[]),('emma','/defs/p',[]),
                   ('lucas','/defs/p',[]),('people','/defs/people',['emma','lucas']),('other','/defs/other',[])]]
        result=m.scoped_frame({'nodes':nodes},{'selected':{'subject':'emma','scope':'definition'}})
        self.assertEqual([n['id'] for n in result['nodes']],['definition','emma','lucas','people'])
        self.assertEqual(result['catalog'][0]['id'],'other')





    def test_declared_fallback_retains_reason(self):
        receipt={'model':'fallback'}
        with patch.object(m,'_completion',side_effect=[m.RoutingFailure(429,'limited'),({},receipt)]):
            _,actual=m.completion([], 'fast',threading.Event())
        self.assertEqual(actual['fallback_status'],429)
        self.assertEqual(actual['fallback_from'],'openrouter/auto')

    def test_exhausted_generation_gets_one_bounded_recovery_with_receipt(self):
        failed={'model':'reasoner','finish_reason':'length','usage':{'total_tokens':3500}}
        with patch.object(m,'_completion',side_effect=[m.IncompleteGeneration(failed),({'content':'done'},{'model':'fallback'})]) as call:
            _,receipt=m.completion([],'interpret',threading.Event())
        self.assertEqual(call.call_count,2)
        self.assertLessEqual(call.call_args.args[2]['max_tokens'],16000)
        self.assertEqual(receipt['prior_attempt'],failed)

    def test_recovery_does_not_loop_or_execute_partial_output(self):
        first={'finish_reason':'length','generation':'first'}
        second={'finish_reason':'length','generation':'second'}
        with patch.object(m,'_completion',side_effect=[m.IncompleteGeneration(first),m.IncompleteGeneration(second)]) as call:
            with self.assertRaises(m.IncompleteGeneration) as failure:m.completion([],'author',threading.Event())
        self.assertEqual(call.call_count,2)
        self.assertEqual(failure.exception.receipt['prior_attempt'],first)
        self.assertEqual(failure.exception.receipt['generation'],'second')

    def test_bad_credentials_are_not_retried(self):
        with patch.object(m,'_completion',side_effect=m.RoutingFailure(401,'bad credential')) as call:
            with self.assertRaises(m.RoutingFailure):m.completion([],'fast',threading.Event())
            self.assertEqual(call.call_count,1)


    def test_cancellation_prevents_request(self):
        cancel=threading.Event();cancel.set()
        with patch.object(m.urllib.request,'urlopen') as call:
            with self.assertRaisesRegex(RuntimeError,'Superseded'):m.completion([],'fast',cancel)
            call.assert_not_called()

if __name__=='__main__':unittest.main()
