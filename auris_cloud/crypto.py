from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.x509.oid import NameOID


class CloudSigner:
    def __init__(self, private_key: Ed25519PrivateKey) -> None:
        self.private_key = private_key
        self.public_key = private_key.public_key()

    @classmethod
    def from_pem_path(cls, path: Path) -> "CloudSigner":
        try:
            key = serialization.load_pem_private_key(path.read_bytes(), password=None)
        except (OSError, ValueError, TypeError) as error:
            raise RuntimeError("The AURIS cloud signing key is unavailable or invalid.") from error
        if not isinstance(key, Ed25519PrivateKey):
            raise RuntimeError("The AURIS cloud signing key must be Ed25519.")
        return cls(key)

    @property
    def fingerprint(self) -> str:
        public_bytes = self.public_key.public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )
        return hashlib.sha256(public_bytes).hexdigest()

    @property
    def public_key_b64(self) -> str:
        return _b64url(
            self.public_key.public_bytes(
                serialization.Encoding.Raw,
                serialization.PublicFormat.Raw,
            )
        )

    def sign_envelope(self, envelope: dict[str, Any]) -> str:
        return _b64url(self.private_key.sign(canonical_json(envelope)))

    def verify_envelope(self, envelope: dict[str, Any]) -> bool:
        signature = str(envelope.get("signature") or "")
        unsigned = {key: value for key, value in envelope.items() if key != "signature"}
        try:
            self.public_key.verify(_b64url_decode(signature), canonical_json(unsigned))
        except (InvalidSignature, ValueError, TypeError):
            return False
        return True


def canonical_json(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def certificate_details(certificate_pem: str, device_id: str) -> dict[str, Any]:
    try:
        certificate = x509.load_pem_x509_certificate(certificate_pem.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as error:
        raise ValueError("The device certificate is invalid.") from error
    public_key = certificate.public_key()
    if not isinstance(public_key, Ed25519PublicKey):
        raise ValueError("The device certificate must use Ed25519.")
    now = datetime.now(timezone.utc)
    if certificate.not_valid_before_utc > now or certificate.not_valid_after_utc <= now:
        raise ValueError("The device certificate is expired or not yet valid.")
    expected_uri = f"urn:auris:device:{UUID(device_id)}"
    try:
        uris = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.UniformResourceIdentifier)
    except x509.ExtensionNotFound as error:
        raise ValueError("The device certificate is missing its AURIS identity.") from error
    if expected_uri not in uris:
        raise ValueError("The certificate identity does not match the device.")
    try:
        public_key.verify(certificate.signature, certificate.tbs_certificate_bytes)
    except ValueError as error:
        raise ValueError("The pinned device certificate signature is invalid.") from error
    der = certificate.public_bytes(serialization.Encoding.DER)
    return {
        "certificate": certificate,
        "public_key": public_key,
        "fingerprint": hashlib.sha256(der).hexdigest(),
        "expires_at": certificate.not_valid_after_utc.isoformat(),
    }


def request_proof_bytes(
    method: str,
    path: str,
    device_id: str,
    timestamp: str,
    nonce: str,
    body: bytes,
) -> bytes:
    body_hash = hashlib.sha256(body).hexdigest()
    return "\n".join(
        [method.upper(), path, str(UUID(device_id)), timestamp, nonce, body_hash]
    ).encode("utf-8")


def verify_device_request(
    certificate_pem: str,
    signature: str,
    proof: bytes,
) -> bool:
    try:
        certificate = x509.load_pem_x509_certificate(certificate_pem.encode("ascii"))
        public_key = certificate.public_key()
        if not isinstance(public_key, Ed25519PublicKey):
            return False
        public_key.verify(_b64url_decode(signature), proof)
    except (InvalidSignature, ValueError, UnicodeEncodeError):
        return False
    return True


def create_pinned_device_certificate(
    private_key: Ed25519PrivateKey,
    device_id: str,
) -> str:
    now = datetime.now(timezone.utc)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"AURIS Device {device_id}")])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=30))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.UniformResourceIdentifier(f"urn:auris:device:{UUID(device_id)}")]
            ),
            critical=True,
        )
        .sign(private_key, algorithm=None)
    )
    return certificate.public_bytes(serialization.Encoding.PEM).decode("ascii")


create_test_device_certificate = create_pinned_device_certificate


def sign_device_request(private_key: Ed25519PrivateKey, proof: bytes) -> str:
    return _b64url(private_key.sign(proof))


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
