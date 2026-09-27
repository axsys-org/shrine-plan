"""Compile real Foil, pin exports and attach ordinary native crews."""
from datetime import datetime, timezone
import json, time
from bridge import *

def install(artifact=None):
    if artifact:
        result=json.loads(Path(artifact).read_text())
    else:
        result=SHRINE.call('compile', source=(ROOT/'campus.foil').read_text(),
            exports=['campus/assignment','campus/source','campus/classify','campus/freshness'],work=WORK)
        filename=ROOT/'evidence'/('compile-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
        filename.parent.mkdir(exist_ok=True);filename.write_text(json.dumps(result,indent=2))
    c=checked(result)
    for key in ['assignment','source']:
        upsert('/campus/forms/'+key, {'form':c['exports']['campus/'+key]})
    crew=pin("(cpail (mop/sing[path dep lt_pith] ['clock] (dep .x ['campus 'clock])).put(['settings] (dep .x ['campus 'settings'])))")
    bindings={key:pin("(kook [['campus 'forms '"+key+"]])") for key in ['assignment','source']}
    upsert('/campus/schema', {'crew':crew,'assignment_behavior':bindings['assignment'],'source_behavior':bindings['source'],
        'module_pin_json':json.dumps(c['module']),'compile_receipt':{'path':c['receipt']['path']},
        'statement':'Dates and local planning are native. Canvas alone determines submission and grading.'})
    upsert('/campus/clock',{'epoch':int(time.time())})
    if not one('/campus/settings'):
        upsert('/campus/settings',{'soon_seconds':259200,'max_age_seconds':21600,'refresh_seconds':900,'timezone':'America/New_York'})
    seed=browser_seed()
    receipt=observe('browser-course-inventory',seed) if seed['courses'] else None
    for course in seed['courses']:
        upsert('/campus/courses/'+str(course['id']),{**course,'term':seed.get('term',''),
            'url':'https://sit.instructure.com/courses/'+str(course['id']),'evidence':{'path':receipt['path']}})
    upsert('/campus/source',{'/sys/crew':crew,'/sys/limb':bindings['source'],
        'host':'sit.instructure.com','mode':'Canvas calendar feed + verified browser observations',
        'coverage':'partial','limitations':'Calendar feed includes dated coursework and events, not submission status, grades, or all course materials.',
        'origin_work':{'path':WORK}})
    upsert('/campus/questions/submission-coverage',{'question':'How can authorized read-only submission receipts supplement the calendar feed when Stevens disables personal API tokens?',
        'anchors':[{'path':'/campus/source'},{'path':'/campus/assignments'}],
        'origin_work':{'path':WORK},'applicability':'UNESTABLISHED',
        'statement':'Unchecked planner boxes and absent calendar items do not prove missing submissions or deletion.'})
    print('Compiled native coursework forms; installed',len(seed['courses']),'optional course records.')

if __name__=='__main__':
    import sys
    install(sys.argv[1] if len(sys.argv)>1 else None)
