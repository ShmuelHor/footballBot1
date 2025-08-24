from __future__ import annotations
import uvicorn
from fastapi import FastAPI

from app.core.logging_config import setup_logging
from app.core import config
from app.services.football_api import FootballAPI
from app.scheduler import FootballScheduler
from app.api.routes import router, set_api_instance

logger = setup_logging()

api = FootballAPI()
scheduler: FootballScheduler | None = None
app = FastAPI(title=config.APP_TITLE, version=config.APP_VERSION)
app.include_router(router)

@app.on_event("startup")
async def startup():
    global scheduler
    await api.startup()
    set_api_instance(api)
    scheduler = FootballScheduler(api)
    scheduler.start()
    logger.info("Application startup complete")

@app.on_event("shutdown")
async def shutdown():
    await api.shutdown()
    logger.info("Application shutdown complete")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=3000, reload=False)
