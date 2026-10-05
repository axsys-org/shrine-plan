from pathlib import Path
p=Path('extras/mounts/medium/typed_collections.py');s=p.read_text()
s=s.replace("TYPES={'Text','Natural','Boolean','Choice','Date'}", "TYPES={'Text','Natural','Number','Boolean','Choice','Date','Reference','Image','File','List','Sequence','Object'}\nSTRUCTURED={'Number','List','Sequence','Object'}")
s=s.replace("'choices':choices if kind=='Choice' else []", "'choices':choices if kind=='Choice' else [],'target':field.get('target','') if kind=='Reference' else ''")
s=s.replace("    for kind in sorted({f['type']", "    if any(f['type'] in STRUCTURED for f in schema['fields']):parts.append('#import values=gov/user/collection_values_v1')\n    if any(f['type'] in {'Reference','Image','File'} for f in schema['fields']):parts.append('#import reference=lib/grove/types/path')\n    for kind in sorted({f['type']")
s=s.replace("        if f['type']=='Choice':return mode+'_'+f['key']", "        if f['type'] in STRUCTURED:return 'values/'+f['type'].lower()\n        if f['type'] in {'Reference','Image','File'}:return 'reference'\n        if f['type']=='Choice':return mode+'_'+f['key']")
s=s.replace("record =\\n  @role\\n  lede: text\\n  #opt ;\\n", "record =\\n  @role\\n  #opt ;\\n")
a=s.index('    # One native action per field');b=s.index('    groups=[]',a)
s=s[:a]+'''    # Same native Grove handler protocol, without expanding N argument structs.
    # Native codecs validate every field before one immutable record commits.
    path=lambda suffix:'(path_parse '+quoted(root+'/'+suffix)+').fall([])'
    lines=['save_all =','  @slot','  #meta ;','    "/sys/grove/action_handler": (grove_action_handler save_all/apply)','  ! foil','  + apply','    \\\\ arguments=myth current=myth','    ^ maybe[myth]']
    for f in schema['fields']:
        key=f['key'];kind=f['type'];ref=type_ref(f,'type');slot=path(key)
        lines.extend(['    < '+key+' arguments.get('+path('arg_'+key)+')','    < '+key+' (text/read '+key+')'])
        # Complex values stay native typed structures. Their display slot is a
        # canonical projection produced by the same native action, not editable.
        lines.extend(['    < current','      ? (eq '+key+' "") (./some current.del('+slot+').del('+path('display_'+key)+'))'])
        if kind in STRUCTURED:
            lines.extend(['      < value ('+ref+'/parse '+key+')','      | ./some current.put('+slot+' ('+ref+'/write value)).put('+path('display_'+key)+' (pails/t ('+ref+'/format value)))'])
        elif kind in {'Reference','Image','File'}:
            lines.extend(['      < value (path_parse '+key+')','      ? (eq value.len 0) .none','      | ./some current.put('+slot+' (pails/p value))'])
        else:
            if kind!='Text':lines.append('      < '+key+' ('+type_ref(f,'input')+'/read (pails/t '+key+'))')
            value='(pails/n (nat/parse '+key+').fall(0))' if kind=='Natural' else '(pails/b (eq '+key+' "true"))' if kind=='Boolean' else '(pails/t '+key+')'
            lines.append('      | ./some current.put('+slot+' '+value+')')
    lines.append('    | ./some current');parts.append('\\n'.join(lines))
''' + s[b:]
s=s.replace("'choices':f['choices'],'slot':root+'/'+f['key']", "'choices':f['choices'],'target':f.get('target',''),'slot':root+'/'+f['key']")
s=s.replace("'value':values.get(root+'/'+f['key']) or ''", "'value':values.get(root+'/'+('display_' if f['type'] in STRUCTURED else '')+f['key']) or ''")
p.write_text(s)
