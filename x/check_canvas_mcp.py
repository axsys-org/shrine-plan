#!/usr/bin/env python3
"""Continue an already-open native Canvas candidate through actual MCP stdio."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--connection', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    with subprocess.Popen([sys.executable, str(root/'extras/mounts/canvas/mcp.py'),
                           '--connection', str(args.connection)], stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE, text=True) as process:
        def exchange(identity, method, params):
            message = dict(jsonrpc='2.0', method=method, params=params)
            if identity is not None:
                message['id'] = identity
            process.stdin.write(json.dumps(message)+'\n'); process.stdin.flush()
            if identity is None:
                return None
            reply = json.loads(process.stdout.readline())
            assert reply['id'] == identity and 'error' not in reply, reply
            assert not reply['result'].get('isError'), reply
            return reply['result']
        initialized = exchange(1, 'initialize', dict(protocolVersion='2025-06-18',
                capabilities={}, clientInfo=dict(name='canvas-acceptance', version='1')))
        exchange(None, 'notifications/initialized', {})
        before = exchange(2, 'tools/call', dict(name='read', arguments={}))['structuredContent']
        assert before['candidate'], 'Begin a candidate in Canvas first'
        repaired = exchange(3, 'tools/call', dict(name='continue_candidate', arguments=dict(
            operation='stage', expected=before['expected'], event=str(uuid.uuid4()),
            body=dict(turnaround='15', same_person='true',
                      intent='Preserve the demonstrated same-person continuation.'))))['structuredContent']
        after = exchange(4, 'tools/call', dict(name='read', arguments={}))['structuredContent']
        assert repaired['candidate']['admissible']
        assert after['candidate'] == repaired['candidate']
        assert after['revision'] == before['revision']
        assert after['policy'] == before['policy']
        process.stdin.close()
        assert process.wait(timeout=10) == 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dict(status='passed', completed=time.time(),
        protocol=initialized['protocolVersion'], installed_revision=after['revision'],
        previous_candidate=before['candidate'], repaired_candidate=after['candidate'],
        commitments=after['commitments'], checks=['real MCP stdio initialization',
        'continue existing native candidate', 'native read sees the repaired candidate',
        'installed policy and revision unchanged']), indent=2)+'\n')
    print('MCP continuation verified:', args.output)


if __name__ == '__main__':
    main()
