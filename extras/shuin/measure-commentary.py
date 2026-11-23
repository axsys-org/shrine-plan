#!/usr/bin/env python3
"""Measure local commentary HTTP reads/selection; optionally capture state for the CPU benchmark."""
import argparse
import json
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', required=True, help='Use a disposable test world')
    parser.add_argument('--library', default='/0x11/app/talmud')
    parser.add_argument('--view', default='/0x11/gov/shuin_commentary/reader')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--state', type=Path)
    args = parser.parse_args()
    session = uuid.uuid4().hex

    def send(fields):
        fields = dict(session=session, library=args.library, view=args.view, **fields)
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(args.server.rstrip('/') + '/shuin/commentary',
                                        urllib.parse.urlencode(fields).encode(), timeout=60) as response:
                data = response.read()
        except urllib.error.HTTPError as error:
            raise SystemExit(error.read().decode()) from error
        return json.loads(data), len(data), (time.perf_counter() - start) * 1000

    state, size, opening = send(dict(operation='open'))
    samples = []
    for _ in range(12):
        state, size, elapsed = send(dict(operation='read'))
        samples.append(elapsed)
    if args.state:
        args.state.write_text(json.dumps(state))
    selections = []
    for p in state['passages'][:6]:
        quote = p['secondary'].split(' ')[0]
        state, _, elapsed = send(dict(operation='select', id=uuid.uuid4().hex,
            expected=state['revision'], publication=state['publication'], dirty='0',
            target=p['path'], life=p['life'], revision=p['revision'], language='secondary',
            start='0', end=str(len(quote.encode())), quote=quote))
        selections.append(elapsed)
    result = dict(open_ms=opening, bytes=size, read_median_ms=statistics.median(samples),
                  read_max_ms=max(samples), read_samples_ms=samples,
                  select_median_ms=statistics.median(selections), select_samples_ms=selections)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
