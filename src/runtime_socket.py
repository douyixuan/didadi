"""Loopback WebSocket transport for the existing durable single-agent gateway."""
import hmac
import json
import logging
import secrets
import threading
import time
from urllib.parse import urlsplit

from websockets.exceptions import ConnectionClosed
from websockets.sync.server import serve
from src.matrix_http import MatrixError, request


def loopback_url(value, scheme):
    parsed = urlsplit(value)
    if (parsed.scheme != scheme or parsed.hostname not in {'127.0.0.1', 'localhost'} or
        parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError('only loopback runtime endpoints are supported')
    return value


def bridge(base, token, port=9020, wait_seconds=20):
    loopback_url(base, 'http')
    if not token or not 0 < wait_seconds <= 20:
        raise ValueError('invalid runtime bridge configuration')
    def authenticate(connection, incoming):
        if (incoming.path != '/runtime' or not hmac.compare_digest(
            incoming.headers.get('Authorization', ''), 'Bearer ' + token)):
            return connection.respond(403, 'Forbidden\n')
    def handler(socket):
        session = secrets.token_hex(24)
        stopped = threading.Event()
        def observe(connected):
            try:
                request(base, 'POST', '/agent/runtime', token, {'session':session, 'connected':connected})
            except (MatrixError, OSError, ValueError) as error:
                logging.warning('Runtime connection observation failed (%s)', type(error).__name__)
        def pulse():
            while not stopped.wait(10): observe(True)
        observe(True)
        heartbeat = threading.Thread(target=pulse, daemon=True)
        heartbeat.start()
        try:
            for raw in socket:
                try:
                    message = json.loads(raw)
                    if not isinstance(message, dict) or set(message) - {'method', 'path', 'data', 'query'}:
                        raise ValueError()
                    method, path = message.get('method'), message.get('path')
                    data, query = message.get('data'), message.get('query')
                    if method == 'GET' and path == '/agent/tasks' and data is None and query is None:
                        deadline = time.monotonic() + wait_seconds
                        while True:
                            result = request(base, method, path, token)
                            if result['task'] or time.monotonic() >= deadline:
                                break
                            # Wait for disconnect rather than claiming future work for a dead stream.
                            try:
                                socket.recv(timeout=.25)
                            except TimeoutError:
                                pass
                            else:
                                socket.close(1008, 'One request at a time')
                                return
                    elif method == 'GET' and path == '/agent/status' and data is None and isinstance(query, dict) and set(query) == {'id'} and isinstance(query['id'], str):
                        result = request(base, method, path, token, query=query)
                    elif method == 'POST' and path in {'/agent/validate', '/agent/complete', '/agent/fail', '/agent/document-scope'} and isinstance(data, dict) and query is None:
                        result = request(base, method, path, token, data)
                    else:
                        raise ValueError()
                    response = {'ok': True, 'result': result}
                except MatrixError as error:
                    response = {'ok': False, 'status': error.status, 'error': error.body}
                except (ValueError, KeyError, TypeError):
                    response = {'ok': False, 'status': 400, 'error': {'error': 'invalid_runtime_message', 'retryable': False}}
                except OSError:
                    response = {'ok': False, 'status': 503, 'error': {'error': 'gateway_unavailable', 'retryable': True}}
                socket.send(json.dumps(response))
        except ConnectionClosed:
            pass  # Do not release a possibly executing lease; durable expiry controls redelivery.
        finally:
            stopped.set()
            observe(False)
            heartbeat.join(timeout=1)
    return serve(handler, '127.0.0.1', port, origins=[None], process_request=authenticate,
                 compression=None, max_size=65536, max_queue=4, ping_interval=10, ping_timeout=10,
                 close_timeout=2)
