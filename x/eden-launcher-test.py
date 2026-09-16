"""Isolated launcher regressions; never starts Wisp or opens a network port.

Run with python3 x/eden-launcher-test.py. Only the pure exit-status helper
is compiled from the launcher AST, so importing the CLI cannot boot Eden.
"""
import ast
import contextlib
import io
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import unittest


LAUNCHER = Path(__file__).with_name('eden')
TREE = ast.parse(LAUNCHER.read_text(), filename=str(LAUNCHER))
HELPER = next(node for node in TREE.body
              if isinstance(node, ast.FunctionDef)
              and node.name == 'runtime_exit_status')
namespace = {'signal': signal, 'sys': sys}
exec(compile(ast.Module(body=[HELPER], type_ignores=[]), str(LAUNCHER), 'exec'),
     namespace)
runtime_exit_status = namespace['runtime_exit_status']
POPEN = next(node for node in ast.walk(TREE)
             if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Attribute)
             and isinstance(node.func.value, ast.Name)
             and node.func.value.id == 'subprocess'
             and node.func.attr == 'Popen')
OPTIONS = {item.arg: item.value for item in POPEN.keywords}


class LauncherTests(unittest.TestCase):
    def report(self, returncode):
        output = io.StringIO()
        with contextlib.redirect_stderr(output):
            code = runtime_exit_status(returncode, '/test/eden/out.log')
        return code, output.getvalue()

    def test_launcher_preserves_ignored_sigpipe(self):
        self.assertIs(ast.literal_eval(OPTIONS['restore_signals']), False)

    @unittest.skipUnless(os.name == 'posix' and hasattr(signal, 'SIGPIPE'),
                         'SIGPIPE is a POSIX behavior')
    def test_closed_reader_does_not_signal_the_native_child(self):
        # A native writer matters: a Python child would independently ignore
        # SIGPIPE and could accidentally hide a broken Popen configuration.
        writer = shutil.which('yes')
        if not writer:
            self.skipTest('native yes utility unavailable')
        self.assertEqual(signal.getsignal(signal.SIGPIPE), signal.SIG_IGN)

        def write_to_closed_pipe(restore_signals):
            reader, output = os.pipe()
            os.close(reader)
            try:
                process = subprocess.Popen(
                    [writer], stdout=output, stderr=subprocess.DEVNULL,
                    restore_signals=restore_signals)
            finally:
                os.close(output)
            try:
                return process.wait(timeout=5)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()

        self.assertEqual(write_to_closed_pipe(True), -signal.SIGPIPE,
                         'control proves the native writer receives SIGPIPE')
        actual = write_to_closed_pipe(ast.literal_eval(OPTIONS['restore_signals']))
        self.assertGreater(actual, 0,
                           'ignored SIGPIPE becomes an ordinary write error')

    def test_abnormal_exit_code_is_preserved_and_reported(self):
        code, text = self.report(9)
        self.assertEqual(code, 9)
        self.assertIn('status 9', text)
        self.assertIn('/test/eden/out.log', text)

    def test_signal_name_and_shell_status_are_reported(self):
        code, text = self.report(-signal.SIGTERM)
        self.assertEqual(code, 128 + signal.SIGTERM)
        self.assertIn('SIGTERM', text)
        self.assertIn(f'signal {signal.SIGTERM}', text)

    def test_unknown_signal_still_reports_its_number(self):
        code, text = self.report(-99)
        self.assertEqual(code, 227)
        self.assertIn('signal 99', text)

    def test_clean_exit_remains_zero(self):
        code, text = self.report(0)
        self.assertEqual(code, 0)
        self.assertIn('status 0', text)

    def test_wait_status_is_used_by_the_launcher(self):
        exits = [node for node in ast.walk(TREE)
                 if isinstance(node, ast.Raise)
                 and isinstance(node.exc, ast.Call)]
        self.assertTrue(any(
            ast.unparse(node.exc) ==
            'SystemExit(runtime_exit_status(process.wait(), log_path))'
            for node in exits))


if __name__ == '__main__':
    unittest.main()
