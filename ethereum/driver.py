"""Loopback-only, token-authenticated I/O boundary for Shrine's Fetch driver."""
import hmac
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from wallet import canonical


def server(wallet, token, port=18545):
    if len(token) < 24:
        raise ValueError('Driver token is too short')

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            self.connection.settimeout(10)
            if self.path != '/v0' or self.headers.get('Origin') or not hmac.compare_digest(
                    self.headers.get('Authorization', ''), 'Bearer ' + token):
                self.send_error(403)
                return
            try:
                size = int(self.headers.get('Content-Length', '-1'))
                if not 0 < size <= 131072 or self.headers.get('Transfer-Encoding'):
                    raise ValueError('Invalid body size')
                request = json.loads(self.rfile.read(size))
                result = {'ok': True, 'result': wallet.dispatch(request)}
            except (KeyError, TypeError, ValueError):
                result = {'ok': False, 'error': 'invalid_request'}
            except Exception:
                # Exceptions from providers can include credential-bearing URLs.
                result = {'ok': False, 'error': 'driver_failure_retry_same_intent'}
            data = canonical(result).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)
