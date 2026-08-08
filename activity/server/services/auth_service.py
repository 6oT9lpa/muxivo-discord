import os
from typing import Any

from fastapi import HTTPException

from activity.server.config import activity_server_config
from activity.server.schemas.auth import TokenRequest
from activity.server.utils.http_client import discord_async_client
from infrastructure.logging import get_logger


logger = get_logger(__name__)


class ActivityAuthService:
    async def exchange_token(self, payload: TokenRequest) -> dict[str, Any]:
        logger.info("Exchanging Discord OAuth code for Activity token")
        client_id = os.getenv("DISCORD_CLIENT_ID")
        client_secret = os.getenv("DISCORD_CLIENT_SECRET")

        if not client_id or not client_secret:
            logger.error("Discord OAuth exchange failed because client credentials are missing")
            raise HTTPException(
                status_code=500,
                detail="DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET are required",
            )

        data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "authorization_code",
            "code": payload.code,
        }

        async with discord_async_client(timeout=10) as client:
            response = await client.post(
                f"{activity_server_config.discord_api_base}/oauth2/token",
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        if response.status_code >= 400:
            try:
                error_code = str(response.json().get("error", "unknown"))
            except (TypeError, ValueError):
                error_code = "unknown"
            logger.warning(
                "Discord OAuth token exchange failed status=%s error=%s",
                response.status_code,
                error_code,
            )
            raise HTTPException(status_code=401, detail="Discord authorization code was rejected")

        try:
            token = response.json()
            access_token = token["access_token"]
        except (KeyError, TypeError, ValueError):
            logger.error("Discord OAuth exchange returned an invalid response")
            raise HTTPException(status_code=502, detail="Discord OAuth returned an invalid response")
        if not isinstance(access_token, str) or not access_token:
            logger.error("Discord OAuth exchange returned an empty access token")
            raise HTTPException(status_code=502, detail="Discord OAuth returned an invalid response")
        logger.info("Discord OAuth token exchange completed scope=%s expires_in=%s", token.get("scope", ""), token.get("expires_in", 0))
        return {
            "access_token": access_token,
            "token_type": token.get("token_type", "Bearer"),
            "expires_in": token.get("expires_in", 0),
            "scope": token.get("scope", ""),
        }
