import sys,runpy,json,sqlite3
sys.path.insert(0,'extras/mounts/nenex/address_book')
from model import path,reference,slot,address_selection,projections
from austin import overlay,ROOT
c=runpy.run_path('extras/mounts/cooperate/client.py')['Client']('http://127.0.0.1:8131',timeout=180)
db=sqlite3.connect('.local-data/austin-addresses/index.sqlite')
ident,label,sid,addr=db.execute('SELECT place_id,label,street_id,namespace_path FROM addresses WHERE place_id=91412').fetchone()
report=json.load(open('.local-data/austin-addresses/prepared.json'))
street=overlay('/0x11/gov/nenex_ui/austin_street_lens',report['lenses']['/0x11/gov/nenex_ui/austin_street_lens'],report['source']+'/street_pages/p_'+sid[2:4])+'/'+sid
reads=c.tool('read',reads=[{'path':addr,'care':'x'},{'path':street,'care':'x'},*[{'path':'/0x11/weft/stdlib/'+x,'care':'x'} for x in ('lookup','gather')]])['answers']
assert reads[0]['properties'][slot('address_label')]==label
assert reads[0]['properties'][slot('address_street')]==street
assert reads[1]['properties']['/sys/lede']=='W 2ND ST'
formulas={k:{'type':'reference','value':v['reference']} for k,v in zip(('lookup','gather'),reads[2:])}
r='/0x11/agent/nenex_assistant/austin_crm_check'
records=[{'path':r+'/directory/people/test','slots':{'/sys/about':path(r+'/directory/people/test'),'/sys/lede':'Temporary synthetic test person'}},
 {'path':r+'/contacts/test','slots':{slot('contact_person'):path(r+'/directory/people/test'),slot('contact_workplace'):path(r+'/links/test')}},
 {'path':r+'/links/test','slots':{'/sys/about':path(r+'/links/test'),slot('association_address'):path(addr),slot('association_purpose'):path(r+'/demo_workplace'),slot('association_verification'):path(r+'/demo_unverified')}}]
selection,table=address_selection(r+'/selected',[addr],formulas['gather'])
cells,outputs=projections(r+'/views',r+'/contacts',r+'/directory',r+'/links',formulas,address_table=table)
written=c.tool('write',records=records+selection+cells,who='nenex_assistant',then=[{'path':outputs['contacts'],'care':'y'}])
row=written['then'][outputs['contacts']]['children'][0]['properties']
assert row[slot('contact_address_label')]==label
assert row[slot('contact_address_target')]==addr
c.tool('write',records=[{'path':r,'action':'cull'},{'path':'/0x11/agent/nenex_assistant/austin_codec_check','action':'cull'}],who='nenex_assistant')
print(json.dumps({'passed':'individual address + street paths + bounded CRM selection with native real address','label':label,'address':addr}),flush=True)
