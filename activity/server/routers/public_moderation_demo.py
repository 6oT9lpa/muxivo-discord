from fastapi import APIRouter, HTTPException

from activity.server.schemas.public_moderation_demo import PublicModerationDemoPayload
from activity.server.services.public_moderation_demo_service import PublicModerationDemoService
from infrastructure.logging import get_logger


logger = get_logger(__name__)
router = APIRouter()
service = PublicModerationDemoService()


@router.post("/api/public/moderation-demo/classify")
async def classify_public_demo(payload: PublicModerationDemoPayload) -> dict[str, object]:
    """Returns an AI decision for the website sandbox and never executes Discord actions."""

    try:
        return await service.classify(payload.message)
    except Exception as exc:
        logger.exception("Public moderation demo classification failed message_length=%s", len(payload.message))
        raise HTTPException(status_code=503, detail="Muxivo Core is temporarily unavailable") from exc
