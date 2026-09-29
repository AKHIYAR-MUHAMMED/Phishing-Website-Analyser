"""
A local TLS server with a freshly generated, in-memory self-signed certificate — used only to
test dataset/tls_probe.py's real handshake/certificate-parsing code path (never a real website;
CLAUDE.md section 17.6's "local test server" rule applied to TLS).
"""

import datetime
import os
import socket
import ssl
import tempfile
import threading

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def generate_self_signed_cert(common_name: str = "phish.example", days_valid: int = 365):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)  # self-signed: issuer == subject
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=days_valid))
        .sign(key, hashes.SHA256())
    )
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    return cert_pem, key_pem, cert


class LocalTLSServer:
    """Accepts one TLS connection at a time on an ephemeral 127.0.0.1 port, presenting a fresh
    self-signed certificate. Enough to exercise a real handshake and getpeercert(binary_form)
    without any external CA or network access."""

    def __init__(self, common_name: str = "phish.example", http_response: bytes = None):
        self.common_name = common_name
        self.http_response = http_response or b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n"
        cert_pem, key_pem, self.certificate = generate_self_signed_cert(common_name)

        self._cert_file = tempfile.NamedTemporaryFile(suffix=".pem", delete=False)
        self._cert_file.write(cert_pem)
        self._cert_file.close()
        self._key_file = tempfile.NamedTemporaryFile(suffix=".pem", delete=False)
        self._key_file.write(key_pem)
        self._key_file.close()

        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(self._cert_file.name, self._key_file.name)
        self._context = context

        self._raw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._raw_socket.bind(("127.0.0.1", 0))
        self._raw_socket.listen(5)
        self.port = self._raw_socket.getsockname()[1]

        self._stop_requested = False
        self._thread = threading.Thread(target=self._serve_forever, daemon=True)

    def _serve_forever(self):
        self._raw_socket.settimeout(0.5)
        while not self._stop_requested:
            try:
                conn, _addr = self._raw_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                with self._context.wrap_socket(conn, server_side=True) as tls_conn:
                    try:
                        tls_conn.recv(1024)
                        tls_conn.sendall(self.http_response)
                    except Exception:
                        pass
            except Exception:
                pass  # a failed/aborted handshake from a probing test client is expected

    def start(self) -> "LocalTLSServer":
        self._thread.start()
        return self

    def stop(self):
        self._stop_requested = True
        try:
            self._raw_socket.close()
        except Exception:
            pass
        self._thread.join(timeout=2)
        for path in (self._cert_file.name, self._key_file.name):
            try:
                os.unlink(path)
            except OSError:
                pass
