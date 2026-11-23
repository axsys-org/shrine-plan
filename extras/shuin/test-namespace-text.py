#!/usr/bin/env python3
"""Lossless reflection-driven encoding checks against a disposable Shrine world."""
import argparse
import json
import urllib.error
import urllib.request


def request(server, **body):
    try:
        with urllib.request.urlopen(server + '/shuin-test', json.dumps(body).encode(), timeout=120) as response:
            return response.read().decode()
    except urllib.error.HTTPError as error:
        raise AssertionError(error.read().decode()) from error


def source_names(text):
    # The seed writer emits canonical definition paths. The test-only Foil
    # evaluator imports modules; preserve columns when adapting those names.
    for full, short in [('0x11/lib/shuin_commentary/', ''),
                        ('0x11/lib/shuin_agents_test/', ''),
                        ('sys/types/', '')]:
        text = text.replace(full, ' ' * (len(full) - len(short)) + short)
    return text


def check(server):
    results = []
    samples = ['', 'שלום — English', 'first\n  second\n\nlast\n', '\nleading\n', 'a\tb\0c']
    for sample in samples:
        atom = str(int.from_bytes(sample.encode(), 'little'))
        for index in range(5):
            fields = dict(operation='codec_commentary', index=str(index), atom=atom)
            literal = request(server, **fields)
            assert request(server, source=source_names(literal), **fields) == 'Equal', literal
            results.append({'kind': 'commentary', 'index': index, 'bytes': len(sample.encode())})
        for variant in ['filled', 'empty']:
            fields = dict(operation='codec_generic', atom=atom, variant=variant)
            literal = request(server, **fields)
            assert request(server, source=source_names(literal), **fields) == 'Equal', literal
            results.append({'kind': 'generic_nested', 'variant': variant, 'bytes': len(sample.encode())})
        print(f'PASS round trips for {sample!r}', flush=True)
    rejection = request(server, operation='codec_reject')
    assert '/codec slot /test' in rejection and 'callback' in rejection, rejection
    exported = request(server, operation='export', path='/0x11/app/talmud')
    assert 'shuin_commentary/library' in exported and 'shuin_commentary/passage' in exported, exported
    assert 'ברכות' in exported or 'מאימתי' in exported, exported
    context = request(server, operation='commentary_context')
    assert 'shuin_commentary/library' in context and 'shuin_commentary/passage' in context, context
    return {'round_trips': results, 'rejection': rejection,
            'talmud_export_bytes': len(exported.encode()), 'tool_context_bytes': len(context.encode())}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--server', required=True)
    p.add_argument('--output')
    args = p.parse_args()
    results = check(args.server)
    text = json.dumps(results, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, 'w') as output:
            output.write(text + '\n')
    print(text)
