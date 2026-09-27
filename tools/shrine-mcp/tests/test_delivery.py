import tempfile
from pathlib import Path
import unittest
from fixtures import *
from server import API
from codex import participate, install

class LocalClient:
    def __init__(self,api):self.api=api
    def call(self,method,**kwargs):return self.api.call(method,kwargs)

class DeliveryTests(unittest.TestCase):
    def test_capped_delivery_retains_pending_notices(self):
        w=world();client=LocalClient(API(w));root=tempfile.mkdtemp()
        for i in range(16):
            checked(w.write('make','/delivery-cap/'+str(i),{'kind':'notice','question':'Notice '+str(i)+' '+'x'*4000}))
        state={}; delivered=set()
        for i in range(30):
            output,state=participate(client,{'hook_event_name':'SessionStart','cwd':root,'session_id':'cap-session'},root,'cap-consumer',state)
            text=output['hookSpecificOutput']['additionalContext']
            self.assertLessEqual(len(text.encode()),12288)
            for n in range(16):
                if '"path":"/delivery-cap/'+str(n)+'"' in text:delivered.add(n)
            if len(delivered)==16:break
        self.assertEqual(delivered,set(range(16)))

    def test_pending_notice_and_consumer_cursors_survive_contexts(self):
        w=world();api=API(w)
        checked(w.write('make','/custom-notice',{'kind':'notice','question':'Review a real transition'}))
        a=api.events(consumer='delivery-fixture',notices_only=True)
        self.assertTrue(a['events'])
        self.assertTrue(API(w).events(consumer='delivery-fixture',notices_only=True)['events'])
        api.events(consumer='delivery-fixture',acknowledge=a['cursor'])
        self.assertFalse(API(w).events(consumer='delivery-fixture',notices_only=True)['events'])
        with self.assertRaises(ValueError):api.events(consumer='unoffered',acknowledge=w.sequence+1)

    def test_hook_output_is_bounded_and_never_claims_mental_use(self):
        w=world();client=LocalClient(API(w));root=tempfile.mkdtemp()
        output,state=participate(client,{'hook_event_name':'SessionStart','cwd':root,'session_id':'session-a'},root,'fixture-hook',{})
        text=output['hookSpecificOutput']['additionalContext']
        self.assertLessEqual(len(text.encode()),12288)
        self.assertIn('delivery does not establish use',text)
        ignored,_=participate(client,{'hook_event_name':'PostToolUse','cwd':root,'tool_name':'mcp__shrine__observe'},root,'fixture-hook',state)
        self.assertEqual(ignored,{})
        hooks=install('/tmp/unused-connection',root)
        self.assertTrue(Path(hooks['hooks']).exists())
        self.assertIn('trust',hooks['review'])

if __name__=='__main__':unittest.main()
