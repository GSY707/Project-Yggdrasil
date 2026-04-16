from fastapi import FastAPI

from yggdrasil_sdk import instrument_fastapi_app

from .api.router import router
from .config import settings


app = FastAPI(title=settings.app_name, version=settings.app_version)
instrument_fastapi_app(app, "core-api")
app.include_router(router)