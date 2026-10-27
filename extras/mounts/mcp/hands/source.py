"""The source hand: one runner for every kind of source. A source is a record the agent wrote at
/user/<scope>/sources/<artifact> {where, script, key?, every?}; the hand binds it with the script named, a module in
hands/sources/<script>.py, and keeps the artifact's own structure under the record as regions:

    contents eager, content lazy   the locators the script calls contents (the parts, the sections; every locator when
                                   it has no contents()) are written on first contact as records with only `source`, and
                                   a region's content when a cell waits for it: a reference to a path under the artifact
                                   whose record has no content yet, found with `read path=<scope> referencing=<artifact>`;
                                   an eager script (rows) writes
                                   every region's content on first contact
    scoped change                  when the script's marker moves, the regions that exist are re-read; the ones whose
                                   digest moved are rewritten with if_case, the ones the source lost are culled, the
                                   rest are untouched, so the chains over them do not move
    one event                      everything a pass writes is one write signed who: source_<artifact>; a pass that
                                   finds nothing changed and no new hole writes nothing
    write-back                     a region edited in the world (its slots no longer match its digest) is written
                                   back to its own locator in the source, and only there, when the artifact record
                                   carries `write: true` and the script has `write`; the region's digest and the
                                   marker then follow. An edit while the source also moved is a conflict: logged,
                                   left alone, nothing written either way until one side is resolved

A region is the source's own content at that locator, in the script's slots, plus the three the hand owns: `source`
(a reference to the artifact record), `digest` (of the content) and the position slots the script gives (row, line,
page). Nothing else is ever written by the binding: no status, no kind, no interpretation.

Config: /agent/hands/source {folders: "/user/finance/sources /user/legal/sources", url: <webhook>}; --folders and
--url override. `url`, when set, gets one JSON POST per change {artifact, marker, written, culled, epoch}.

A script is a module with `eager` (bool) and three functions over the artifact's slots:
    marker(source) -> str                    the version read: an mtime and size, a digest, a commit, an etag
    skeleton(source) -> [path, ...]          every locator's relative path, in the source's order, nested as it is
    contents(source) -> [path, ...]          optional: the locators written eagerly (default: every one)
    regions(source, paths) -> {path: slots}  the content at those locators (a path the source lacks maps to None)
    write(source, path, slots)               optional: put these slots back into the source at that locator, touching
                                             nothing else of the source

    python3 source.py <base> [--node 0x11] [--folders "/user/x/sources"] [--url http://...] [--once]
"""
import hashlib
import importlib.util
import json
import os
import time
import urllib.request

_base = importlib.util.spec_from_file_location('hand_base', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hand.py'))
_hand = importlib.util.module_from_spec(_base); _base.loader.exec_module(_hand)
World, Hand, case_of = _hand.World, _hand.Hand, _hand.case_of

SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sources')


def load_script(name, where=SCRIPTS):
    spec = importlib.util.spec_from_file_location('source_' + name, os.path.join(where, name + '.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def post(url, payload, timeout=30):
    """The plug for `url`: one JSON POST."""
    req = urllib.request.Request(url, json.dumps(payload).encode(), {'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status


HAND_SLOTS = ('source', 'digest')


def shown(v):
    """A slot value as a read answers it, so a digest over what was written equals one over what was read back."""
    if isinstance(v, dict):
        return shown(v.get('value'))
    if isinstance(v, bool):
        return 'true' if v else 'false'
    return str(v)


def content_of(props):
    """A region's content as read: its slots without the hand's, the system's and the scales."""
    return {k.lstrip('/'): v for k, v in props.items()
            if not k.startswith('/sys') and k.lstrip('/') not in HAND_SLOTS and not k.endswith('/scale')}


def digest_of(slots):
    return hashlib.sha256(json.dumps({k: shown(v) for k, v in slots.items()}, sort_keys=True).encode()).hexdigest()[:16]


def reference(path):
    return {'type': 'reference', 'value': '/h/x/0/' + str(len(path.strip('/').split('/'))) + path}


class Source(Hand):
    name = 'source'
    every = 60.0

    def __init__(self, world, log=print, plug=post, scripts=None, **overrides):
        super().__init__(world, log=log, **overrides)
        self.plug = plug
        self.scripts = dict(scripts or {})
        self.passed = {}                                   # artifact path -> the time of its last pass

    # ---- the artifacts the hand binds
    def folders(self):
        return [f for f in (self.setting('folders') or '').split() if f]

    def artifacts(self):
        """Every record under a listed folder that names a script, with the scope the folder sits in."""
        out = []
        for folder in self.folders():
            scope = folder.rsplit('/', 1)[0]
            for ch in self.w.read(folder, 'y', limit=500).get('children', []):
                props = {k.lstrip('/'): v for k, v in (ch.get('properties') or {}).items() if not k.startswith('/sys')}
                if ch.get('exists') and props.get('script') and props.get('where'):
                    out.append((ch['path'], scope, props))
        return out

    def script(self, name):
        if name not in self.scripts:
            self.scripts[name] = load_script(name)
        return self.scripts[name]

    # ---- what the world asks for
    def holes(self, scope, artifact):
        """The relative paths under the artifact that something points at: the requests. A skeleton node is a hole
        in all but name (a record with no content), so a cell tacked at one, or a record citing one, asks for it."""
        wanted, nxt, pages = set(), None, 0
        while pages < 20:
            page = self.w.read(scope, 'y', referencing=artifact, limit=500, **({'next': nxt} if nxt else {}))
            for m in page.get('matches', []):
                target = m.get('target') or ''
                if target.startswith(artifact + '/'):
                    wanted.add(target[len(artifact) + 1:])
            nxt, pages = page.get('next'), pages + 1
            if not nxt:
                break
        return wanted

    def existing(self, artifact):
        """The regions already under the artifact: relative path -> (digest or None, x case, content as read)."""
        out = {}

        def walk(n):
            for ch in n.get('children', []):
                if ch.get('exists'):
                    props = ch.get('properties') or {}
                    out[ch['path'][len(artifact) + 1:]] = (props.get('/digest'), case_of(ch.get('reference')), content_of(props))
                walk(ch)
        walk(self.w.read_all(artifact, 'z'))
        return out

    def edited(self, existing):
        """The regions whose content no longer matches their digest: edited in the world since the hand wrote them."""
        return {p: c for p, (d, _, c) in existing.items() if d and digest_of(c) != d}

    # ---- one pass over one artifact
    def sync(self, artifact, scope, source, now):
        name = artifact.rsplit('/', 1)[1]
        every = float(source.get('every') or 0)
        if every and now - self.passed.get(artifact, -every) < every:
            return 0
        self.passed[artifact] = now
        script = self.script(source['script'])
        marker = str(script.marker(source))
        changed = marker != str(source.get('marker') or '')
        existing = self.existing(artifact)
        edited = self.edited(existing)
        held, refresh = set(), set()                       # regions edited here: left as they are; re-read for their digest
        if edited and str(source.get('write') or '').lower() == 'true' and hasattr(script, 'write'):
            current, back = script.regions(source, sorted(edited)), []
            for p in sorted(edited):
                now = current.get(p)                       # the source's own content at that locator, as it is
                if now is not None and digest_of(now) == digest_of(edited[p]):
                    refresh.add(p)                         # the world was made to match the source: the digest follows
                elif now is not None and digest_of(now) == existing[p][0]:
                    script.write(source, p, edited[p])     # the source did not move there: the edit goes back
                    back.append(p)
                else:
                    held.add(p)                            # both sides moved: neither written back nor overwritten
            if back:
                self.log(f'source {name}: {len(back)} region(s) written back: ' + ' '.join(back))
                marker, changed = str(script.marker(source)), True
            if held:
                self.log(f'source {name}: {len(held)} region(s) edited here and in the source; left alone: ' + ' '.join(sorted(held)))
        elif edited:
            held = set(edited)                             # an edit the artifact does not let out stays as it is
        requested = self.holes(scope, artifact)
        paths = [p for p in script.skeleton(source) if p not in held]
        known = set(paths) | held
        eager_paths = [p for p in (script.contents(source) if hasattr(script, 'contents') else paths) if p in known and p not in held]
        new_requests = {p for p in requested if p in known and existing.get(p, (None, 0))[0] is None}
        if not changed and not new_requests and not refresh and all(p in existing for p in eager_paths):
            return 0
        if getattr(script, 'eager', False):
            want = [p for p in paths if changed or p not in existing or p in refresh]
        else:
            want = [p for p in paths if p in new_requests or p in refresh or (changed and existing.get(p, (None, 0))[0] is not None)]
        paths = [p for p in paths if p in eager_paths or p in want or p in existing]      # what gets a record this pass
        content = script.regions(source, want) if want else {}
        ref = reference(artifact)
        records, written, culled = [], 0, 0
        for p in paths:                                    # the skeleton: every path that is not there yet
            if p in existing or p in content:
                continue
            records.append({'path': artifact + '/' + p, 'slots': {'source': ref}})
            written += 1
        for p in want:                                     # the content: new, or rewritten where its digest moved
            slots = content.get(p)
            if slots is None:
                continue
            digest = digest_of(slots)
            if p in existing and existing[p][0] == digest:
                continue
            record = {'path': artifact + '/' + p, 'slots': dict(slots, source=ref, digest=digest)}
            if p in existing:
                record['if_case'] = existing[p][1]
            records.append(record)
            written += 1
        if changed:                                        # what the source no longer has
            for p in sorted(existing):
                if p not in known and not any(p.startswith(q + '/') for q in existing if q not in known and q != p):
                    records.append({'path': artifact + '/' + p, 'action': 'cull'})
                    culled += 1
            records.append({'path': artifact, 'action': 'poke', 'slots': {'marker': marker}})
        if not records:
            return 0
        who = 'source_' + name
        for start in range(0, len(records), 200):
            reply = self.w.tool('write', records=records[start:start + 200], who=who)
        self.log(f'source {name}: {written} written, {culled} culled' + (', marker ' + marker if changed else ''))
        url = self.setting('url')
        if url and changed:
            self.plug(url, {'artifact': artifact, 'marker': marker, 'written': written, 'culled': culled, 'epoch': reply.get('epoch')})
        return written + culled

    def line(self, line):
        """A line under a scope may be a new cell waiting at a path under an artifact: pass over that scope's artifacts."""
        touched = line.get('touched') or []
        done = 0
        for artifact, scope, source in self.artifacts():
            if any(t == scope or t.startswith(scope + '/') for t in touched):
                done += self.sync(artifact, scope, dict(source, every=0), time.time())
        return done

    def tick(self, now):
        return sum(self.sync(a, s, src, now) for a, s, src in self.artifacts())


if __name__ == '__main__':
    _hand.run(Source, settings=('folders', 'url'))
