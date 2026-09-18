"""Run Codex checks through the extras inventory."""
from pathlib import Path
import subprocess
import sys
root = Path(__file__).resolve().parents[2]
raise SystemExit(subprocess.call([sys.executable, str(root / 'x/check'), '--mount', 'codex', *sys.argv[1:]]))
