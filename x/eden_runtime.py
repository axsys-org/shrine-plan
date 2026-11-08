import signal
import sys

def runtime_exit_status(returncode, log_path):
    """Keep a native child failure visible to people and calling tools."""
    if returncode < 0:
        number = -returncode
        try:
            name = signal.Signals(number).name
        except ValueError:
            name = 'unknown signal'
        print(f'Wisp exited due to {name} (signal {number}). Log: {log_path}',
              file=sys.stderr, flush=True)
        return 128 + number
    print(f'Wisp exited with status {returncode}. Log: {log_path}',
          file=sys.stderr, flush=True)
    return returncode

import re
def startup_ready(output, returned_marker):
    return ('HTTP foot listening' in output and bool(
        re.search(r'^\((?:0\s+)?"EDEN-READY"(?:\s|\))', output, re.M) or re.search(
        r'^\("' + re.escape(returned_marker) + r'"\s+\(0(?:\s|\))', output, re.M)))

def startup_failed(output, returned_marker):
    # Initial launch reports failures through Try; a resumed native root can
    # fail directly. Readiness separately requires the committed startup marker
    # and a listening HTTP foot.
    return bool(re.search(r'^\("ERROR"(?:\s|\))', output, re.M)
                or re.search(r'^\("' + re.escape(returned_marker) + r'"\s+\(1(?:\s|\))', output, re.M)
                or 'pump: listen failed' in output or 'bind/listen failed' in output)
