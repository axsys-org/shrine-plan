"""End-to-end check for the gematria mount: drive the real page over HTTP."""
import urllib.parse
import urllib.request


def check(url, node, timeout):
    def get(path):
        with urllib.request.urlopen(url + path, timeout=timeout) as response:
            assert 'text/html' in response.headers.get('Content-Type', ''), response.headers
            return response.read().decode()

    def calc(phrase):
        data = urllib.parse.urlencode({'phrase': phrase}).encode()
        with urllib.request.urlopen(url + '/gematria/calc', data=data, timeout=timeout) as response:
            response.read()

    def cell(value):
        return f'>{value}</td>'

    assert 'Nothing yet.' in get('/gematria')

    calc('gematria')
    page = get('/gematria?phrase=gematria')
    for value in (146, 155, 74, 83, 484, 3030, 506, 1588, 3399, 560, 1777, 354, 353, 38, 338, 630, 23):
        assert cell(value) in page, (value, page)
    assert 'g16 e14 m22 a10 t29 r27 i18 a10' in page, page

    calc('god')
    calc('zi')                      # AQ 35 + 18 = 53, same as god
    calc('god')                     # already saved: no second record
    page = get('/gematria?phrase=god')
    assert cell(2) in page and cell(53) in page, page
    assert 'AQ 53' in page and 'phrase=zi' in page, page
    assert page.count('phrase=god"') == 1, page

    assert cell(-1) in get('/gematria?phrase=a')
    # The bare page shows the most recent saved phrase.
    assert 'phrase">zi</h2>' in get('/gematria')
