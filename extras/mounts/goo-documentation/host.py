"""Smoke checks against the real installed namespace, not fixture HTML."""
import urllib.request
import urllib.error


def check(url, node, timeout):
    for path, expected in [('/goo-documentation', 'Goo documentation'),
                           ('/goo-documentation?path=/' + node + '/lib/pact', 'data-workspace'),
                           ('/goo-documentation/style.css', '.goo-documentation')]:
        with urllib.request.urlopen(url + path, timeout=timeout) as response:
            assert response.status == 200
            assert expected in response.read().decode()
    for path, method, status in [('/goo-documentation', 'POST', 405),
                                 ('/goo-documentation?path=relative', 'GET', 400),
                                 ('/goo-documentation?path=/sys&path=/app', 'GET', 400),
                                 ('/goo-documentation/missing', 'GET', 404)]:
        request = urllib.request.Request(url + path, method=method)
        try:
            urllib.request.urlopen(request, timeout=timeout)
            raise AssertionError((path, 'Unexpected success'))
        except urllib.error.HTTPError as error:
            assert error.code == status, (path, error.code)
