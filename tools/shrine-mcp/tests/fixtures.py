"""Real native integration fixtures; no Python evaluator substitutes."""
from pathlib import Path
import os
import sys
import shutil
sys.path.append(str(Path(__file__).resolve().parents[1]))
from native import World
from records import checked, fields_of

WISP = os.environ.get('SHRINE_WISP') or shutil.which('wisp')
SEED = os.environ.get('SHRINE_SEED') or None

CUSTOM = '''-  sept [order=10]
-  shrine_types [order=20]
-  lain [order=30]
+  demo
  +  update
    \\  b=bowl cur=myth changed=row[dep]
    ^  yell
    =  > input b.crew.gut(['input] (axal/new[myth] .none))
    ?  input.fil
     > (./some t)
       (yell [] cur.put(['n] (pails/n t.nat_at(['n] 0))))
    (yell [] cur.put(['available] (pails/t "unknown")))
  +  init
    \\  b=bowl cur=myth
    ^  yell
    (demo/update b cur [])
  +  form
    ^  form
    def_form.set_init(demo/init).set_hear(demo/update)
  +  crew
    ^  cpail
    (cpail (mop/sing[path dep lt_pith] ['input] (dep .x ['inputs])))
  +  crew2
    ^  cpail
    (cpail (mop/sing[path dep lt_pith] ['input] (dep .x ['replacement])))
  +  binding
    ^  kook
    (kook [['forms 'custom]])
'''


def install_custom(w):
    compiled = checked(w.compile(CUSTOM, exports=['demo/form', 'demo/crew', 'demo/crew2', 'demo/binding']))
    e = compiled['exports']
    checked(w.write('make', '/forms/custom', {'form': e['demo/form']}))
    checked(w.write('make', '/inputs', {'n': 3, 'noise': 0}))
    checked(w.write('make', '/projection', slots=[{'key':['sys','limb'], 'value': e['demo/binding']},
        {'key':['sys','crew'], 'value': e['demo/crew']}]))
    return compiled

import atexit
_world = None
_compiled = None

def world():
    global _world
    if _world is None:
        if not WISP:
            import unittest
            raise unittest.SkipTest('Set SHRINE_WISP to a compatible Wisp executable')
        directory = os.environ.get('SHRINE_TEST_WORLD')
        if not directory:
            import tempfile
            directory = tempfile.mkdtemp(prefix='shrine-v5-test-')
        _world = World(directory, WISP, SEED)
        atexit.register(lambda: _world.close())
    return _world


def custom():
    global _compiled
    if _compiled is None:
        _compiled = install_custom(world())
    return _compiled

REALIZE = r"""-  sept [order=10]
-  shrine_types [order=20]
-  lain [order=30]
-  shadow_io [order=40]
+  realize
  +  talk
    \  b=bowl cur=myth add=myth
    ^  yell
    =  > next cur.meld(add)
    =  > request next.put(['status] (pails/t "PENDING")).put(['sys 'limb] (kook [['forms 'physical_request]]))
    (shadow_io/issue ['requests 'realized] request b next)
  +  form
    ^  form
    def_form.set_talk(realize/talk)
"""
VERIFY_FILE = r"""-  sept [order=10]
-  shrine_types [order=20]
-  lain [order=30]
-  json [order=35]
-  shadow [order=40]
+  verified
  \  observed=myth
  ^  nat
  ?  observed.get(['value])
   > (./some pl)
     ?  pl
      > raw=shadow/literal
        ?  raw.value
         > (./obj kvs)
           kvs.fold(0 ;
             \ acc item
             ? (eq item.k "text")
               (equal item.v (json/str "native realization verified"))
             acc)
        0
     0
  0
"""
