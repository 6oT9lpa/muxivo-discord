"""Private Control API endpoints called by Muxivo Console."""

import logging
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from activity.server.control_auth import (
    ControlAssertionRejectedError,
    signing_key_from_environment,
    verify_control_assertion,
)
from activity.server.services.discord_guild_authority import DiscordGuildAuthority

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/control/v1", tags=["control"])
authority = DiscordGuildAuthority()


class PlatformConnectionVerificationRequest(BaseModel):
    platform: Literal["discord"]
    external_resource_id: str = Field(pattern=r"^\d{1,20}$")


@router.post("/organizations/{organization_id}/connections/verify")
async def verify_platform_connection(
    organization_id: UUID,
    payload: PlatformConnectionVerificationRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, bool]:
    """Verify the Console subject's native authority over a Discord guild."""
    assertion = _verify_request_assertion(authorization)
    if assertion.organization_id != organization_id:
        logger.warning(
            "Control assertion organization does not match the requested platform connection"
        )
        raise HTTPException(
            status_code=403,
            detail="Control assertion is not authorized for this organization",
        )

    verified = await authority.has_administrator_permission(
        payload.external_resource_id, assertion.platform_subject
    )
    logger.info(
        "Console platform connection verification completed organization_id=%s guild_id=%s verified=%s correlation_id=%s",
        organization_id,
        payload.external_resource_id,
        verified,
        assertion.correlation_id,
    )
    return {"verified": verified}


def _verify_request_assertion(authorization: str | None):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Control assertion is required")
    try:
        return verify_control_assertion(
            authorization.removeprefix("Bearer "),
            signing_key=signing_key_from_environment(),
            expected_resource="console.platform_connections",
            expected_action="manage",
        )
    except ControlAssertionRejectedError as error:
        raise HTTPException(
            status_code=401, detail="Control assertion is invalid"
        ) from error
