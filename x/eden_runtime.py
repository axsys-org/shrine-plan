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
    return ('HTTP foot listening' in output and bool(re.search(
        r'^\("' + re.escape(returned_marker) + r'"\s+\(0(?:\s|\))', output, re.M)))

def startup_failed(output, returned_marker):
    # Try returns (0 value) on success and (1 reason) on failure. Eden's entry
    # returns its spawned supervisor actor ID before the HTTP foot listens.
    # Success is not readiness: the caller must still prove the live listener.
    return bool(re.search(r'^\("ERROR"(?:\s|\))', output, re.M)
                or re.search(r'^\("' + re.escape(returned_marker) + r'"\s+\(1(?:\s|\))', output, re.M)
                or 'pump: listen failed' in output or 'bind/listen failed' in output)
