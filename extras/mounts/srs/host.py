import re
import urllib.request
import urllib.parse
import urllib.error

def check(url, node, timeout):
    def get(path):
        with urllib.request.urlopen(url + path, timeout=timeout) as response:
            return response.read().decode()
    preview = get(f'/ns/{node}/gov/srs')
    assert 'Install instance' in preview
    assert 'name="root"' in preview
    assert 'no record at this node' in get(f'/ns/{node}/gov/srs/cards/demo')
    grade = get(f'/ns/{node}/gov/srs/grade')
    assert 'compiled Grove module' in grade
    version = re.search(r'name="version" value="(\d+)"', preview)
    assert version, preview
    def install_instance(target, case=version.group(1)):
        data = urllib.parse.urlencode({
            'source': f'/{node}/gov/srs', 'version': case, 'root': f'/{node}{target}'
        }).encode()
        try:
            with urllib.request.urlopen(urllib.request.Request(
                    url + '/grove/install', data=data), timeout=timeout) as response:
                return response.read().decode()
        except urllib.error.HTTPError as error:
            print(f'Install {target}: {error.code} {error.read().decode()}', flush=True)
            raise
    # Activation must have installed the default instance before any HTTP writes.
    assert 'What does a Shrine name identify?' in get(f'/ns/{node}/app/srs/cards/demo')
    assert 'committed' in install_instance('/app/second')
    for target, case in [('/app/srs', version.group(1)), ('/app/stale', '0')]:
        try:
            install_instance(target, case)
            raise AssertionError('Conflicting/stale installation must fail')
        except urllib.error.HTTPError as error:
            assert error.code == 409
    assert 'Install instance' in get(f'/ns/{node}/gov/srs')
    assert 'What does a Shrine name identify?' in get(f'/ns/{node}/app/srs/cards/demo')
    assert 'What does a Shrine name identify?' in get(f'/ns/{node}/app/second/cards/demo')
    assert f'path="/x/{node}/app/srs/next/0"' in get(f'/ns/x/{node}/app/srs/next')
    assert 'no record at this node' in get(f'/ns/{node}/app/srs/grade')
