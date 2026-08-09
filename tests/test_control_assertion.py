import base64
import hashlib
import hmac
import json
from uuid import uuid4

import pytest
from activity.server.control_auth import (
    ControlAssertionRejectedError,
    verify_control_assertion,
)

KEY = b"k" * 32


def token(claims: dict[str, object]) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    encode = (
        lambda value: base64.urlsafe_b64encode(
            json.dumps(value, separators=(",", ":")).encode()
        )
        .rstrip(b"=")
        .decode()
    )
    encoded_header, encoded_claims = encode(header), encode(claims)
    signature = hmac.new(
        KEY, f"{encoded_header}.{encoded_claims}".encode(), hashlib.sha256
    ).digest()
    return f"{encoded_header}.{encoded_claims}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"


def claims() -> dict[str, object]:
    now = 1_700_000_000
    return {
        "iss": "muxivo-console",
        "aud": "muxivo-discord-control",
        "sub": str(uuid4()),
        "organization_id": str(uuid4()),
        "platform_subject": "123456789012345678",
        "correlation_id": str(uuid4()),
        "resource": "console.platform_connections",
        "action": "manage",
        "iat": now,
        "exp": now + 60,
    }


def test_accepts_exact_short_lived_signed_assertion() -> None:
    assertion = verify_control_assertion(
        token(claims()),
        signing_key=KEY,
        expected_resource="console.platform_connections",
        expected_action="manage",
        now=1_700_000_001,
    )

    assert assertion.platform_subject == "123456789012345678"
    assert assertion.organization_id


@pytest.mark.parametrize(
    "mutation", ("signature", "audience", "expiry", "subject", "resource")
)
def test_rejects_tampered_or_out_of_context_assertion(mutation: str) -> None:
    payload = claims()
    now = 1_700_000_001
    issued = token(payload)
    if mutation == "signature":
        issued = f"{issued[:-1]}x"
    elif mutation == "audience":
        payload["aud"] = "other-service"
        issued = token(payload)
    elif mutation == "expiry":
        payload["exp"] = now - 1
        issued = token(payload)
    elif mutation == "subject":
        payload["platform_subject"] = "not-a-snowflake"
        issued = token(payload)
    else:
        payload["resource"] = "console.control_modules"
        issued = token(payload)

    with pytest.raises(ControlAssertionRejectedError):
        verify_control_assertion(
            issued,
            signing_key=KEY,
            expected_resource="console.platform_connections",
            expected_action="manage",
            now=now,
        )
