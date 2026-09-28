"""
A local HTTP test server used only by the crawler tests, so those tests never touch a real
website (CLAUDE.md section 17.6: "Crawler tests with a local test server").
"""

import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LOGIN_PAGE_HTML = (
    "<html><head><title>Sign in</title></head><body>"
    "<form action='http://collector.example.net/post'>"
    "<input type='text' name='user'><input type='password' name='pw'></form>"
    "<div style='display:none'>hidden</div>"
    "<script>eval('x')</script></body></html>"
).encode("utf-8")

MALFORMED_HTML = b"<html><body><div><p>Unclosed tags all the way down<div>"

SLOW_DELAY_SECONDS = 2.0


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass  # keep test output quiet

    def _send(self, status: int, body: bytes, content_type: str = "text/html; charset=utf-8", headers=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_GET(self):
        path = self.path

        if path == "/ok":
            self._send(200, LOGIN_PAGE_HTML)
        elif path == "/empty":
            self._send(200, b"")
        elif path == "/404":
            self._send(404, b"<html><body>Not found</body></html>")
        elif path == "/redirect-a":
            self._send(302, b"", headers={"Location": "/redirect-b"})
        elif path == "/redirect-b":
            self._send(302, b"", headers={"Location": "/ok"})
        elif path == "/loop":
            self._send(302, b"", headers={"Location": "/loop"})
        elif path == "/slow":
            time.sleep(SLOW_DELAY_SECONDS)
            self._send(200, LOGIN_PAGE_HTML)
        elif path == "/nonhtml":
            self._send(200, b"\x00\x01binary\x02", content_type="application/octet-stream")
        elif path == "/malformed":
            self._send(200, MALFORMED_HTML)
        elif path.startswith("/big"):
            size = int(path.split("/big/")[1]) if "/big/" in path else 5000
            self._send(200, b"<html><body>" + b"x" * size + b"</body></html>")
        else:
            self._send(404, b"<html><body>Not found</body></html>")


class LocalTestServer:
    """Starts a ThreadingHTTPServer on an ephemeral 127.0.0.1 port in a background thread."""

    def __init__(self):
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    def start(self) -> "LocalTestServer":
        self._thread.start()
        return self

    def stop(self):
        self._httpd.shutdown()
        self._httpd.server_close()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self._httpd.server_address[1]}"

    def url(self, path: str) -> str:
        return self.base_url + path


def closed_port_url() -> str:
    """Returns a URL to a port on 127.0.0.1 that nothing is listening on (connection refused)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return f"http://127.0.0.1:{port}/"
