from fastapi import FastAPI

from activity.server.routers import (
    activity_roles,
    auth,
    bot_settings,
    channel_purposes,
    control,
    creator_alerts,
    dashboard,
    dev_blog,
    discord,
    health,
    integrations,
    logs,
    media,
    rbac,
    session,
    stats,
    voice_rooms,
    welcome,
    ai_moderation,
    public_moderation_demo,
)


def include_activity_routers(app: FastAPI) -> None:
    app.include_router(control.router)
    app.include_router(auth.router)
    app.include_router(session.router)
    app.include_router(rbac.router)
    app.include_router(dashboard.router)
    app.include_router(welcome.router)
    app.include_router(ai_moderation.router)
    app.include_router(public_moderation_demo.router)
    app.include_router(activity_roles.router)
    app.include_router(discord.router)
    app.include_router(channel_purposes.router)
    app.include_router(dev_blog.router)
    app.include_router(creator_alerts.router)
    app.include_router(voice_rooms.router)
    app.include_router(stats.router)
    app.include_router(logs.router)
    app.include_router(media.router)
    app.include_router(bot_settings.router)
    app.include_router(integrations.router)
    app.include_router(health.router)
