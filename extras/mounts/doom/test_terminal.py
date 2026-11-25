"""Device-boundary tests; the Foil suite covers game behavior."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('doom_terminal', Path(__file__).with_name('terminal.py'))
terminal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(terminal)


class Chunks:
    def __init__(self, chunks):
        self.chunks = iter(chunks)

    def recv(self, size):
        return next(self.chunks, b'')


class TerminalTests(unittest.TestCase):
    def test_partial_reads_preserve_nuls(self):
        self.assertEqual(terminal.recv_exact(Chunks([b'\0', b'a', b'\0']), 3), b'\0a\0')

    def test_disconnect_is_an_error(self):
        with self.assertRaises(RuntimeError):
            terminal.recv_exact(Chunks([b'a']), 2)

    def test_key_mask_matches_native_protocol(self):
        self.assertEqual(terminal.mask('wfr'), 321)
        self.assertEqual(terminal.mask('ww'), 1)
        with self.assertRaises(ValueError):
            terminal.mask('x')

    def test_column_major_ppm(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'frame.ppm'
            palette = bytes([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])
            terminal.ppm(path, bytes([0, 1, 2, 3]), palette, 2, 2)
            self.assertEqual(path.read_bytes(), b'P6\n2 2\n255\n' + bytes([1, 2, 3, 7, 8, 9, 4, 5, 6, 10, 11, 12]))

    def test_profile_units_and_warm_summary(self):
        samples = terminal.parse_profile('noise\n"DOOM_PROFILE 1 1000000 2000000 3000000 4000 5000"\n'
                                         '"DOOM_PROFILE 2 2000000 4000000 6000000 8000 10000"')
        self.assertEqual(samples[0]['step'], 1)
        self.assertEqual(samples[0]['pack'], .004)
        summary = terminal.summarize_profile(samples[1:], [12.5])
        self.assertEqual(summary['count'], 1)
        self.assertEqual(summary['phases']['visibility']['mean_ms'], 4)
        self.assertEqual(summary['roundtrip']['p95_ms'], 12.5)
        self.assertIsNone(terminal.summarize_profile([], [])['roundtrip'])

    def test_percentile_uses_nearest_rank(self):
        self.assertEqual(terminal.distribution(list(range(1, 101)))['p95_ms'], 95)
        self.assertEqual(terminal.distribution([3, 1, 2])['median_ms'], 2)

    def test_fragmented_arrow_does_not_quit(self):
        keyboard = terminal.Keyboard()
        with patch.object(terminal.select, 'select', return_value=([1], [], [])), \
             patch.object(terminal.os, 'read', side_effect=[b'\x1b', b'[', b'A']), \
             patch.object(terminal.time, 'monotonic', side_effect=[1, 1.01, 1.02]):
            self.assertEqual(keyboard.read(), 0)
            self.assertEqual(keyboard.read(), 0)
            self.assertEqual(keyboard.read(), 1)
        self.assertFalse(keyboard.quit)

    def test_escape_quits_after_sequence_timeout(self):
        keyboard = terminal.Keyboard()
        keyboard.pending = b'\x1b'
        with patch.object(terminal.select, 'select', return_value=([], [], [])), \
             patch.object(terminal.time, 'monotonic', side_effect=[1, 1.1]):
            keyboard.read()
            keyboard.read()
        self.assertTrue(keyboard.quit)


if __name__ == '__main__':
    unittest.main()
