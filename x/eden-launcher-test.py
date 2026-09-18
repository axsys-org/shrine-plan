"""Launcher regression entrypoint."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).with_name('eden-mounts-test.py')), run_name='__main__')
