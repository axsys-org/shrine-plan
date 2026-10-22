#!/usr/bin/env python3
"""Sequential, warmed reference/span comparisons on an identical deterministic replay."""
import argparse
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--sizes', nargs='+', default=['48x30', '96x60'])
    parser.add_argument('--runs', type=int, default=2)
    parser.add_argument('--frames', type=int, default=100)
    parser.add_argument('--warmup', type=int, default=10)
    args = parser.parse_args()
    if args.runs < 1 or not 0 <= args.warmup < args.frames <= 220:
        parser.error('runs >= 1 and 0 <= warmup < frames <= 220 required')
    sizes = []
    for size in args.sizes:
        try:
            width, height = map(int, size.split('x'))
        except ValueError:
            parser.error('sizes must be WIDTHxHEIGHT')
        if not 16 <= width <= 320 or not 16 <= height <= 200:
            parser.error('resolution must be 16..320 by 16..200')
        sizes.append((width, height))
    args.out.mkdir(parents=True, exist_ok=True)
    report = dict(platform=platform.platform(), machine=platform.machine(),
                  runtime=os.environ.get('WISP', 'wisp on PATH'), frames=args.frames,
                  warmup=args.warmup, replay='demo.json', runs=[], comparisons=[])
    expected_states = None
    for width, height in sizes:
        measured = {name: [] for name in ('reference', 'spans')}
        hashes = {}
        for run in range(args.runs):
            # Alternate order to reduce systematic warm/thermal bias. Never run concurrently.
            order = ('reference', 'spans') if run % 2 == 0 else ('spans', 'reference')
            for renderer in order:
                stem = f'{width}x{height}-{renderer}-{run + 1}'
                profile = args.out / (stem + '.json')
                command = [sys.executable, str(HERE / 'terminal.py'), '--headless',
                           '--script', str(HERE / 'demo.json'), '--frames', str(args.frames),
                           '--width', str(width), '--height', str(height), '--renderer', renderer,
                           '--warmup', str(args.warmup), '--profile', str(profile),
                           '--state', str(args.out / (stem + '-state.json')),
                           '--ppm', str(args.out / (stem + '.ppm'))]
                subprocess.run(command, check=True)
                data = json.loads(profile.read_text())
                if expected_states is None:
                    expected_states = data['states']
                if data['states'] != expected_states:
                    raise RuntimeError(f'Gameplay diverged: {stem}')
                if renderer in hashes and hashes[renderer] != data['frame_hashes']:
                    raise RuntimeError(f'Renderer is nondeterministic: {stem}')
                hashes[renderer] = data['frame_hashes']
                summary = data['summary']
                measured[renderer].append(summary['roundtrip']['mean_ms'])
                report['runs'].append(dict(name=stem, width=width, height=height,
                                           renderer=renderer, summary=summary,
                                           final_frame_sha256=data['frame_hashes'][-1]))
                print(stem, json.dumps(summary['roundtrip']), flush=True)
                (args.out / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
        before = statistics.mean(measured['reference'])
        after = statistics.mean(measured['spans'])
        report['comparisons'].append(dict(width=width, height=height,
                                          reference_ms=before, spans_ms=after, speedup=before / after))
    (args.out / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report['comparisons'], indent=2))


if __name__ == '__main__':
    main()
