import urllib.request

def check(url, node, timeout):
    for path, expected in [('/goo-inspector', 'Goo inspector'),
                           ('/goo-inspector/config.js', '/' + node),
                           ('/goo-inspector/app.js', 'new GooPanes'),
                           ('/goo-inspector/model.js', 'inspector_summary')]:
        with urllib.request.urlopen(url + path, timeout=timeout) as response:
            assert expected in response.read().decode()
    request = urllib.request.Request(url + '/goo-inspector', data=b'', method='POST')
    try:
        urllib.request.urlopen(request, timeout=timeout)
        raise AssertionError('Inspector accepted a write')
    except urllib.error.HTTPError as error:
        assert error.code == 405
