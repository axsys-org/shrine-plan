#!/usr/bin/env python3
"""x/foil-lint [FILE.foil ...] [--changed | --staged] [--json]
              [--warnings-as-errors] [--rule ID[,ID]] [--no-rule ID[,ID]]
              [--no-text-checks] [--baseline FILE] [--write-baseline FILE]

Style linter for .foil files (style-guide.md).  One wisp session, warmed
from the x/check template, compiles src/foil/lint.foil once, parses each
file with the native Rex reader and applies lint/check_all; this script
adds the two text-level rules a Rex tree cannot see (tabs,
trailing-space), filters rules, sorts, and prints

    path:line:col: level rule: message

Default corpus: every tracked *.foil except the schemagen outputs
(open_router_api*) and src/foil-bad/ (deliberately broken fixtures).
Rules the guide still marks TODO (lapidary, ufcs-lift) are off unless
named with --rule.

Exit 0 when clean or warnings only, 1 when any error remains, 2 on a
tooling failure (no wisp, no template, unfinished session, unknown rule).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_runner as tr  # noqa: E402

ROOT = tr.ROOT
GENERATED = {'extras/mounts/openrouter/open_router_api.foil',      # foil-test-deps.rvr:12
             'extras/mounts/openrouter/open_router_api_hand.foil'}
TEXT_RULES = ('tabs', 'trailing-space')
TEXT_LEVEL = {'tabs': 'error', 'trailing-space': 'warning'}

# The session: the foil-rex-tests recipe (fixture roots, no --node),
# then one ("LD" path line col level rule msg) per finding and one
# ("LF" path errors warnings) per file.  Every field is a cord; nats go
# through showNat because the printer shows a printable nat as text.
SESSION = r'''
(#bind std (#module std))
(#import std)
(#bind reef (#module reef))
(#import reef)
(#bind rex (#module rex))
(#bind foil (#module foil-new-env))
(#bind source (#module foil-source))
(#bind fixture (#module foil-test-context))
(#bind render (#module foil-render))
(define (ms-since start) (Div (Sub (Now 0) start) 1000000))
(define t-compile (Now 0))
(define loaded (Seq t-compile (source:compile (fixture:files 0 ["lint"]) 0 "lint")))
(define lint-sut (foil:perc-subject (_1 loaded)))
(define lint-check (foil:source-entry-val ["lint" "check_all"] lint-sut))
(define (optional-row path)
  (let ((r (Try (lambda (z) (force (foil:source-entry-val path lint-sut))) 0)))
    (If (Eq 1 (Hd r)) [] (_0 r))))
(Seq (DeepSeq lint-check 0)
  (Seq (DeepSeq (map (lambda (n) (print ("LR" n))) (optional-row ["lint" "default_rules"])) 0)
    (Seq (DeepSeq (map (lambda (n) (print ("LA" n))) (optional-row ["lint" "all_rules"])) 0)
      (print ("LINT-READY" (showNat (ms-since t-compile)))))))
;; lint/diag is a record: (_0 d)=span [line col offset length]
;; (_1 d)=rule (_2 d)=level (_3 d)=message.  The message gets the
;; test-runner's "~:" prefix so an empty cord still prints as an atom.
(define (say-diag path d)
  (print ("LD" path (showNat (_0 (_0 d))) (showNat (_1 (_0 d)))
           (_2 d) (_1 d) (strWeld "~:" (_3 d)))))
(define (say-fail path line col rule msg)
  (Seq (print ("LD" path (showNat line) (showNat col) "error" rule (strWeld "~:" msg)))
    (print ("LF" path "1" "0"))))
;; a reader error is ("rex" [msg "line" n "col" m]); anything else
;; renders plain, as x/foil-check does
(define (say-parse-error path e)
  (define m (If (And (IsApp e) (Eq "rex" (Hd e))) (_0 e) 0))
  (If (And (IsApp m) (Eq 5 (Sz m)))
    (say-fail path (_2 m) (_4 m) "parse" (_0 m))
    (say-fail path 0 0 "parse" (render:render-plain e))))
(define (lint-one path)
  (define text (read-text-file path))
  (If (Eq 0 (Bytes text))
    (say-fail path 0 0 "io" "empty or unreadable (outside --file-root?)")
    (let ((r (Try (lambda (z)
                (let ((report (lint-check (force (rex:ParseRexFile text)))))
                  (DeepSeq report report))) 0)))
      (If (Eq 1 (Hd r))
        (say-parse-error path (_0 r))
        (let ((report (_0 r)))
          (Seq (DeepSeq (map (say-diag path) (_0 report)) 0)
            (Seq (DeepSeq (map (say-diag path) (_1 report)) 0)
              (print ("LF" path (showNat (Sz (_0 report)))
                       (showNat (Sz (_1 report))))))))))))
;; One top-level call: nested prints are not echoed by the REPL.
(define (lint-all paths)
  (define start (Now 0))
  (Seq start
    (Seq (DeepSeq (map lint-one paths) 0)
      (Seq (print ("LINT-DONE" (showNat (Sz paths)) (showNat (ms-since start)))) 0))))
(lint-all [@FILES@])
'''

LD = re.compile(r'^\("LD"\s+' + r'\s+'.join([tr.ATOM] * 6) + r'\s*\)', re.M)
LF = re.compile(r'^\("LF"\s+' + r'\s+'.join([tr.ATOM] * 3) + r'\s*\)', re.M)
LR = re.compile(r'^\("LR"\s+' + tr.ATOM + r'\s*\)', re.M)
LA = re.compile(r'^\("LA"\s+' + tr.ATOM + r'\s*\)', re.M)
READY = re.compile(r'^\("LINT-READY"\s+' + tr.ATOM, re.M)
DONE = re.compile(r'^\("LINT-DONE"\s+' + tr.ATOM + r'\s+' + tr.ATOM, re.M)


def fail(code, message):
    print('x/foil-lint: ' + message, file=sys.stderr)
    sys.exit(code)


def git_lines(command, *options, paths=('*.foil',)):
    # -z must come before the pathspec separator or git reads it as a path
    out = subprocess.run(['git', '-C', str(ROOT), command, '-z', *options, '--', *paths],
                         check=True, capture_output=True, text=True).stdout
    return [p for p in out.split('\0') if p]


def tracked_foil():
    try:
        files = git_lines('ls-files')
        if files:
            return files
    except (OSError, subprocess.CalledProcessError):
        pass
    # nix flake check copies the tree without .git: walk instead
    return sorted(str(p.relative_to(ROOT)) for top in ('src', 'extras')
                  for p in (ROOT / top).rglob('*.foil'))


def select_files(args):
    if args.files:
        files = []
        for name in args.files:
            path = Path(name).resolve()
            if not path.is_relative_to(ROOT) or not path.is_file():
                fail(2, f'{name}: not a file inside {ROOT}')
            files.append(str(path.relative_to(ROOT)))
        return files
    if args.changed or args.staged:
        names = git_lines('diff', '--name-only', '--diff-filter=ACMR',
                          *(['--cached'] if args.staged else ['HEAD']))
        if args.changed:
            names += git_lines('ls-files', '--others', '--exclude-standard')
        return sorted({p for p in names if (ROOT / p).is_file()})
    return [p for p in tracked_foil()
            if not p.startswith('src/foil-bad/') and p not in GENERATED]


def session_path(repo_path):
    # ReadFile is jailed to --file-root: paths must be root-relative
    if repo_path.startswith('src/'):
        return repo_path[len('src/'):]
    if repo_path.startswith('extras/'):
        return repo_path
    fail(2, f'{repo_path}: outside src/ and extras/, unreachable from the file root')


def run_session(files, timeout):
    wisp = os.environ.get('WISP') or shutil.which('wisp') or str(ROOT / 'wisp')
    if not os.access(wisp, os.X_OK):
        fail(2, f'no wisp on PATH and no {ROOT}/wisp (enter the dev shell or set WISP)')
    template = (Path(os.environ['TEST_TEMPLATE']) if os.environ.get('TEST_TEMPLATE')
                else ROOT / '.check' / ('template-' + tr.compiler_key(wisp)))
    if not (template / 'data.mdb').exists():
        fail(2, 'no matching compiler/runtime template - run x/check --fast first')
    source = Path(os.environ.get('TEST_SOURCE_ROOT') or ROOT / 'src')
    if os.environ.get('TEST_RUN_DIR'):
        work = Path(tempfile.mkdtemp(prefix='foil-lint-', dir=os.environ['TEST_RUN_DIR']))
    else:
        work = ROOT / '.check' / 'foil-lint'
        shutil.rmtree(work, ignore_errors=True)
        work.mkdir(parents=True)
    tr.copy_template(template, work / 'snap')
    if any(p.startswith('extras/') for p in files):
        # Merged root: extras live outside src and the file-root jail
        # follows symlinks.  copytree keeps mtimes (copy2), which the
        # .rvr module cache's Stamp check needs to stay warm.
        root = work / 'root'
        shutil.copytree(source, root, ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copytree(ROOT / 'extras', root / 'extras')
    else:
        root = source
    paths = [session_path(p) for p in files]
    script = SESSION.replace('@FILES@', ' '.join(tr.rvr_string(p) for p in paths))
    code, complete, _ = tr.run_process([wisp, '--file-root', str(root), 'snap', 'root', '_'],
                                       work, script, timeout)
    log = (work / 'out.log').read_text(errors='replace')
    if not (complete and READY.search(log) and DONE.search(log)):
        error = tr.ERROR.search(log)
        detail = log[error.start():error.start() + 2000] if error else ('timeout' if not complete else '')
        why = 'compile of lint.foil failed' if not READY.search(log) else 'session unfinished'
        fail(2, f'{why} (exit={code}) - see {work}/out.log\n{detail}')
    return log, dict(zip(paths, files)), work


def parse_log(log):
    diags, prev = [], None
    for m in LD.finditer(log):
        row = tuple(tr.decode_atom(x) for x in m.groups())
        if row == prev:          # REPL echo / merged-stream duplicates
            continue
        prev = row
        path, line, col, level, rule, msg = row
        diags.append(dict(file=path, line=int(line), col=int(col), level=level, rule=rule,
                          msg=msg[2:] if msg.startswith('~:') else msg))
    linted = {tr.decode_atom(m.group(1)) for m in LF.finditer(log)}
    default_rules = {tr.decode_atom(m.group(1)) for m in LR.finditer(log)}
    all_rules = {tr.decode_atom(m.group(1)) for m in LA.finditer(log)}
    timing = dict(compile_ms=int(tr.decode_atom(READY.search(log).group(1))),
                  lint_ms=int(tr.decode_atom(DONE.search(log).group(2))))
    return diags, linted, default_rules, all_rules, timing


def text_checks(repo_path):
    # Text-level rules: the guide forbids tabs; trailing whitespace is a
    # freebie a Rex tree cannot see.
    out = []
    for n, line in enumerate((ROOT / repo_path).read_text(errors='replace').split('\n'), 1):
        if '\t' in line:
            out.append(dict(file=repo_path, line=n, col=line.index('\t') + 1,
                            level=TEXT_LEVEL['tabs'], rule='tabs',
                            msg='tab character (text-level check)'))
        stripped = line.rstrip(' \t')
        if stripped != line:
            out.append(dict(file=repo_path, line=n, col=len(stripped) + 1,
                            level=TEXT_LEVEL['trailing-space'], rule='trailing-space',
                            msg='trailing whitespace (text-level check)'))
    return out


def counts_by_file_rule(diags):
    table = {}
    for d in diags:
        table.setdefault(d['file'], {})
        table[d['file']][d['rule']] = table[d['file']].get(d['rule'], 0) + 1
    return table


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('files', nargs='*')
    ap.add_argument('--changed', action='store_true', help='worktree changes vs HEAD plus untracked')
    ap.add_argument('--staged', action='store_true', help='index vs HEAD (pre-commit)')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--warnings-as-errors', action='store_true')
    ap.add_argument('--rule', action='append', default=[], help='only these rule ids (comma separated, repeatable)')
    ap.add_argument('--no-rule', action='append', default=[], help='drop these rule ids')
    ap.add_argument('--no-text-checks', action='store_true')
    ap.add_argument('--baseline', help='JSON {file: {rule: count}}; only counts above it fail')
    ap.add_argument('--write-baseline', help='write the current counts as a baseline and exit 0')
    ap.add_argument('--timeout', type=float, default=1800)
    args = ap.parse_args(argv)
    files = select_files(args)
    if not files:
        print('x/foil-lint: no files selected')
        return 0
    log, back, work = run_session(files, args.timeout)
    diags, linted, default_rules, all_rules, timing = parse_log(log)
    missing = [p for p in back if p not in linted]
    if missing:
        fail(2, f'{len(missing)} file(s) produced no verdict (see {work}/out.log): ' + ' '.join(missing[:5]))
    for d in diags:
        d['file'] = back.get(d['file'], d['file'])
    if not args.no_text_checks:
        for repo_path in files:
            diags += text_checks(repo_path)
    only = {r for spec in args.rule for r in spec.split(',') if r}
    drop = {r for spec in args.no_rule for r in spec.split(',') if r}
    known = all_rules | set(TEXT_RULES) | {'parse', 'io'}
    unknown = (only | drop) - known if all_rules else set()
    if unknown:
        fail(2, 'unknown rule id(s): ' + ', '.join(sorted(unknown)))
    if default_rules:
        drop |= (all_rules - default_rules) - only
    diags = [d for d in diags if (not only or d['rule'] in only) and d['rule'] not in drop]
    if args.warnings_as_errors:
        for d in diags:
            d['level'] = 'error'
    diags.sort(key=lambda d: (d['file'], d['line'], d['col'], d['rule']))
    if args.write_baseline:
        Path(args.write_baseline).write_text(json.dumps(counts_by_file_rule(diags), indent=1, sort_keys=True) + '\n')
        print(f'x/foil-lint: wrote baseline for {len(files)} files to {args.write_baseline}')
        return 0
    over = []
    if args.baseline:
        allowed = json.loads(Path(args.baseline).read_text())
        for file, rules in counts_by_file_rule(diags).items():
            for rule, n in rules.items():
                cap = allowed.get(file, {}).get(rule, 0)
                if n > cap:
                    over.append((file, rule, n, cap))
    errors = sum(d['level'] == 'error' for d in diags)
    warnings = len(diags) - errors
    summary = (f'{errors} errors, {warnings} warnings in {len(files)} files '
               f'(compile {timing["compile_ms"]} ms, lint {timing["lint_ms"]} ms)')
    if args.json:
        json.dump(diags, sys.stdout, indent=1)   # keys mirror wire-json jdiags + file/level/rule
        print()
        print(summary, file=sys.stderr)
    else:
        for d in diags:
            print(f"{d['file']}:{d['line']}:{d['col']}: {d['level']} {d['rule']}: {d['msg']}")
        print(summary)
    if args.baseline:
        for file, rule, n, cap in over:
            print(f'{file}: {rule}: {n} findings, baseline allows {cap}', file=sys.stderr)
        print(f'x/foil-lint: {len(over)} (file, rule) count(s) above the baseline', file=sys.stderr)
        return 1 if over else 0
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
