"""
SSL/TLS metadata capture (PHASE3_DATASET_PLAN.md section 20, approved decision 14).

A small, separate probe — not a crawler/fetcher.py change. Opens a direct TLS connection with
the standard-library ssl/socket modules and reads the leaf certificate's subject, issuer and
expiry, plus the negotiated protocol version, independently of and without blocking the main
HTML fetch. Attempted only for https:// hosts. Any failure (timeout, handshake failure,
unparseable certificate) sets tls_captured=False with the other fields empty; this never raises
and is not part of the section-16 eligibility predicate (TLS capture is additive metadata, not
a gate on whether a row can be used for modelling).

Revision note (post-review fix, C1): the previous version set verify_mode=ssl.CERT_NONE and
then called the stdlib ssl.SSLSocket.getpeercert() text-form method — per Python's documented
behavior, that method returns an EMPTY dict whenever certificate verification did not run (which
is exactly what CERT_NONE means), so every real probe silently captured nothing while reporting
tls_captured=True. Fixed by pulling the certificate in DER (binary) form instead — available
regardless of verification — and parsing it with the `cryptography` package, which makes no
trust decision of its own; this project still does not validate the certificate (a research
probe deliberately wants metadata from self-signed/expired/invalid certificates too), it now
just reads it correctly. See tests/tls_server.py for the local self-signed-certificate
integration test this fix requires (a getpeercert()-shaped fixture, used previously, could never
occur in production and is not a substitute).

Reuses crawler.fetcher's host guard (looked up dynamically at call time, not imported by name,
so the test suite's monkeypatch on crawler.fetcher._host_guard also applies here) so a
forgotten real hostname in a test fails fast instead of making a live connection.
"""

import asyncio
import socket
import ssl
from typing import Any, Dict, Optional

from cryptography import x509

import config
from crawler import fetcher as _fetcher

EMPTY_RESULT: Dict[str, Any] = {
    "tls_captured": False,
    "tls_version": "",
    "certificate_subject": "",
    "certificate_issuer": "",
    "certificate_self_signed": None,
    "certificate_not_after": "",
}


def _format_name(name: x509.Name) -> str:
    if name is None:
        return ""
    try:
        return name.rfc4514_string()  # standard "CN=...,O=..." form, public cryptography API
    except Exception:
        return str(name)


def _parse_certificate(cert: x509.Certificate, negotiated_version: Optional[str]) -> Dict[str, Any]:
    subject = _format_name(cert.subject)
    issuer = _format_name(cert.issuer)
    try:
        not_after = cert.not_valid_after_utc.isoformat()
    except AttributeError:  # older cryptography versions: naive datetime attribute
        not_after = cert.not_valid_after.isoformat()
    return {
        "tls_captured": True,
        "tls_version": negotiated_version or "",
        "certificate_subject": subject,
        "certificate_issuer": issuer,
        "certificate_self_signed": bool(subject) and subject == issuer,
        "certificate_not_after": not_after,
    }


def _blocking_probe(host: str, port: int, timeout: float) -> Dict[str, Any]:
    context = ssl.create_default_context()
    # A research probe wants certificate metadata even for self-signed/expired/invalid
    # certificates (that IS often the signal of interest for a phishing host); it is not
    # making a trust decision, so certificate verification is intentionally disabled here.
    # This does NOT affect whether getpeercert(binary_form=True) returns data — the raw DER
    # bytes of whatever certificate the peer presents are always available; only the
    # convenience *parsed dict* form of getpeercert() is verification-gated (see module
    # docstring — this is exactly the bug this revision fixes).
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    with socket.create_connection((host, port), timeout=timeout) as sock:
        with context.wrap_socket(sock, server_hostname=host) as tls_sock:
            der_bytes = tls_sock.getpeercert(binary_form=True)
            version = tls_sock.version()
    if not der_bytes:
        return dict(EMPTY_RESULT)
    cert = x509.load_der_x509_certificate(der_bytes)
    return _parse_certificate(cert, version)


async def probe_tls(host: str, port: int = 443, timeout: Optional[float] = None) -> Dict[str, Any]:
    if not host:
        return dict(EMPTY_RESULT)
    timeout = config.DATASET_TLS_PROBE_TIMEOUT_SECONDS if timeout is None else timeout
    try:
        _fetcher._host_guard(host)
        return await asyncio.to_thread(_blocking_probe, host, port, timeout)
    except Exception:
        return dict(EMPTY_RESULT)
