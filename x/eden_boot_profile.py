"""Opt-in boot timings, instrumenting only Eden's disposable source copy."""
import ast
import json
import re
from pathlib import Path
import test_runner as runner


def instrument(source):
    reaver = Path(source) / 'reaver'
    (reaver / 'eden-boot-measure.rvr').write_text('''(#bind std (#module std))
(#import std)
(define (timed label deps f)
  (define start (DeepSeq deps (Now 0)))
  (define result (Seq start (f 0)))
  (define end (DeepSeq result (Now 0)))
  (Seq (print ("BOOT" label (Div (Sub end start) 1000000))) result))
(#export timed)
''')
    def edit(name, changes):
        path = reaver / name
        text = path.read_text()
        text = '(#bind measure (#module eden-boot-measure))\n' + text
        for before, after in changes:
            if text.count(before) != 1:
                raise RuntimeError(f'Boot probe needs updating: {name}: {before}')
            text = text.replace(before, after)
        path.write_text(text)

    def wrap(expression, label, deps='0'):
        return (expression,
                f'(measure:timed "{label}" {deps} (lambda (_) {expression}))')

    edit('foil-bootstrap.rvr', [
        wrap('(publication:prepare-system compiler source:read-module system-roots)', 'system.prepare'),
        wrap('(publication:compile prepared driver:empty-foil-cache)', 'system.compile', 'prepared'),
        wrap('(source:prepare-publication selection compiler module-root images\n      (lambda (path) 0) ["compiler_publication"])', 'policy.prepare', 'compiled'),
        wrap('(publication:compile policy-plan (_1 compiled))', 'policy.compile', '[policy-plan compiled]'),
        wrap('(publication:publish-system policy slot compiled 0 0)', 'system.publish', '[policy compiled]'),
        wrap('(source:prepare-publication (context:publication-key previous-context)\n      (context:compiler-key previous-context) module-root images\n      (lambda (path) 0) modules)', 'local.prepare', '[previous-context images]'),
        wrap('(publication:compile prepared (_1 policy-code))', 'local.compile', '[prepared policy-code]'),
        wrap('(publication:publish-local store-policy slot policy-code\n      0 0 (accepted initial))', 'policy.publish', '[store-policy policy-code initial]'),
        wrap('(publication:publish-local store-policy slot code\n      0 0 policy-state)', 'local.publish', '[store-policy code policy-state]'),
    ])
    edit('foil-new-env.rvr', [
        ('(define out (elab-mod-info sut decls))',
         '(define out (measure:timed (strWeld "module." mod) [sut decls] (lambda (_) (elab-mod-info sut decls))))'),
        ('(foil-new-elab:compiler-subject\n      (foil-new-elab:elab-mod\n        (foil-new-elab:compiler-for sut) decls))',
         '(measure:timed "elaborate" 0 (lambda (_) (foil-new-elab:compiler-subject (foil-new-elab:elab-mod (foil-new-elab:compiler-for sut) decls))))'),
        ('(define final (foil-lower:materialize-consts mod))',
         '(define final (measure:timed "materialize" mod (lambda (_) (foil-lower:materialize-consts mod))))'),
        ('(define lowered (foil-lower:lower-tc-unit sut final own-keys))',
         '(define lowered (measure:timed "lower" [final own-keys] (lambda (_) (foil-lower:lower-tc-unit sut final own-keys))))'),
    ])
    path = reaver / 'foil-new-elab.rvr'
    text = path.read_text()
    start = text.index('(define (elab-declaration compiler row)')
    end = text.index('(define (module-declarations mod)', start)
    block = text[start:end]
    block = block.replace('(r (elab-value-go compiler env body))',
        '(start (Now 0))\n           (r (Seq start (elab-value-go compiler env body)))')
    block = block.replace('(compiler-with-subject subject1 (_0 r))',
        '(Seq (print ("BOOT" (foldl (lambda (out part) (strcat [out "/" part])) "decl" (_1 row)) (Div (Sub (Now 0) start) 1000000))) (compiler-with-subject subject1 (_0 r)))')
    path.write_text(text[:start] + block + text[end:])


def report(log, destination):
    def number(atom):
        if atom.startswith('"'):
            quoted = '"' + atom[1:-1].replace('""', '\\"') + '"'
            return int.from_bytes(ast.literal_eval(quoted).encode('latin1'), 'little')
        return int(atom)
    rows = [dict(phase=runner.decode_atom(m[1]), milliseconds=number(m[2]))
            for m in re.finditer(r'^\("BOOT"\s+' + runner.ATOM + r'\s+' + runner.ATOM + r'\)', log, re.M)]
    Path(destination).write_text(json.dumps(rows, indent=2) + '\n')
    for row in rows:
        if row["phase"].startswith("decl/") or row["phase"] in {"elaborate", "materialize", "lower"}:
            continue
        print(f"Boot {row['phase']}: {row['milliseconds']/1000:.3f}s", flush=True)
