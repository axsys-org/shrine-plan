import json,time,urllib.request,sys,statistics
from pathlib import Path
sys.path.insert(0,str(Path('extras/mounts/medium').resolve()))
import model
key=model.credential()
cases=[
('pointed quantity',{'request':'show this as a number','target':{'field':'duration','type':'Number'},'nearby':['Tasks.status','Tasks.title']},{'a':'Show selected duration','b':'Count nearby tasks','c':'Show task status'},'a'),
('exact geometry',{'request':'put this here','dragged':{'field':'duration','type':'Number'},'target':{'shape':'rectangle','channel':'width'}},{'a':'width ← duration','b':'x ← duration','c':'text ← duration'},'a'),
('readonly',{'request':'let me drag this','target':{'channel':'angle','field':'temperature','writable':False}},{'a':'Show locked input; request a writable target','b':'Write temperature','c':'Write nearby thermostat.target'},'a'),
('missing timeline',{'request':'tasks over time one row per person','installed':['Board','Table','List'],'fields':['start','duration','assignee']},{'a':'Use Table','b':'Use Board','c':'No fit; offer component maker'},'c'),
('adapter',{'request':'use this on the lane component','required':{'x':'start','width':'duration'},'available':{'from':'Date','to':'Date'},'operations':['subtract compatible dates']},{'a':'x ← from; width ← to - from','b':'x ← from; width ← to','c':'x ← to; width ← from'},'a'),
('ambiguous source',{'request':'summarize this','target':{'part':'Number'},'nearby':[{'id':'a','distance':40,'type':'Many<Record>'},{'id':'b','distance':40,'type':'Many<Record>'}],'selection':None},{'a':'Use a','b':'Use b','c':'Ask which source'},'c'),
('effect hole',{'request':'finish this button','target':{'label':'Notify crew'},'capabilities':[]},{'a':'Send a message','b':'Keep a destination/capability hole','c':'Pretend notification succeeded'},'b'),
('novel logic',{'request':'red if it delays project finish','installed_operations':['enumColour','count','sum'],'available_fields':['duration','depends_on']},{'a':'Red when status is late','b':'Escalate a small pure function for checking','c':'Use count'},'b'),
]
results=[]
for name,state,options,expected in cases:
 for which in ('jev','small'):
  rules='Choose the most faithful available interpretation. Explicit target and channel outrank proximity. Do not invent a capability or write authority. Ambiguity stays a question. An available display that lacks the requested spatial encoding or behavior is not a fit: do not substitute another view. A named status is not a computed dependency condition. Missing computations require a checked function; missing external capabilities require a hole.'
  if which=='jev':
   endpoint='alpha/decisions';body={'model':'typesafe/jev-1.13','state':state,'questions':{'next':{'type':'choice','instructions':rules,'criteria':options}}}
  else:
   endpoint='v1/chat/completions';body={'model':'google/gemini-2.5-flash-lite','messages':[{'role':'system','content':rules},{'role':'user','content':json.dumps({'state':state,'options':options})}],'temperature':0,'max_tokens':80,'response_format':{'type':'json_schema','json_schema':{'name':'choice','strict':True,'schema':{'type':'object','properties':{'choice':{'type':'string','enum':list(options)}},'required':['choice'],'additionalProperties':False}}}}
  started=time.perf_counter()
  try:
   req=urllib.request.Request('https://openrouter.ai/api/'+endpoint,json.dumps(body).encode(),{'Authorization':'Bearer '+key,'Content-Type':'application/json'})
   with urllib.request.urlopen(req,timeout=15) as response:answer=json.load(response)
   picked=answer['answers']['next']['choice'] if which=='jev' else json.loads(answer['choices'][0]['message']['content'])['choice']
   result={'case':name,'model':which,'picked':picked,'expected':expected,'correct':picked==expected,'ms':round((time.perf_counter()-started)*1000),'usage':answer.get('usage'),'bytes':len(json.dumps(answer.get('answers',answer.get('choices'))).encode())}
  except Exception as error:result={'case':name,'model':which,'correct':False,'ms':round((time.perf_counter()-started)*1000),'error':type(error).__name__}
  results.append(result);print(json.dumps(result),flush=True)
  Path('work/spatial-decision/results.json').write_text(json.dumps({'scope':'Eight synthetic routing probes; one call per case per model. Not held-out product acceptance or p95 evidence.','results':results},indent=2))
