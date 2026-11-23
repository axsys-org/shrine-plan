#!/usr/bin/env python3
"""Build an offline study fixture from attributed Sefaria snapshots; no runtime logic."""
from pathlib import Path
import json, re, html, hashlib
ROOT=Path(__file__).resolve().parent.parent/'mounts/shuin-chat'
SRC=ROOT/'talmud-source'
def clean(value):
    value=re.sub(r'<i\b[^>]*class=[\"\']footnote[\"\'][^>]*>.*?</i>', '',value,flags=re.S)
    value=re.sub(r'<sup\b[^>]*>.*?</sup>','',value,flags=re.S)
    value=re.sub(r'<br\s*/?>',' ',value)
    return ' '.join(html.unescape(re.sub('<[^>]+>','',value)).replace('\u200f','').replace('\u200e','').split())
def q(s):
    parts=re.split(r'(["\\])',s)
    if len(parts)==1:return '"'+s+'"'
    return '(str/cat_all ['+' '.join('(str/from_atom '+str(ord(x))+')' if x in ['"',chr(92)] else '"'+x+'"' for x in parts if x)+'])'

def path(s):return "[state.self 'app 'talmud "+' '.join("'"+x for x in s.split('/'))+"]"
d=json.loads((SRC/'Berakhot.json').read_text())
he=[clean(x) for x in d['he']]; en=[clean(x) for x in d['text']]
assert len(he)==len(en)==14
lines=['- shuin_commentary','- shuin_scenes','','+ shuin_talmud','  + install','    \\ state=namespace','    ^ either[pail namespace]',"    = schema (shuin_commentary/schema state.self)", "      home=path [state.self 'app 'talmud]", "      pages=row[path] [[state.self 'app 'talmud 'pages 'berakhot_2a]]", "      layers=row[path] [[state.self 'app 'talmud 'layers 'rashi] [state.self 'app 'talmud 'layers 'tosafot] [state.self 'app 'talmud 'layers 'personal]]", '      entries=row[[path myth]]','        [']
def record(p,title,help,slot,expr):
    lines.append('         ['+p+' ((shuin_commentary/named '+q(title)+' '+q(help)+').put(schema.snoc(\''+slot+') '+expr+'))]')
record('home','Talmud','Via Sefaria · English: A. Cohen (1921, public domain); Rashi: Sefaria Community (CC0); Tosafot: Jan Buckler (CC-BY). Hebrew: Wikisource (CC-BY-SA), Vilna (public domain).','library',"(shuin_commentary/library pages layers home.snoc('glosses) \"rtl\")")
for p,title,desc in [('pages','Pages','The source pages in this study.'),('layers','Commentary layers','Independent commentary traditions and personal notes.'),('glosses','Glosses','Comments with exact, versioned text anchors.'),('layers/rashi','Rashi','Hebrew: Vilna edition, public domain. English: Sefaria Community Translation, CC0.'),('layers/tosafot','Tosafot','Hebrew: Vilna edition, public domain. English: Jan Buckler, CC-BY, via Sefaria.'),('layers/personal','My notes','Your own glosses and replies, saved as namespace records.')]:
    lines.append('         ['+path(p)+' (shuin_commentary/named '+q(title)+' '+q(desc)+')]')
passages='['+' '.join(path(f'pages/berakhot_2a/p{i:02}') for i in range(1,15))+']'
record(path('pages/berakhot_2a'),'Berakhot 2a','Evening Shema: the opening Mishnah and Gemara.','page',f'(shuin_commentary/page {passages} "https://www.sefaria.org/Berakhot.2a")')
for i,(h,e) in enumerate(zip(he,en),1):record(path(f'pages/berakhot_2a/p{i:02}'),f'Berakhot 2a:{i}','Mishnah' if i==1 else 'Gemara','passage',f'(shuin_commentary/passage {q(h)} {q(e)} "https://www.sefaria.org/Berakhot.2a.{i}")')
lines+=['        ]','    % rest=row[[path myth]] entries state=namespace state','    ^ either[pail namespace]','    ? !(rest.len) (shuin_talmud/glosses state)','    = [target card] rest.at(0)','    ?> (./ok next) (grove_install/change target (writ/make card) state) (./err (pails/t "Talmud record installation failed"))','    | _ rest.drop(1) next','  + glosses','    \\ state=namespace','    ^ either[pail namespace]',"    = schema (shuin_commentary/schema state.self)", '      entries=row[[path myth]]','        [']
count=0
for name,side,key in [('Rashi_on_Berakhot','right','rashi'),('Tosafot_on_Berakhot','left','tosafot')]:
    c=json.loads((SRC/(name+'.json')).read_text());primary=c['he'];secondary=c['text']
    for idx,group in enumerate(primary):
        if isinstance(group,str): group=[group]
        for sub,h in enumerate(group):
            h=clean(h)
            if not h:continue
            eg=secondary[idx] if idx<len(secondary) else []
            if isinstance(eg,str):eg=[eg]
            e=clean(eg[sub]) if sub<len(eg) else ''
            source=f'https://www.sefaria.org/{name}.2a.{idx+1}.{sub+1}'
            target=path(f'pages/berakhot_2a/p{idx+1:02}')
            anchor=f'(shuin_commentary/anchor {target} (goo_runtime/lifetime {target} state) (state.case(.x {target})).fall(0) "primary" 0 {len(he[idx].encode())} {q(he[idx])})'
            g=f'(shuin_commentary/gloss {anchor} {path("layers/"+key)} "{side}" {q(h)} {q(e)} [] {q(source)})'
            record(path(f'glosses/{key}_{idx+1:02}_{sub+1:02}'),f'{"Rashi" if key=="rashi" else "Tosafot"} on Berakhot 2a:{idx+1}:{sub+1}','An imported commentary linked to its source segment.','gloss',g);count+=1
lines += ['        ]','    % rest=row[[path myth]] entries state=namespace state','    ^ either[pail namespace]','    ? !(rest.len)','      = scene (shuin_scenes/scene state.self "Talmud" "Bilingual reading with commentary in both margins." "commentary" 40 [state.self \'app \'talmud] [state.self \'gov \'shuin_commentary \'reader])',"      ?> (./ok next) (grove_install/change (shuin_scenes/home state.self).snoc('talmud) (writ/make scene) state) (./err (pails/t \"Talmud scene installation failed\"))",'      | ./ok next','    = [target card] rest.at(0)','    ?> (./ok next) (grove_install/change target (writ/make card) state) (./err (pails/t "Commentary installation failed"))','    | _ rest.drop(1) next']
(ROOT/'talmud.foil').write_text('\n'.join(lines)+'\n')
manifest=[]
for n in ['Berakhot','Rashi_on_Berakhot','Tosafot_on_Berakhot']:
    p=SRC/(n+'.json');c=json.loads(p.read_text());manifest.append({'file':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'url':f'https://www.sefaria.org/{n}.2a','english':{'version':c.get('versionTitle'),'license':c.get('license'),'source':c.get('versionSource')},'hebrew':{'version':c.get('heVersionTitle'),'license':c.get('heLicense'),'source':c.get('heVersionSource')}})
(SRC/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(f'Generated 14 bilingual passages and {count} imported glosses.')
