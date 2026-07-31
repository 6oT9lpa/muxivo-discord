from fastapi import APIRouter, Depends, Query

from activity.server.dependencies import require_bearer_token
from activity.server.schemas.ai_moderation_channels import AiModerationChannelsPayload
from activity.server.schemas.ai_moderation_policy import AiModerationPolicyPayload
from activity.server.schemas.ai_moderation_review import AiModerationReviewUpdatePayload
from activity.server.schemas.ai_moderation_simulation import AiModerationSimulationPayload
from activity.server.schemas.media_policy import MediaPolicyPayload
from activity.server.services.ai_moderation_service import AiModerationService

router = APIRouter()
service = AiModerationService()


@router.get("/api/ai-moderator/settings")
async def get_ai_moderator_settings(guild_id: int = Query(gt=0), access_token: str = Depends(require_bearer_token)) -> dict[str, object]:
    return await service.get_settings(guild_id, access_token)


@router.get("/api/ai-moderator/media-policy")
async def get_media_policy(guild_id: int = Query(gt=0), access_token: str = Depends(require_bearer_token)) -> dict[str, object]:
    return await service.get_media_policy(guild_id, access_token)


@router.put("/api/ai-moderator/media-policy")
async def save_media_policy(payload: MediaPolicyPayload, access_token: str = Depends(require_bearer_token)) -> dict[str, object]:
    return await service.save_media_policy(payload, access_token)


@router.delete("/api/ai-moderator/media-policy")
async def reset_media_policy(
    guild_id: int = Query(gt=0), expected_revision: int = Query(ge=1),
    access_token: str = Depends(require_bearer_token),
) -> dict[str, object]:
    return await service.reset_media_policy(guild_id, expected_revision, access_token)


@router.get("/api/ai-moderator/metrics")
async def get_ai_moderator_metrics(guild_id: int = Query(gt=0), access_token: str = Depends(require_bearer_token)) -> dict[str, object]:
    return await service.get_metrics(guild_id, access_token)


@router.get("/api/ai-moderator/reviews")
async def get_ai_moderator_reviews(guild_id: int = Query(gt=0), status: str = Query("OPEN", pattern="^(OPEN|RESOLVED)$"), limit: int = Query(20, ge=1, le=50), offset: int = Query(0, ge=0), access_token: str = Depends(require_bearer_token)) -> dict[str, object]:
    return await service.list_review_items(guild_id, access_token, status, limit, offset)


@router.get("/api/ai-moderator/reviews/audit")
async def get_ai_moderator_review_audit(guild_id: int = Query(gt=0), limit: int = Query(20, ge=1, le=50), offset: int = Query(0, ge=0), access_token: str = Depends(require_bearer_token)) -> dict[str, object]:
    return await service.list_review_audit(guild_id, access_token, limit, offset)


@router.put("/api/ai-moderator/reviews/{item_id}")
async def update_ai_moderator_review(item_id: int, payload: AiModerationReviewUpdatePayload, access_token: str = Depends(require_bearer_token)) -> dict[str, object]:
    return await service.update_review_item(item_id, payload, access_token)


@router.post("/api/ai-moderator/simulate")
async def simulate_ai_moderator(payload: AiModerationSimulationPayload, access_token: str = Depends(require_bearer_token)) -> dict[str, object]:
    return await service.simulate(payload.guild_id, payload.message_text, access_token)


@router.put("/api/ai-moderator/channels")
async def save_ai_moderator_channels(payload: AiModerationChannelsPayload, access_token: str = Depends(require_bearer_token)) -> dict[str, object]:
    return await service.save_channels(payload, access_token)


@router.put("/api/ai-moderator/policy")
async def save_ai_moderator_policy(payload: AiModerationPolicyPayload, access_token: str = Depends(require_bearer_token)) -> dict[str, object]:
    return await service.save_policy(payload, access_token)
