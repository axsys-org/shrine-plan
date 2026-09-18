import urllib.request

def check(url, node, timeout):
    for path, expected in [('/ns', 'sh-triptych'), ('/ns/' + node + '/hello', 'Hello from Eden.')]:
        with urllib.request.urlopen(url + path, timeout=timeout) as response:
            assert expected in response.read().decode()
    with urllib.request.urlopen(url + '/style.css', timeout=timeout) as response:
        assert response.read()
