from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, Query

from activity.server.dependencies import require_bearer_token
from activity.server.services.logs_service import LogsService

router = APIRouter()
service = LogsService()


@router.get("/api/logs")
async def list_activity_logs(
    guild_id: int = Query(gt=0),
    source: Literal["messages", "audit", "all", "moderator", "welcome", "channel", "activity", "ai"] = "all",
    event_type: Optional[str] = None,
    q: str = Query(default="", max_length=200),
    limit: int = Query(default=50, ge=1, le=200),
    access_token: str = Depends(require_bearer_token),
) -> dict[str, list[dict[str, Any]]]:
    return await service.list_logs(guild_id, source, event_type, q, limit, access_token)


@router.get("/api/logs/actors")
async def list_activity_log_actors(
    guild_id: int = Query(gt=0),
    access_token: str = Depends(require_bearer_token),
) -> list[dict[str, str]]:
    return await service.list_actors(guild_id, access_token)
