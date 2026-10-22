#!/usr/bin/env python3
"""Reproduce hand catch-up and restart gaps with a local fake model, without core edits."""
import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', default='http://127.0.0.1:8192')
    parser.add_argument('--output', type=Path, default=HERE / 'run/ask-probe.json')
    args = parser.parse_args()
    path = HERE.parents[2] / 'extras/mounts/mcp/hands/ask.py'
    spec = importlib.util.spec_from_file_location('probe_ask', path)
    ask = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ask)
    w = ask.World(args.server, '0x11', 120)
    base = '/0x11/user/branchmap_ask_probe'
    if w.read(base)['exists']:
        raise SystemExit('Probe namespace exists; use a fresh world.')

    class Probe(ask.AskHand):
        name = 'branchmap_ask_probe'

    log = []
    h = Probe(w, fake=True, model='fake', log=log.append)
    h.seen = 0
    start = w.epoch()
    h.catch_up()
    result = {'backlog': {'world_epoch_before': start, 'seen_after_one_catch_up': h.seen,
                          'caught_up': h.seen >= start}}
    # Isolate ordinary behavior from the backlog finding.
    h.seen = start
    w.tool('write', who='probe_setup', records=[{'path': base, 'slots': {}},
        {'path': base + '/facts', 'slots': {}}, {'path': base + '/facts/a', 'slots': {'amount': 10}}])
    ref = w.read('/0x11/weft/stdlib/ask')['reference']
    cell = base + '/answer'
    w.tool('write', who='probe_setup', records=[{'path': cell, 'slots': {
        'sys/weft': {'type': 'reference', 'value': ref}, 'sys/tack': ask.live(base + '/facts'),
        'prompt': 'Sum the observations', 'model': 'fake'}}])
    first = h.tick()
    answer = w.read('/x' + cell)
    assert first == 1 and 'amount total 10' in answer['properties']['/answer'], answer
    w.tool('write', who='probe_setup', records=[{'path': base + '/facts/a', 'action': 'poke', 'slots': {'amount': 20}}])
    updated = h.tick()
    assert updated == 1 and 'amount total 20' in w.read('/x' + cell)['properties']['/answer']
    result['uninterrupted'] = {'first_answers': first, 'updated_answers': updated, 'passed': True}
    resumed = Probe(w, fake=True, model='fake', log=log.append)
    w.tool('write', who='probe_setup', records=[{'path': base + '/facts/a', 'action': 'poke', 'slots': {'amount': 30}}])
    count = resumed.tick()
    context = w.read('/c/x' + cell)['properties']
    result['restart'] = {'answers': count, 'discovered_cells': dict(resumed.asks),
                         'context': context, 'passed': count == 1 and w.read('/x' + cell)['exists']}
    # A direct re-learn repairs this run without claiming the hand did it itself.
    resumed.learn({'with': {cell: w.read(cell)}})
    repaired = resumed.tick()
    result['manual_rediscovery'] = {'answers': repaired, 'view': w.read('/x' + cell)}
    assert repaired == 1 and 'amount total 30' in result['manual_rediscovery']['view']['properties']['/answer']
    result['log'] = log
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k in ('backlog', 'uninterrupted', 'restart')}, indent=2))


if __name__ == '__main__':
    main()
