"""Product checks against the actual Foil engine and factual feed parser."""
from datetime import datetime
import json, unittest, time
from bridge import *
from canvas import parse, PRIVATE, TZ

def event(uid='event-assignment-12', start='DTSTART;VALUE=DATE:20261004', extra=''):
    return ('BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:'+uid+'\r\n'+start+
        '\r\nSUMMARY:Read\\, then test [Test Course]\r\nURL:https://sit.instructure.com/calendar?include_contexts=course_42#assignment_12\r\n'+extra+
        'END:VEVENT\r\nEND:VCALENDAR\r\n').encode()

class FeedTests(unittest.TestCase):
    def test_date_is_not_an_invented_due_time(self):
        r=parse(event())[0]
        self.assertEqual(r['due_precision'],'date')
        self.assertEqual(datetime.fromtimestamp(r['due_epoch'],TZ).isoformat(),'2026-10-05T00:00:00-04:00')
        self.assertEqual(r['title'],'Read, then test')
    def test_utc_instant_is_preserved(self):
        r=parse(event(start='DTSTART:20261005T035900Z'))[0]
        self.assertEqual(r['due_precision'],'instant')
        self.assertEqual(r['due_date'],'2026-10-04')
    def test_override_identity_retained(self):
        r=parse(event(uid='event-assignment-override-99'))[0]
        self.assertEqual(r['uid'],'event-assignment-override-99')
        self.assertNotIn('canvas_id',r)
    def test_recurrence_not_silently_dropped(self):
        with self.assertRaises(ValueError):parse(event(extra='RRULE:FREQ=WEEKLY;COUNT=3\r\n'))
    def test_duplicate_is_not_silently_overwritten(self):
        v=event().decode();chunk=v[v.index('BEGIN:VEVENT'):v.index('END:VCALENDAR')]
        with self.assertRaises(ValueError):parse(v.replace('END:VCALENDAR',chunk+'END:VCALENDAR').encode())
    def test_real_snapshot(self):
        if not (PRIVATE/'first.ics').exists():self.skipTest('Optional private snapshot not configured')
        rows=parse((PRIVATE/'first.ics').read_bytes())
        self.assertTrue(rows)
        self.assertEqual(len(rows),len({r['uid'] for r in rows}))

class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema=one('/campus/schema');cls.module=json.loads(cls.schema['module_pin_json'])
        cls.root='/campus/tests/'+str(int(time.time()))
        upsert(cls.root+'/clock',{'epoch':1000})
        upsert(cls.root+'/settings',{'soon_seconds':100,'max_age_seconds':200})
        path=lambda p:'['+' '.join('($ts '+json.dumps(x)+')' for x in p.strip('/').split('/'))+']'
        crew=pin('(cpail (mop/sing[path dep lt_pith] [\'clock] (dep .x '+path(cls.root+'/clock')+')).put([\'settings] (dep .x '+path(cls.root+'/settings')+')))')
        cls.crew=crew
        upsert(cls.root+'/item',{'/sys/limb':cls.schema['assignment_behavior'],'/sys/crew':crew,
            'due_epoch':1500,'observed_epoch':1000,'submission_state':'unknown','local_done':0})
        # Native attachment hydrates the crew after init. An ordinary poke settles it.
        assert one(cls.root+'/item')['phase']=='unknown'
        write(cls.root+'/item',{})
    def evaluate(self,expression):
        return checked(SHRINE.call('eval',expression=expression,module=self.module,work=WORK))['value']
    def test_semantic_distinctions(self):
        checks=[('(campus/classify 1000 1050 "unknown" 0 0 100)','due_soon'),
            ('(campus/classify 1000 900 "unknown" 0 1 100)','planned_done'),
            ('(campus/classify 1000 900 "submitted" 0 0 100)','submitted'),
            ('(campus/classify 1000 900 "unknown" 0 0 100)','due_passed'),
            ('(campus/freshness 1201 1000 200)','stale')]
        # nat text renderings are available through the native pails/t wrapper.
        for expr,expected in checks:
            value=self.evaluate('(pails/t '+expr+')')
            upsert(self.root+'/value',{'value':value})
            self.assertEqual(one(self.root+'/value')['value'],expected)
    def test_native_cascade_noop_and_recovery(self):
        path=self.root+'/item'
        self.assertEqual(one(path)['phase'],'upcoming')
        upsert(self.root+'/clock',{'epoch':1450})
        self.assertEqual(one(path)['phase'],'due_soon')
        notice='/campus/notices'+path
        n=one(notice);self.assertEqual(n.get('kind'),'notice')
        upsert(self.root+'/clock',{'epoch':1451})
        self.assertEqual(one(notice)['_case'],n['_case'])
        self.assertEqual(one(path)['freshness'],'stale')
        upsert(path,{'observed_epoch':1451,'due_epoch':1800})
        self.assertEqual(one(path)['freshness'],'recent')
        self.assertEqual(one(path)['phase'],'upcoming')
        self.assertIn('deadline changed',one(notice)['statement'])
        old=one(path)
        upsert(path,{'local_done':1})
        self.assertEqual(one(path)['phase'],'planned_done')
        self.assertEqual(one(path)['submission_state'],'unknown')
        with self.assertRaises(RuntimeError):write(path,{'note':'stale edit'},old['_case'])

if __name__=='__main__':unittest.main(verbosity=2)
