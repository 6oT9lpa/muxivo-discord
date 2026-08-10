"""Private Control API endpoints called by Muxivo Console."""

import logging
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from activity.server.control_auth import (
    ControlAssertionRejectedError,
    signing_key_from_environment,
    verify_control_assertion,
)
from activity.server.services.dashboard_service import ActivityDashboardService
from activity.server.services.discord_guild_authority import DiscordGuildAuthority
from activity.server.services.health_service import ActivityHealthService
from activity.server.services.stats_service import ActivityStatsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/control/v1", tags=["control"])
authority = DiscordGuildAuthority()
health_service = ActivityHealthService()
dashboard_service = ActivityDashboardService()
stats_service = ActivityStatsService()

_CONTROL_MODULES = {
    "items": [
        {
            "key": "discord.health",
            "display_name": "Platform health",
            "platform": "discord",
            "capability": "view",
            "status": "available",
        },
        {
            "key": "discord.dashboard-summary",
            "display_name": "Dashboard summary",
            "platform": "discord",
            "capability": "view",
            "status": "available",
        },
        {
            "key": "discord.server-stats",
            "display_name": "Server stats",
            "platform": "discord",
            "capability": "view",
            "status": "available",
        },
    ]
}


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
    assertion = _verify_request_assertion(authorization, require_platform_subject=True)
    _require_assertion_organization(assertion.organization_id, organization_id)
    if assertion.platform_subject is None:
        raise HTTPException(status_code=401, detail="Control assertion is invalid")

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


@router.get("/organizations/{organization_id}/modules")
async def list_control_modules(
    organization_id: UUID,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, list[dict[str, str]]]:
    """Expose only browser-ready Discord modules to the Console BFF."""
    assertion = _verify_request_assertion(authorization)
    _require_assertion_organization(assertion.organization_id, organization_id)
    return _CONTROL_MODULES


@router.get("/organizations/{organization_id}/health")
async def get_platform_health(
    organization_id: UUID,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    """Return aggregate Discord health after Console RBAC authorization."""
    assertion = _verify_request_assertion(authorization)
    _require_assertion_organization(assertion.organization_id, organization_id)
    return (await health_service.get_platform_health()).model_dump(mode="json")


@router.get("/organizations/{organization_id}/connections/{guild_id}/dashboard")
async def get_dashboard_summary(
    organization_id: UUID,
    guild_id: str,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    """Return safe aggregate metrics for one assertion-bound Discord guild."""
    _validate_guild_id(guild_id)
    assertion = _verify_request_assertion(
        authorization, require_platform_resource_id=True
    )
    _require_assertion_organization(assertion.organization_id, organization_id)
    _require_assertion_platform_resource(assertion.platform_resource_id, guild_id)
    return {
        "guild_id": guild_id,
        "metrics": await dashboard_service.get_control_summary(int(guild_id)),
    }


@router.get("/organizations/{organization_id}/connections/{guild_id}/server-stats")
async def get_server_stats(
    organization_id: UUID,
    guild_id: str,
    period: int = Query(default=30, ge=1, le=365),
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    """Return the Activity server-stats snapshot for one assertion-bound guild."""
    _validate_guild_id(guild_id)
    assertion = _verify_request_assertion(
        authorization, require_platform_resource_id=True
    )
    _require_assertion_organization(assertion.organization_id, organization_id)
    _require_assertion_platform_resource(assertion.platform_resource_id, guild_id)
    return {
        "guild_id": guild_id,
        "stats": await stats_service.get_server_stats_snapshot(int(guild_id), period),
    }


def _verify_request_assertion(
    authorization: str | None,
    *,
    require_platform_subject: bool = False,
    require_platform_resource_id: bool = False,
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Control assertion is required")
    try:
        return verify_control_assertion(
            authorization.removeprefix("Bearer "),
            signing_key=signing_key_from_environment(),
            expected_resource=(
                "console.platform_connections"
                if require_platform_subject
                else "console.control_modules"
            ),
            expected_action="manage" if require_platform_subject else "read",
            require_platform_subject=require_platform_subject,
            require_platform_resource_id=require_platform_resource_id,
        )
    except ControlAssertionRejectedError as error:
        raise HTTPException(
            status_code=401, detail="Control assertion is invalid"
        ) from error


def _validate_guild_id(guild_id: str) -> None:
    if not guild_id.isdecimal() or len(guild_id) > 20:
        raise HTTPException(status_code=422, detail="Invalid Discord guild identifier")


def _require_assertion_platform_resource(
    assertion_platform_resource_id: str | None, guild_id: str
) -> None:
    if assertion_platform_resource_id == guild_id:
        return
    raise HTTPException(
        status_code=403,
        detail="Control assertion is not authorized for this platform resource",
    )


def _require_assertion_organization(
    assertion_organization_id: UUID, organization_id: UUID
) -> None:
    if assertion_organization_id == organization_id:
        return
    logger.warning(
        "Control assertion organization does not match the requested platform resource"
    )
    raise HTTPException(
        status_code=403,
        detail="Control assertion is not authorized for this organization",
    )
