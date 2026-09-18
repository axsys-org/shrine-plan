"""Isolated launcher regressions; never starts Wisp or opens a network port.

Run with python3 x/eden-launcher-test.py. The CLI runs with a fake Nix executable
or stubbed build/runtime processes; the exit-status helper is compiled from its AST.
"""
import ast
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import runpy
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from debug_runtime_helpers import ASSET_PATHS


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
    def test_bootstrap_forwards_arguments_from_another_directory(self):
        with tempfile.TemporaryDirectory(prefix='eden tools ') as directory:
            directory = Path(directory)
            capture = directory / 'invocation.json'
            nix = directory / 'nix'
            nix.write_text(f'#!{sys.executable}\n'
                           'import json, os, pathlib, sys\n'
                           'pathlib.Path(os.environ["EDEN_TEST_CAPTURE"]).write_text('
                           'json.dumps({"argv": sys.argv[1:], "cwd": os.getcwd()}))\n')
            nix.chmod(0o755)
            env = dict(os.environ, PATH=str(directory), EDEN_TEST_CAPTURE=str(capture))
            env.pop('_EDEN_NIX_ROOT', None)
            for options in ([], ['--node', '0x0102', '--port', '8140', '--srs'],
                            ['--mash-root', '../mash with spaces']):
                with self.subTest(options=options):
                    subprocess.run([sys.executable, str(LAUNCHER), *options],
                                   cwd=directory, env=env, check=True, capture_output=True)
                    invocation = json.loads(capture.read_text())
                    argv = invocation['argv']
                    self.assertEqual(invocation['cwd'], str(directory.resolve()))
                    self.assertIn(f'{LAUNCHER.parent.parent}#debugger', argv)
                    self.assertIn('--no-update-lock-file', argv)
                    self.assertEqual(argv[argv.index('--command') + 1:], [
                        'env', f'_EDEN_NIX_ROOT={LAUNCHER.parent.parent}',
                        f'TMPDIR={tempfile.gettempdir()}',
                        'python3', str(LAUNCHER), *options])

    def test_help_and_invalid_arguments_do_not_require_nix(self):
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ, PATH=directory)
            env.pop('_EDEN_NIX_ROOT', None)
            for options, code in [(['--help'], 0), (['--port', '0'], 2),
                                  (['--node', '0x00'], 2), (['--debug', '--codex'], 2)]:
                with self.subTest(options=options):
                    result = subprocess.run([sys.executable, str(LAUNCHER), *options],
                                            env=env, capture_output=True, text=True)
                    self.assertEqual(result.returncode, code)
                    self.assertNotIn('requires Nix', result.stderr)
            missing = subprocess.run([sys.executable, str(LAUNCHER)],
                                     env=env, capture_output=True, text=True)
            self.assertEqual(missing.returncode, 2)
            self.assertIn('requires Nix', missing.stderr)

    def launch_stub(self, options=(), build_error=None, expected_mash_root=None):
        """Exercise the real CLI through staging and launch with an exited child."""
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            work = directory / 'work'
            work.mkdir()
            template = directory / 'template'
            template.mkdir()
            for name in ('data.mdb', 'pins.pack'):
                (template / name).touch()
            source = io.StringIO()

            def bundle(command, *, cwd, env, check):
                if build_error:
                    raise subprocess.CalledProcessError(build_error, command)
                assets = Path(env['DEBUG_OUTPUT_ROOT'])
                self.assertTrue(assets.is_relative_to(work))
                self.assertEqual(Path(command[1]), LAUNCHER.with_name('build-debug.mjs'))
                self.assertTrue(check)
                self.assertEqual(env.get('MASH_ROOT'), expected_mash_root)
                hashes = {}
                for name in ASSET_PATHS:
                    target = assets / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(b'fresh bundle')
                    hashes[name] = hashlib.sha256(target.read_bytes()).hexdigest()
                (assets / 'build.json').write_text(json.dumps({'mode': 'grove', 'assets': hashes}))

            env = dict(_EDEN_NIX_ROOT=str(LAUNCHER.parent.parent), WISP=sys.executable,
                       MASH_ROOT=str(directory / 'stale-mash-checkout'),
                       DEBUG_OUTPUT_ROOT=str(directory / 'unused-shared-assets'))
            with patch.dict(os.environ, env), patch.object(sys, 'argv', [str(LAUNCHER), *options]), \
                    patch('tempfile.mkdtemp', return_value=str(work)), \
                    patch('test_runner.stage', return_value=template) as stage, \
                    patch('subprocess.run', side_effect=bundle) as build, \
                    patch('subprocess.Popen') as popen, patch('os.execvpe') as reexec, \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                popen.return_value.stdin = source
                popen.return_value.poll.return_value = 7
                with self.assertRaises(SystemExit) as exit:
                    runpy.run_path(str(LAUNCHER), run_name='__main__')
                reexec.assert_not_called()
                self.assertNotIn('_EDEN_NIX_ROOT', os.environ)
                if build_error:
                    self.assertEqual(exit.exception.code, build_error)
                    stage.assert_not_called()
                    popen.assert_not_called()
                else:
                    self.assertEqual(exit.exception.code, 7)
                    if build.called:
                        for name in ASSET_PATHS:
                            self.assertEqual((work / 'src/foil' / name).read_bytes(), b'fresh bundle')
                return source.getvalue(), build.call_count

    def test_codex_still_selects_its_own_entry_point(self):
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ, _EDEN_NIX_ROOT=str(LAUNCHER.parent.parent))
            result = subprocess.run([
                sys.executable, str(LAUNCHER), '--codex',
                '--codex-bin', str(Path(directory) / 'missing-codex'),
            ], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn('--codex requires a Codex executable', result.stderr)
            self.assertNotIn('separate entry points', result.stderr)

    def test_plain_command_builds_and_launches_the_debugger(self):
        source, builds = self.launch_stub()
        self.assertEqual(builds, 1)
        self.assertIn('eden:start-debug ', source)
        self.assertIn('(eden:start-debug ("x" 17)', source)

    def test_mash_checkout_requires_an_explicit_option(self):
        _, builds = self.launch_stub(['--mash-root', '../mash with spaces'],
                                    expected_mash_root=str(Path('../mash with spaces').resolve()))
        self.assertEqual(builds, 1)

    def test_explorer_opt_out_and_custom_authority(self):
        source, builds = self.launch_stub(['--no-debug', '--node', '0x0102', '--port', '8140'])
        self.assertEqual(builds, 0)
        self.assertIn('(eden:start ("x" 513)', source)
        self.assertIn('slot 8140)', source)

    def test_srs_keeps_the_default_debugger(self):
        source, builds = self.launch_stub(['--srs'])
        self.assertEqual(builds, 1)
        self.assertIn('eden:start-debug-srs ', source)

    def test_failed_bundle_stops_before_compilation_or_launch(self):
        self.launch_stub(build_error=19)

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
