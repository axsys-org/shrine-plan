"""The ask hand, end to end over MCP with the fake model: an ask over a folder answers once; a poke to the folder marks
it stale and the hand re-answers with a new stamp; a cell over an ask composes; lineage shows model and case.

Usage: python3 -I -c "import runpy; runpy.run_path('extras/mounts/mcp/tests/ask.py')['check']('http://127.0.0.1:8300', '0x11', 120)"
"""
import importlib.util
import json
import os
import urllib.request


def check(base, node, timeout):
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location('ask_hand', os.path.join(here, '..', 'hands', 'ask.py'))
    ask_hand = importlib.util.module_from_spec(spec); spec.loader.exec_module(ask_hand)
    w = ask_hand.World(base, node, timeout)
    checks = []

    def expect(label, got, want):
        checks.append((label, got, want, got == want))
        assert got == want, (label, got, want)

    def epoch():
        with urllib.request.urlopen(base + '/probe/read?path=/' + node, timeout=timeout) as r:
            return json.load(r).get('epoch')

    home = '/' + node + '/agent/asker'
    try:
        w.tool('write', records=[{'path': home, 'action': 'cull'}])
    except RuntimeError:
        pass
    deals = home + '/deals'
    w.tool('write', records=[{'path': home, 'slots': {'title': 'asker'}}, {'path': deals, 'slots': {'title': 'deals'}}] +
           [{'path': deals + '/d' + str(i), 'slots': {'amount': 100 * i, 'status': 'closed' if i % 2 else 'open'}} for i in range(1, 4)])
    stdlib = {c['path'].rsplit('/', 1)[1]: {'type': 'reference', 'value': c['reference']} for c in w.read('/' + node + '/weft/stdlib', 'y', limit=100)['children']}
    hand = ask_hand.Hand(w, model='fake', fake=True, log=lambda *a: None)     # the hand starts watching from now; the ask is written after
    cell = home + '/views/verdict'
    w.tool('write', records=[{'path': cell, 'slots': {'sys/weft': stdlib['ask'], 'sys/tack': ask_hand.live(deals), 'prompt': 'How are the deals going?', 'model': 'fake'}}])

    # 1. before the hand runs: no answer, the context says so, no event spent on reading
    ctx = w.read('/c/x' + cell, 'x')['properties']
    expect('1 an ask with no answer yet reads empty and the context says asking', (w.read('/x' + cell, 'x')['exists'], ctx.get('/sys/view/asking', '').startswith('no answer yet')), (False, True))

    # 2. the hand answers once: one event, the result stamped with the input's case, the model and the prompt
    e0 = epoch(); answered = hand.tick(); e1 = epoch()
    answer = w.read('/x' + cell, 'x')
    expect('2 the hand answered the ask once', answered, 1)
    expect('2 one event for the answer plus one for the hand\'s seen mark', e1 - e0, 2)
    expect('2 /x is the result record: the answer with its stamp (case, model, prompt)',
           (answer['exists'], answer['properties']['/answer'].startswith('3 records, amount total 600'), answer['properties']['/model'], answer['properties']['/prompt'], answer['properties']['/case']),
           (True, True, 'fake', 'How are the deals going?', ctx['/sys/tack/case']))
    expect('2 a second tick has nothing to answer', hand.tick(), 0)

    # 3. a poke to the folder marks it stale; the hand re-answers with a new stamp
    w.tool('write', records=[{'path': deals + '/d4', 'slots': {'amount': 400, 'status': 'open'}}])
    stale = w.read('/c/x' + cell, 'x')['properties']
    expect('3 after a write under the input the ask is stale: /x empty, context says re-asking with both cases', (w.read('/x' + cell, 'x')['exists'], stale.get('/sys/view/asking', '').startswith('re-asking fake: answer at case')), (False, True))
    expect('3 the hand re-answers', hand.tick(), 1)
    again = w.read('/x' + cell, 'x')['properties']
    expect('3 the new answer carries the new stamp and the new total', (again['/case'] == stale['/sys/tack/case'], again['/answer'].startswith('4 records, amount total 1000')), (True, True))
    expect('3 the answer\'s history keeps both stamps', [v['properties']['/case'] for v in w.tool('history', path=cell + '/result')['versions']], [again['/case'], answer['properties']['/case']])

    # 4. a cell over an ask composes
    picked = home + '/views/picked'
    w.tool('write', records=[{'path': picked, 'slots': {'sys/weft': stdlib['pick'], 'sys/tack': ask_hand.live('/x' + cell, 'x'), 'from': '/model', 'into': '/judged_by'}}])
    expect('4 a pick over the ask reads the model off the stamped answer', w.read('/x' + picked, 'x')['properties']['/judged_by'], 'fake')

    # 5. changing the prompt or the model re-asks; lineage shows which
    w.tool('write', records=[{'path': cell, 'action': 'poke', 'slots': {'prompt': 'Which deal is largest?'}}])
    expect('5 a new prompt makes the ask stale and says so', 'prompt changed' in w.read('/c/x' + cell, 'x')['properties'].get('/sys/view/asking', ''), True)
    expect('5 the hand answers the new prompt', hand.tick(), 1)
    expect('5 lineage: the answer names the model, the case and the prompt it came from', (w.read('/x' + cell, 'x')['properties']['/prompt'], w.read('/x' + cell, 'x')['properties']['/model']), ('Which deal is largest?', 'fake'))
    print(json.dumps({'checks': len(checks), 'hand_calls': w.seq}), flush=True)
