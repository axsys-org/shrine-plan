"""The mesa mount's host hook: where a world listens for other worlds, and the two files its foot keeps.

The ring (the world's signing seed, 32 bytes) and the mark (its rift and the highest epoch it has announced) live
under the world's file root at io/mesa/, outside the namespace: the seed is never a record, and the mark has to
outlive a restore of the world. A ring is made the first time a world starts with this mount.

SHRINE_MESA names a JSON file: {"port": 9251, "peers": [{"node": "0x52", "key": <number>, "host": "127.0.0.1",
"port": 9252}]}. The port is where this world's foot listens. Each peer becomes a card at /<node>/io/mesa/<peer>
when the world starts, unless one is there already; a card is an ordinary record and can as well be written
later through any door. A key is the peer's public key as the foot publishes it on /<node>/io/mesa (slot key).
"""
import json
import os
from pathlib import Path


def prepare(root, work, check, cleanup, context):
    world = Path(work).parent.parent
    home = world / 'src' / 'io' / 'mesa'
    home.mkdir(parents=True, exist_ok=True)
    ring = home / 'ring'
    if not ring.is_file():
        seed = os.environ.get('SHRINE_MESA_SEED')
        data = bytes.fromhex(seed) if seed else os.urandom(32)
        if len(data) != 32:
            raise ValueError('SHRINE_MESA_SEED must be 32 bytes of hex')
        descriptor = os.open(ring, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'wb') as out:
            out.write(data)
    mark = home / 'mark'
    if not mark.is_file():
        # rift 0, nothing announced: eight bytes each
        mark.write_bytes(bytes(16))
    source = os.environ.get('SHRINE_MESA')
    config = json.loads(Path(source).read_text()) if source else {}
    arguments = [str(int(config.get('port', 0))), 'io/mesa/ring', 'io/mesa/mark', '/' + context['node'] + '/io/mesa']
    for peer in config.get('peers', []):
        arguments += [str(int(str(peer['node']), 0)), str(int(peer['key'])), str(peer['host']), str(int(peer['port']))]
    return root, arguments
