"""End-to-end check for the gematria mount: the app's assets and its API."""
import json
import re
import urllib.error
import urllib.request


def check(url, node, timeout):
    def fetch(path, body=None):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(url + path, data=data,
                                         headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status, response.headers.get('Content-Type', ''), response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.headers.get('Content-Type', ''), error.read()

    def api(path, body=None, status=200):
        code, ctype, raw = fetch('/gematria/api' + path, body)
        assert code == status, (path, code, raw[:400])
        assert 'application/json' in ctype, (path, ctype)
        return json.loads(raw)

    # The app shell and every asset it references come from the mount.
    code, ctype, page = fetch('/gematria')
    assert code == 200 and 'text/html' in ctype, (code, ctype)
    page = page.decode()
    assert '<div id="root">' in page, page[:400]
    for asset in re.findall(r'(?:src|href)="(/gematria/[^"]+)"', page):
        code, ctype, raw = fetch(asset)
        assert code == 200 and len(raw) > 100, (asset, code, len(raw))
        if asset.endswith('.js'):
            assert 'javascript' in ctype and b'Alphanumeric Qabbala' in raw, (asset, ctype)
        if asset.endswith('.css'):
            assert 'text/css' in ctype, (asset, ctype)

    assert api('/categories') == ['uncategorized']
    assert api('/auth/login', {'username': 'travis', 'password': 'x'})['user']['username'] == 'travis'

    assert api('/phrases', {'phrase': 'god', 'category': 'names', 'tags': ['short']}) == {'success': True}
    assert api('/phrases', {'phrase': 'zi', 'category': 'uncategorized', 'tags': []})['success']
    assert api('/phrases', {'phrase': 'jesus christ', 'tags': []})['success']
    assert api('/phrases', {'phrase': 'god', 'category': 'names', 'tags': []})['duplicate']
    assert 'error' in api('/phrases', {'phrase': 'drop;table'}, status=400)
    assert api('/categories') == ['uncategorized', 'names']

    saved = api('/phrases')
    assert [p['phrase'] for p in saved] == ['god', 'zi', 'jesus christ'], saved
    assert saved[0]['tags'] == ['short'] and saved[0]['category'] == 'names', saved

    every = ['Alphanumeric Qabbala', 'Numeric QWERTY', 'Ordinal', 'QWERTY', 'Synx',
             'AQ Squares', 'AQ Primes', 'AQ Trigonal', 'NQ Squares', 'NQ Primes',
             'NQ Trigonal', 'Satanic', 'Standard', 'Reduction', 'Unun', 'Vaxen',
             'Based Atlanteanism']
    page = {'page': 0, 'limit': 50}

    found = api('/phrases/search', {'mode': 'text', 'query': 'JE', 'ciphers': every, 'pagination': page})
    assert [r['phrase'] for r in found['results']] == ['jesus christ'], found
    values = found['results'][0]['ciphers']
    assert values['Alphanumeric Qabbala'] == 250 and values['Synx'] == 1088, values
    assert values['Vaxen'] == 838 and values['Based Atlanteanism'] == 75, values
    assert found['pagination'] == {'total': 1, 'hasMore': False}, found

    # god and zi share AQ 53; only god also has Ordinal 26.
    found = api('/phrases/search', {'mode': 'numeric', 'query': '53', 'ciphers': every, 'pagination': page})
    assert sorted(r['phrase'] for r in found['results']) == ['god', 'zi'], found
    found = api('/phrases/search', {'mode': 'numeric', 'query': '53, *, 26', 'ciphers': every, 'pagination': page})
    assert [r['phrase'] for r in found['results']] == ['god'], found

    found = api('/phrases/search', {'mode': 'numeric', 'query': '53', 'ciphers': every,
                                    'pagination': {'page': 0, 'limit': 1}})
    assert len(found['results']) == 1 and found['pagination'] == {'total': 2, 'hasMore': True}, found
