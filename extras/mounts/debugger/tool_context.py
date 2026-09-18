"""Locate core compiler tools and assemble isolated application test fixtures."""
import os
from pathlib import Path
import sys
import tempfile

BAG = Path(__file__).resolve().parent
EXTRAS = BAG.parents[1]
CORE = Path(os.environ.get('SHRINE_CORE_ROOT', EXTRAS.parent)).resolve()
sys.path.insert(0, str(CORE / 'x'))
sys.path.insert(0, str(EXTRAS / 'x'))
from fixture_sources import materialize

def fixture_repository():
    root = Path(tempfile.mkdtemp(prefix='shrine-debug-fixture-'))
    materialize(CORE, EXTRAS, root / 'src')
    return root
