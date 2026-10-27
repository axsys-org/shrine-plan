"""The hands a world runs: named in its descriptor (world.json), started after the foot listens, each its own process
with its log beside the world's, stopped at teardown. A hand not listed does not run."""
import shlex
import subprocess
import sys
from pathlib import Path

HANDS_DIR = Path(__file__).resolve().parent.parent / 'extras' / 'mounts' / 'mcp' / 'hands'


def parse_hand(text):
    """'clock --timezone UTC' -> {'name': 'clock', 'args': ['--timezone', 'UTC']}."""
    parts = shlex.split(text)
    if not parts or not parts[0].replace('_', '').isalnum():
        raise ValueError(f'--hand takes a hand name and its arguments, not {text!r}')
    return {'name': parts[0], 'args': parts[1:]}


def hand_commands(hands, url, node, hands_dir=HANDS_DIR):
    """The argv of every listed hand; a hand that has no script is an error before anything starts."""
    out = []
    for hand in hands:
        script = Path(hands_dir) / (hand['name'] + '.py')
        if not script.is_file():
            raise ValueError(f"no hand called {hand['name']} in {hands_dir}")
        out.append([sys.executable, str(script), url, '--node', node, *hand.get('args', [])])
    return out


def start_hands(hands, url, node, work, cleanup, hands_dir=HANDS_DIR):
    """Start every listed hand as its own process, logging to <work>/hands/<name>.log; stopped through cleanup."""
    started = []
    logs = Path(work) / 'hands'
    logs.mkdir(exist_ok=True)
    for hand, command in zip(hands, hand_commands(hands, url, node, hands_dir)):
        log = cleanup.enter_context((logs / (hand['name'] + '.log')).open('a'))
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, cwd=work, text=True)
        cleanup.callback(stop_hand, process)
        started.append((hand['name'], process, logs / (hand['name'] + '.log')))
    return started


def stop_hand(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
