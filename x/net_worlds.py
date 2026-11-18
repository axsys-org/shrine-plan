"""World processes for the cross-process checks: start one, talk to its door, stop it."""
import json
import os
import signal
import subprocess
import sys
import time
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
    def __init__(self, node, http, mesa, home, mounts=('mcp', 'mesa', 'scope')):
        self.node, self.http, self.mesa, self.home, self.mounts = node, http, mesa, home, mounts
        self.process = None
        self.count = 0

    def start(self, timeout):
        self.home.mkdir(parents=True, exist_ok=True)
        self.log = (self.home / 'eden.log').open('a')
        command = [sys.executable, str(ROOT / 'x/eden'), '--node', self.node, '--port', str(self.http),
                   '--world', str(self.home / 'world'), '--extras-root', str(ROOT / 'extras'),
                   '--startup-timeout', str(timeout)]
        for mount in self.mounts:
            command += ['--mount', mount]
        self.process = subprocess.Popen(command, stdout=self.log, stderr=subprocess.STDOUT, start_new_session=True)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(f'{self.node} exited while starting; see {self.home}/eden.log')
            try:
                self.tool('read', path='/' + self.node + '/io/mesa', care='x')
                return
            except Exception:
                time.sleep(2)
        raise RuntimeError(f'{self.node} did not start in {timeout}s; see {self.home}/eden.log')

    def stop(self):
        if self.process and self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGTERM)
            try:
                self.process.wait(timeout=60)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
        self.process = None

    def tool(self, name, **arguments):
        self.count += 1
        body = json.dumps(dict(jsonrpc='2.0', id=self.count, method='tools/call',
                               params={'name': 'mcp/' + name, 'arguments': arguments})).encode()
        request = urllib.request.Request(f'http://127.0.0.1:{self.http}/mcp', body,
                                         {'Content-Type': 'application/json'})
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
    """A world prepared for a place and claimed, as x/check-community does it step by step: the place's
    invitation is minted, a world is started under the minted name with its founding and first statement,
    it is handed the invitation's secret and claims itself, and it is brought before the maker. This
    function plays the door (it moves the secret between file roots) and the host (it starts the world).
    Returns the world, or raises with what did not happen."""
    if not until(lambda: maker.number(place, 'name') > 0, 240):
        raise RuntimeError(f'no invitation was minted for {place}: {maker.read(place)}')
    name = maker.number(place, 'name')
    node = spell(name)
    card = '/' + maker.node + '/io/mesa/' + node
    ask = '/' + maker.node + '/io/mesa/ask/link' + str(invite)
    maker.write(dict(path=ask, slots={'want': 'link', 'id': invite}))
    left = maker.home / 'world' / 'src' / 'io' / 'mesa' / 'out' / str(invite)
    if not until(lambda: left.exists() and left.stat().st_size == 32, 90):
        raise RuntimeError(f'the secret of invitation {invite} was not left for the door: {maker.read(ask)}')
    secret = left.read_bytes()
    world = World(node, http, mesa, home, mounts)
    world.start(timeout)
    here = '/' + node + '/io/mesa'
    until(lambda: world.number(here, 'key') > 0, 180)
    standing = numbers({k: v for k, v in maker.slots(card).items()
                        if k in ('seq', 'last', 'life', 'rift', 'key', 'custody')})
    world.write(dict(path=here + '/pass', slots=numbers(maker.slots(card + '/pass'))),
                dict(path=here + '/pass/1', slots=numbers(maker.slots(card + '/pass/1'))))
    world.write(dict(path=here, action='poke', slots=dict(standing, port=mesa)),
                dict(path=here + '/' + maker.node,
                     slots={'key': maker.number('/' + maker.node + '/io/mesa', 'key'),
                            'host': '127.0.0.1', 'port': maker.mesa}))
    handed = home / 'world' / 'src' / 'io' / 'mesa' / 'in'
    handed.mkdir(parents=True, exist_ok=True)
    (handed / '1').write_bytes(secret)
    world.write(dict(path=here + '/ask/claim', slots={'want': 'claim', 'name': name, 'handed': 1}))
    if not until(lambda: world.number(here, 'seq') == 2, 180):
        raise RuntimeError(f'{node} did not claim itself: {world.read(here + "/ask/claim")}')
    world.write(dict(path=here + '/ask/bring',
                     slots={'want': 'bring', 'to': number_of(maker.node), 'host': '127.0.0.1', 'port': mesa}))
    if not until(lambda: maker.number(place, 'world') == name, 300):
        raise RuntimeError(f'{place} was not filled by {node}: {maker.read(place)} {maker.read(card)}')
    return world
