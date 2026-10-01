#!/usr/bin/env python3
"""Import frozen metrics; never regenerate fonts, CSS, or Haskell tables."""
import hashlib,json,pathlib,sys
root=pathlib.Path(__file__).resolve().parents[1]
faces=json.loads((root/'fonts/metrics.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for name,f in faces.items():
 assert sha(root/'fonts'/f['source'])==f['sourceSHA256'],name
 assert sha(root/'static'/('goo-'+name+'.ttf'))==f['fontSHA256'],name
 assert len(f['advances'])==95 and f['unitsPerEm']>0,name
s='''- goo_app/binary64
- json

' Generated from frozen fonts/metrics.json by generate-foil-fonts.py.
+ goo_fonts
  + face
    & '''+' '.join('goo_fonts/face/'+n.lower() for n in faces)+'\n'
for n in faces:s+='    + '+n.lower()+'\n      :\n'
s+='  + info\n    : name=str source=str source_sha256=str font_sha256=str weight=nat units=nat italic=bool advances=row[nat]\n  + metadata\n    \\ face=goo_fonts/face\n    ^ goo_fonts/info\n    ? face\n'
for n,f in faces.items():
 s+='     > ./'+n.lower()+' (goo_fonts/info '+ ' '.join(json.dumps(v) for v in [n,f['source'],f['sourceSHA256'],f['fontSHA256']])+f' {f["weight"]} {f["unitsPerEm"]} .'+('true' if n.startswith('Italic') else 'false')+' ['+' '.join(map(str,f['advances']))+'])\n'
s+='''  + all
    ^ row[goo_fonts/face]
    ['''+' '.join('(goo_fonts/face/'+n.lower()+')' for n in faces)+''']
  + advance
    \\ face=goo_fonts/face byte=nat
    ^ goo/scalar
    = data (goo_fonts/metadata face)
    ? ((lt byte 32) || (gt byte 126)) (Seq[goo/scalar] (error (goo_fp/fault "unsupported ASCII glyph")) (goo/scalar 0))
    | goo_fp/quotient (goo_fp/integer data.advances.at((sub byte 32))) (goo_fp/integer data.units)
  + json
    \\ face=goo_fonts/face
    ^ json
    = f (goo_fonts/metadata face)
    | json/obj [(jkv "name" (json/str f.name)) (jkv "source" (json/str f.source)) (jkv "sourceSHA256" (json/str f.source_sha256)) (jkv "fontSHA256" (json/str f.font_sha256)) (jkv "weight" (json/num .false f.weight)) (jkv "unitsPerEm" (json/num .false f.units)) (jkv "italic" (json/boo f.italic)) (jkv "advances" (json/arr f.advances.map((\\ n=nat (json/num .false n))))) (jkv "ratios" (json/arr f.advances.map((\\ n=nat (goo_number/encode (goo_fp/quotient (goo_fp/integer n) (goo_fp/integer f.units)))))))]
'''
p=root/'fonts.foil'
if '--check' in sys.argv:
 if p.read_text()!=s:raise SystemExit('generated font table is stale')
else:p.write_text(s)
