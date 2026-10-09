"""
TLS probe tests. Section C1 fix (independent review round 2): _parse_certificate is now tested
against a REAL x509.Certificate object (via tests/tls_server.py's cert generator), not a
getpeercert()-shaped dict the CERT_NONE production code path could never actually produce. The
end-to-end test runs the real handshake against a local self-signed-certificate TLS server —
never a real website.
"""

import asyncio

from cryptography import x509

from dataset.tls_probe import EMPTY_RESULT, _parse_certificate, probe_tls
from local_server import closed_port_url
from tls_server import LocalTLSServer, generate_self_signed_cert


def test_parse_certificate_extracts_fields_from_a_real_certificate():
    _cert_pem, _key_pem, cert = generate_self_signed_cert("example.com")
    parsed = _parse_certificate(cert, "TLSv1.3")
    assert parsed["tls_captured"] is True
    assert parsed["tls_version"] == "TLSv1.3"
    assert "example.com" in parsed["certificate_subject"]
    assert "example.com" in parsed["certificate_issuer"]
    assert parsed["certificate_not_after"]


def test_parse_certificate_detects_self_signed():
    _cert_pem, _key_pem, cert = generate_self_signed_cert("phish.example")
    parsed = _parse_certificate(cert, "TLSv1.2")
    assert parsed["certificate_self_signed"] is True
    assert parsed["certificate_subject"] == parsed["certificate_issuer"]


def test_probe_tls_empty_host_returns_empty_result():
    result = asyncio.run(probe_tls(""))
    assert result == EMPTY_RESULT


def test_probe_tls_connection_refused_is_never_captured_and_never_raises():
    url = closed_port_url()
    hostport = url.split("//")[1].rstrip("/")
    host, port = hostport.split(":")
    result = asyncio.run(probe_tls(host, port=int(port), timeout=1.0))
    assert result["tls_captured"] is False


def test_probe_tls_blocks_real_host_via_network_guard():
    result = asyncio.run(probe_tls("example.com", timeout=1.0))
    assert result["tls_captured"] is False


def test_probe_tls_against_real_local_self_signed_server():
    """The end-to-end regression test for C1: a real TLS handshake, a real self-signed
    certificate, real getpeercert(binary_form=True) + cryptography parsing — the exact
    production code path, not a mocked shape."""
    server = LocalTLSServer(common_name="phish.example").start()
    try:
        result = asyncio.run(probe_tls("127.0.0.1", port=server.port, timeout=3.0))
        assert result["tls_captured"] is True
        assert "phish.example" in result["certificate_subject"]
        assert result["certificate_self_signed"] is True
        assert result["tls_version"].startswith("TLSv1")
        assert result["certificate_not_after"]
    finally:
        server.stop()


def test_generate_self_signed_cert_produces_a_loadable_certificate():
    cert_pem, key_pem, cert = generate_self_signed_cert("x.example")
    assert cert_pem.startswith(b"-----BEGIN CERTIFICATE-----")
    assert key_pem.startswith(b"-----BEGIN RSA PRIVATE KEY-----") or key_pem.startswith(b"-----BEGIN PRIVATE KEY-----")
    assert isinstance(cert, x509.Certificate)
