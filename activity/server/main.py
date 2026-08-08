from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from activity.server.config import activity_server_config
from core.product_identity import ACTIVITY_PRODUCT_NAME
from activity.server.dependencies import initialize_activity_dependencies, shutdown_activity_dependencies
from activity.server.middleware import configure_activity_middleware
from activity.server.routers import include_activity_routers
from infrastructure.logging import get_logger


logger = get_logger(__name__)


def create_app() -> FastAPI:
    logger.info("Creating %s API application", ACTIVITY_PRODUCT_NAME)
    app = FastAPI(title=f"{ACTIVITY_PRODUCT_NAME} API")
    configure_activity_middleware(app)

    @app.on_event("startup")
    async def startup() -> None:
        logger.info("Starting Activity dependencies")
        await initialize_activity_dependencies()
        logger.info("Activity dependencies started")

    @app.on_event("shutdown")
    async def shutdown() -> None:
        logger.info("Shutting down Activity dependencies")
        await shutdown_activity_dependencies()
        logger.info("Activity dependencies stopped")

    include_activity_routers(app)
    mount_activity_client(app)
    return app


def mount_activity_client(app: FastAPI) -> None:
    client_dist = activity_server_config.client_dist
    if client_dist.exists():
        logger.info("Mounting Activity client assets from %s", client_dist)
        app.mount("/assets", StaticFiles(directory=client_dist / "assets"), name="activity-assets")
    else:
        logger.warning("Activity client dist directory not found: %s", client_dist)


app = create_app()


@app.get("/{path:path}")
async def serve_activity(path: str) -> FileResponse:
    if path.startswith("api/"):
        logger.warning("Activity static handler rejected API path=%s", path)
        raise HTTPException(status_code=404)

    client_dist = activity_server_config.client_dist.resolve()
    requested = (client_dist / path).resolve()
    if not _is_path_inside(requested, client_dist):
        logger.warning("Activity static handler rejected path traversal")
        raise HTTPException(status_code=404)

    if requested.is_file():
        logger.info("Serving Activity static file path=%s", requested.relative_to(client_dist))
        return FileResponse(requested)

    index_file = (client_dist / "index.html").resolve()
    if not index_file.is_file():
        logger.warning("Activity client index is unavailable")
        raise HTTPException(status_code=404)
    logger.info("Serving Activity SPA fallback")
    return FileResponse(index_file)


def _is_path_inside(candidate, root) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True
