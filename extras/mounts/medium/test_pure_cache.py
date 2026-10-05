"""Pinned pure results survive reload; inputs and revisions cannot alias."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import behaviors

class PureCacheTest(unittest.TestCase):
    def test_identity_and_revision_are_part_of_the_key(self):
        with tempfile.TemporaryDirectory() as directory:
            server=SimpleNamespace(world=Path(directory))
            descriptor={'surface':'/0x11/app/user/pure_example/surface','implementation':'revision-1'}
            frame={'basis':{'implementation':'revision-1'}}
            with patch.object(behaviors,'call',return_value=frame) as native, patch.object(behaviors,'output',return_value=[{'id':'a','value':True}]):
                first=behaviors.evaluate(server,descriptor,{'id':'a','rows':[]})
                second=behaviors.evaluate(server,descriptor,{'id':'a','rows':[]})
                self.assertEqual(first['value'],second['value'])
                self.assertTrue(second['cached'])
                self.assertEqual(native.call_count,1)
                behaviors.evaluate(server,descriptor,{'id':'b','rows':[]})
                self.assertEqual(native.call_count,2)
                with self.assertRaisesRegex(ValueError,'revision changed'):
                    behaviors.evaluate(server,{**descriptor,'implementation':'revision-2'},{'id':'a','rows':[]})

if __name__=='__main__':unittest.main()
