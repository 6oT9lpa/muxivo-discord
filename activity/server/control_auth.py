"""Verification of short-lived Console-to-Discord Control API assertions."""

import base64
import binascii
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID


class ControlAssertionRejectedError(PermissionError):
    """A deliberately non-specific rejection for an untrusted service assertion."""


@dataclass(frozen=True, slots=True)
class ControlAssertion:
    actor_id: UUID
    organization_id: UUID
    platform_subject: str | None
    correlation_id: UUID


def verify_control_assertion(
    token: str,
    *,
    signing_key: bytes,
    expected_resource: str,
    expected_action: str,
    now: float | None = None,
    expected_issuer: str = "muxivo-console",
    expected_audience: str = "muxivo-discord-control",
    require_platform_subject: bool = False,
) -> ControlAssertion:
    """Validate the exact assertion context before any Discord-native lookup."""
    if len(signing_key) < 32 or not token or len(token) > 4096:
        raise ControlAssertionRejectedError("Control assertion rejected.")
    try:
        encoded_header, encoded_claims, encoded_signature = token.split(".")
        header = _decode_json(encoded_header)
        claims = _decode_json(encoded_claims)
        signature = _base64url_decode(encoded_signature)
    except (ValueError, json.JSONDecodeError, binascii.Error) as error:
        raise ControlAssertionRejectedError("Control assertion rejected.") from error
    signing_input = f"{encoded_header}.{encoded_claims}".encode("ascii")
    expected_signature = hmac.new(signing_key, signing_input, hashlib.sha256).digest()
    if (
        not isinstance(header, dict)
        or header.get("alg") != "HS256"
        or header.get("typ") != "JWT"
        or not hmac.compare_digest(signature, expected_signature)
        or not isinstance(claims, dict)
    ):
        raise ControlAssertionRejectedError("Control assertion rejected.")
    try:
        instant = time.time() if now is None else now
        exp = claims["exp"]
        iat = claims["iat"]
        if (
            not isinstance(exp, int)
            or not isinstance(iat, int)
            or exp <= instant
            or iat > instant + 15
            or exp - iat > 120
            or claims["iss"] != expected_issuer
            or claims["aud"] != expected_audience
            or claims["resource"] != expected_resource
            or claims["action"] != expected_action
        ):
            raise ValueError("Invalid assertion claims.")
        platform_subject = claims.get("platform_subject")
        if platform_subject is not None and (
            not isinstance(platform_subject, str) or not platform_subject.isdigit()
        ):
            raise ValueError("Invalid assertion claims.")
        if require_platform_subject and platform_subject is None:
            raise ValueError("A platform subject is required.")
        return ControlAssertion(
            actor_id=UUID(claims["sub"]),
            organization_id=UUID(claims["organization_id"]),
            platform_subject=platform_subject,
            correlation_id=UUID(claims["correlation_id"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ControlAssertionRejectedError("Control assertion rejected.") from error


def signing_key_from_environment() -> bytes:
    """Load the shared service assertion key; absent config disables Control API use."""
    raw_value = os.getenv("MUXIVO_DISCORD_CONTROL_SIGNING_KEY", "")
    try:
        key = base64.b64decode(raw_value, validate=True)
    except binascii.Error as error:
        raise ControlAssertionRejectedError("Control assertion rejected.") from error
    if len(key) < 32:
        raise ControlAssertionRejectedError("Control assertion rejected.")
    return key


def _decode_json(encoded: str) -> Any:
    return json.loads(_base64url_decode(encoded))


def _base64url_decode(encoded: str) -> bytes:
    padding = "=" * (-len(encoded) % 4)
    return base64.urlsafe_b64decode(encoded + padding)
