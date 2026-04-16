from fastapi import FastAPI

from .api.router import router
from .config import settings


app = FastAPI(title=settings.app_name, version=settings.app_version)
app.include_router(router)