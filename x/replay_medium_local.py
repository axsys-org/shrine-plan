#!/usr/bin/env python3
"""Reconstruct a small, wholly retained local history into an EMPTY candidate.

This deliberately refuses truncated histories and physical actions. It does not
copy a rendered frame into a namespace, replace a running world, or claim to be a
general native migration. The original pinned world remains the recovery source.
"""
import argparse
import json
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

OPERATIONS = {'define', 'property', 'description', 'relate', 'author', 'retire',
              'instantiate', 'duplicate', 'detach', 'rebind'}


def complete_history(frame, pure_medium_actions=False):
    events = [e for e in frame['events'] if e.get('id')]
    events.reverse()
    if [int(e['basis']) for e in events] != list(range(1, int(frame['expected']))):
        raise ValueError('History is truncated or discontinuous; retain the original world.')
    if len({e['id'] for e in events}) != len(events):
        raise ValueError('Repeated event identity.')
    for event in events:
        permitted_action = (pure_medium_actions and event['kind'] == 'act' and
                            'native-definition-actions' in frame.get('features', []))
        if event['kind'] not in OPERATIONS and not permitted_action:
            raise ValueError('Unsupported replay operation: ' + event['kind'])
        json.loads(event['body'])
    return events


def call(world, port, operation='read', expected='0', event='', body=None):
    credential = (Path(world) / 'src/medium-authority').read_text()
    data = urllib.parse.urlencode(dict(credential=credential, principal='administrator',
        operation=operation, expected=str(expected), event=event,
        body=json.dumps(body or {}))).encode()
    request = urllib.request.Request(f'http://127.0.0.1:{port}/medium-native', data)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(error.read().decode()) from None


def observable(frame):
    # Cases and implementation publication pins change with the native build.
    # Records are reconstructed by native commands, never from these values.
    keys = ('id', 'label', 'source', 'intent', 'pattern', 'inputs', 'open',
            'ready', 'fields', 'relation', 'parent', 'authored')
    return [{**{key: n.get(key) for key in keys},
             'properties': [{k: p.get(k) for k in ('label', 'slot', 'value')}
                            for p in n.get('properties', [])]}
            for n in frame['nodes']]


def replay(snapshot, world, port, pure_medium_actions=False):
    events = complete_history(snapshot, pure_medium_actions)
    current = call(world, port)
    if current['nodes'] or current['expected'] != '1':
        raise ValueError('Destination must be a fresh, empty native candidate.')
    if pure_medium_actions and 'native-definition-actions' not in current.get('features', []):
        raise ValueError('Destination does not expose the required native boundary.')
    for event in events:
        if current['expected'] != event['basis']:
            raise ValueError('Native reconstruction diverged before ' + event['id'])
        body = json.loads(event['body'])
        if event['kind'] == 'act':
            # Explicit reconstruction only for the inspected medium owner: its
            # actions execute through ports.pure and cannot dispatch host I/O.
            # Rebase cases onto the new candidate, never reinterpret a journal.
            target = next(n for n in current['nodes'] if n['id'] == body['target'])
            if not any(o['kind'] == 'action' and o.get('invoke') and
                       o['control'] == body['control'] for o in target['view']['occurrences']):
                raise ValueError('Recorded native control is no longer available.')
            body = {**body, 'expected': target['expected'], 'displayed': target['displayed'],
                    'publication': current['publication']}
        current = call(world, port, event['kind'], current['expected'], event['id'], body)
    if observable(current) != observable(snapshot):
        raise ValueError('Reconstructed subjects differ; do not activate this candidate.')
    return current


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path)
    parser.add_argument('world', type=Path)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--pure-medium-actions', action='store_true',
                        help='Explicit reconstruction through the reviewed pure medium action boundary; never driver effects')
    args = parser.parse_args()
    original = json.loads(args.snapshot.read_text())
    result = replay(original, args.world, args.port, args.pure_medium_actions)
    (args.world / 'reconstructed-frame.json').write_text(json.dumps(result, indent=2))
    print(f"Verified {len(complete_history(original, args.pure_medium_actions))} retained native operations; "
          f"{len(result['nodes'])} subject identities preserved. Original world unchanged.")
