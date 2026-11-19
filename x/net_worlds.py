"""World processes for the cross-process checks: start one, talk to its door, stop it."""
import json
import os
import secrets
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def spell(number):
    """A world's number as its name is spelled: 0x and its bytes, lowest first."""
    return '0x' + number.to_bytes((number.bit_length() + 7) // 8, 'little').hex()


def number_of(spelling):
    return int.from_bytes(bytes.fromhex(spelling[2:]), 'little')


def until(condition, seconds=120):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if condition():
            return True
        time.sleep(1)
    return False


class World:
    def __init__(self, node, http, mesa, home, mounts=('mcp', 'mesa', 'scope'), founding=''):
        self.node, self.http, self.mesa, self.home, self.mounts = node, http, mesa, home, mounts
        self.founding = founding
        self.session = None
        self.process = None
        self.count = 0

    def start(self, timeout):
        self.home.mkdir(parents=True, exist_ok=True)
        self.log = (self.home / 'eden.log').open('a')
        command = [sys.executable, str(ROOT / 'x/eden'), '--node', self.node, '--port', str(self.http),
                   '--world', str(self.home / 'world'), '--extras-root', str(ROOT / 'extras'),
                   '--startup-timeout', str(timeout)]
        command += ['--address', f'127.0.0.1:{self.mesa}']
        if self.founding:
            command += ['--founding', self.founding]
        for mount in self.mounts:
            command += ['--mount', mount]
        self.process = subprocess.Popen(command, stdout=self.log, stderr=subprocess.STDOUT, start_new_session=True)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(f'{self.node} exited while starting; see {self.home}/eden.log')
            try:
                self.tool('read', path='/' + self.node + '/io/mesa', care='x')
                break
            except urllib.error.HTTPError:
                break  # the door answered and let nobody in: the world is up
            except Exception:
                time.sleep(2)
        else:
            raise RuntimeError(f'{self.node} did not start in {timeout}s; see {self.home}/eden.log')
        # A world that is its own leaves its first session for whoever is at the machine, which this
        # script is. A world started under a name nobody has claimed lets nobody in until it is claimed.
        if not self.founding and not self.session:
            self.owner()

    def stop(self):
        if self.process and self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGTERM)
            try:
                self.process.wait(timeout=60)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
        self.process = None

    def headers(self, session=None):
        session = session or self.session
        return {'Content-Type': 'application/json', **({'Authorization': 'Bearer ' + session} if session else {})}

    def post(self, route, body='', session=None, nobody=False):
        """One request at the door, as the session this world was let in under, another, or nobody.
        Returns the status and the text."""
        headers = {'Content-Type': 'text/plain'} if nobody else self.headers(session)
        request = urllib.request.Request(f'http://127.0.0.1:{self.http}{route}', body.encode(), headers)
        try:
            reply = urllib.request.urlopen(request, timeout=60)
            return reply.status, reply.read().decode()
        except urllib.error.HTTPError as error:
            return error.code, error.read().decode()

    def get(self, route, session=None, nobody=False):
        """One reading at the door. Returns the status and the text."""
        headers = {} if nobody else {k: v for k, v in self.headers(session).items() if k == 'Authorization'}
        request = urllib.request.Request(f'http://127.0.0.1:{self.http}{route}', headers=headers)
        try:
            reply = urllib.request.urlopen(request, timeout=60)
            return reply.status, reply.read().decode()
        except urllib.error.HTTPError as error:
            return error.code, error.read().decode()

    def files(self):
        """The world's file root. Only whoever is at the machine, and the host, look here."""
        return self.home / 'world' / 'src'

    def owner(self, seconds=240):
        """The first session of a world that is its own, read from the file its foot left: whoever
        is at the machine is the owner, and this script is."""
        left = self.files() / 'io' / 'mesa' / 'out' / 'session'
        if not until(lambda: left.exists() and left.stat().st_size > 0, seconds):
            raise RuntimeError(f'{self.node} left no first session at {left}')
        self.session = left.read_text().strip()
        return self.session

    def link(self, invite, seconds=120):
        """The link to an invitation this world minted, with its secret, from its door, as its owner."""
        if not self.session:
            self.owner()
        deadline = time.time() + seconds
        said = None
        while time.time() < deadline:
            said = self.post(f'/scope/link/{invite}')
            if said[0] == 200:
                return said[1].strip()
            if said[0] != 202:
                break
            time.sleep(1)
        raise RuntimeError(f'the door of {self.node} gave no link to invitation {invite}: {said}')

    def join(self, link, session=None, nobody=False, seconds=60):
        """Hand a link over at this world's door. Returns the last status and text."""
        deadline = time.time() + seconds
        said = None
        while time.time() < deadline:
            said = self.post('/door/join', link, session=session, nobody=nobody)
            if not (said[0] == 409 and 'still being answered' in said[1]):
                break
            time.sleep(1)
        return said

    def tool(self, name, **arguments):
        self.count += 1
        body = json.dumps(dict(jsonrpc='2.0', id=self.count, method='tools/call',
                               params={'name': 'mcp/' + name, 'arguments': arguments})).encode()
        request = urllib.request.Request(f'http://127.0.0.1:{self.http}/mcp', body, self.headers())
        reply = json.load(urllib.request.urlopen(request, timeout=60))
        result = reply['result']
        if result.get('isError'):
            raise RuntimeError(json.dumps(result)[:400])
        return result.get('structuredContent', result)

    def write(self, *records):
        return self.tool('write', records=list(records))

    def read(self, path, care='x'):
        try:
            return self.tool('read', path=path, care=care)
        except Exception as error:
            return {'error': str(error)}

    def there(self, path):
        return bool(self.read(path).get('exists'))

    def slots(self, path):
        """A record's slots as the door gives them, by bare name."""
        properties = self.read(path).get('properties') or {}
        return {name.lstrip('/'): value for name, value in properties.items()}

    def number(self, path, slot):
        try:
            return int(str(self.slots(path).get(slot)))
        except (TypeError, ValueError):
            return 0

    def text(self, path, slot):
        value = self.slots(path).get(slot)
        return '' if value is None else str(value)


def founding_of(link):
    """What a host starts a world under a link's name with: the last four parts of the link itself
    (the name's founding and first statement), and never its secret."""
    return ','.join(link.split(',')[7:11])


def meet(worlds, seconds=180):
    """Each world listens on its port and holds a card for every other: the stand-in for joining, which
    x/check-community covers."""
    keys = {}
    for world in worlds:
        home = '/' + world.node + '/io/mesa'
        until(lambda: world.number(home, 'key') > 0, seconds)
        keys[world.node] = world.number(home, 'key')
    for world in worlds:
        home = '/' + world.node + '/io/mesa'
        records = [dict(path=home, action='poke', slots={'port': world.mesa})]
        for other in worlds:
            if other is not world:
                records.append(dict(path=home + '/' + other.node,
                                    slots={'key': keys[other.node], 'host': '127.0.0.1', 'port': other.mesa}))
        world.write(*records)
    return keys


def numbers(slots):
    return {name: int(str(value)) for name, value in slots.items()}


def prepared(maker, place, invite, http, mesa, home, timeout, mounts=('mcp', 'mesa', 'scope')):
    """A world prepared for a place and claimed, as x/check-community does it step by step. The maker's
    door gives the link to its owner. A world is started under the link's name with the name's founding
    and its address: that much is the host, played here. Then the link is handed over at the
    new world's door by nobody, with a session this function makes, and everything else is the worlds'
    own: the claim, the session let in, the scope met, the introduction, the place filled. Returns the
    world, let in under that session, or raises with what did not happen."""
    if not until(lambda: maker.number(place, 'name') > 0, 240):
        raise RuntimeError(f'no invitation was minted for {place}: {maker.read(place)}')
    name = maker.number(place, 'name')
    link = maker.link(invite)
    world = World(spell(name), http, mesa, home, mounts, founding=founding_of(link))
    world.start(timeout)
    here = '/' + world.node + '/io/mesa'
    session = secrets.token_hex(16)
    said = world.join(link, session=session)
    if said[0] != 202:
        raise RuntimeError(f'the door of {world.node} did not take the link: {said}')
    world.session = session
    if not until(lambda: world.number(here, 'seq') == 2, 180):
        raise RuntimeError(f'{world.node} did not claim itself: {world.read(here)}')
    if not until(lambda: maker.number(place, 'world') == name, 300):
        raise RuntimeError(f'{place} was not filled by {world.node}: {maker.read(place)}')
    return world
