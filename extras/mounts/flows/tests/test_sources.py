import io
import json
from pathlib import Path
import runpy
import unittest
from unittest.mock import patch

api = runpy.run_path(str(Path(__file__).parent / 'client.py'))


class NativeSourceTests(unittest.TestCase):
    def response(self, text, *, myth=None, duplicate=False):
        control = {'id': 'source:4', 'kind': 'input', 'slot': '/source'}
        return {'controls': [control] * (2 if duplicate else 1), 'display': {'nodes': [{
            'id': 'source:4', 'editing': {'encoding': 'goo-text-v1'},
            'textRuns': [{'myth': myth or {}, 'lang': {'en': {'txt': text}}}]}]}}

    def read(self, payload):
        response = io.BytesIO(json.dumps(payload).encode())
        opener = unittest.mock.Mock(return_value=response)
        with patch.dict(api['FlowClient'].source.__globals__, urlopen=opener):
            result = api['FlowClient']('http://disposable.test').source('/0x11/app/nenex/w/source')
        request = opener.call_args.args[0]
        self.assertEqual(request.full_url, 'http://disposable.test/goo/render')
        self.assertIn(b'view=%2F0x11%2Fgov%2Fnenex_tools%2Fsource_view', request.data)
        return result

    def test_native_source_preserves_complete_authored_text(self):
        text = ';.\r\n  Source & <tags> </textarea>\n' + ('  Long source\n' * 1000)
        self.assertEqual(text, self.read(self.response(text)))

    def test_ambiguous_or_formatted_source_is_refused(self):
        for payload in [self.response('source', duplicate=True),
                        self.response('source', myth={'/sys/modifiers': {'kind': 'modifiers', 'value': ['bold']}})]:
            with self.assertRaises(ValueError):
                self.read(payload)


if __name__ == '__main__':
    unittest.main()
