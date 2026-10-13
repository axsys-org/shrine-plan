"""Validated transport into native Rex constructors; no Goo interpretation."""
COLORS={'clear','paren','brack','curly'}
SHAPES={'word','quip','cord','tape','page','span','slug'}
REASONS={'invalid-char','unclosed-trad','unclosed-ugly','mismatched-bracket','invalid-page','invalid-span'}
def string(s):
    if not isinstance(s,str) or '\0' in s: raise ValueError('expected NUL-free string')
    return str(int.from_bytes(s.encode('utf-8'),'little'))
def node(n):
    tag=n['tag']; span=n['span']
    if len(span)!=4 or any(type(x)!=int or x<0 for x in span): raise ValueError('invalid span')
    args=['('+' '.join(map(str,span))+')']
    if tag=='leaf':
        sh=n['shape']
        if isinstance(sh,str) and sh in SHAPES: shape=string(sh)
        elif isinstance(sh,dict) and sh.get('bad') in REASONS: shape='("bad" '+string(sh['bad'])+')'
        else: raise ValueError('invalid shape')
        args += [shape,string(n['text'])]
    else:
        if tag not in {'nest','expr','pref','tyte','bloc','open','juxt','heir'}: raise ValueError('invalid tag')
        if tag in {'nest','expr','bloc'}:
            if n['color'] not in COLORS: raise ValueError('invalid color')
            args += [string(n['color'])]
        if tag in {'nest','pref','tyte','bloc','open'}: args += [string(n['rune'])]
        if tag=='bloc': args += [node(n['head'])]
        if tag=='pref': args += [node(n['kid'])]
        else: args += ['('+' '.join(node(k) for k in n['kids'])+')' if n['kids'] else '0']
    return '('+string(tag)+' '+' '.join(args)+')'
DECODE = r'''(define (datum form)
  (If (Eq 1 (Hd form)) (_0 form) (map datum form)))
(define (decode n)
  (define tag (_0 n))
  (define sp (_1 n))
  (cond
    ((Equal tag "leaf")
      (rex:MakeLeaf sp (If (Nat (_2 n)) (_2 n) ("bad" (_1 (_2 n)))) (_3 n)))
    ((Equal tag "nest") (rex:MakeNest sp (_2 n) (_3 n) (map decode (_4 n))))
    ((Equal tag "expr") (rex:MakeExpr sp (_2 n) (map decode (_3 n))))
    ((Equal tag "pref") (rex:MakePref sp (_2 n) (decode (_3 n))))
    ((Equal tag "tyte") (rex:MakeTyte sp (_2 n) (map decode (_3 n))))
    ((Equal tag "bloc") (rex:MakeBloc sp (_2 n) (_3 n) (decode (_4 n)) (map decode (_5 n))))
    ((Equal tag "open") (rex:MakeOpen sp (_2 n) (map decode (_3 n))))
    ((Equal tag "juxt") (rex:MakeJuxt sp (map decode (_2 n))))
    ((Equal tag "heir") (rex:MakeHeir sp (map decode (_2 n))))
    (else (error ["invalid transport node" n tag]))))'''

FIELDS = {
    'leaf': {'shape', 'text'}, 'nest': {'color', 'rune', 'kids'},
    'expr': {'color', 'kids'}, 'pref': {'rune', 'kid'},
    'tyte': {'rune', 'kids'}, 'bloc': {'color', 'rune', 'head', 'kids'},
    'open': {'rune', 'kids'}, 'juxt': {'kids'}, 'heir': {'kids'},
}
def strict_tree(tree):
    if not isinstance(tree, dict) or not isinstance(tree.get('tag'), str):
        raise ValueError('expected tagged tree')
    if tree['tag'] not in FIELDS or set(tree) != FIELDS[tree['tag']] | {'tag','span'}:
        raise ValueError('unknown tag or incorrect tree fields')
    if not isinstance(tree['span'], list): raise ValueError('expected span array')
    if 'shape' in tree and isinstance(tree['shape'], dict) and set(tree['shape']) != {'bad'}:
        raise ValueError('incorrect bad shape fields')
    if 'kids' in tree:
        if not isinstance(tree['kids'], list): raise ValueError('expected kids array')
        for kid in tree['kids']: strict_tree(kid)
    for key in ('kid', 'head'):
        if key in tree: strict_tree(tree[key])
    node(tree)  # Exact integer spans, colors, leaf shapes and NUL-free strings.

