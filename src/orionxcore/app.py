from fastapi import FastAPI

from orionxcore.api.routes import router
from orionxcore.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.include_router(router)
    return app

