import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from backend.app.core.config import settings
from backend.app.db.session import init_db
from backend.app.api.router import router as router_api
from backend.app.api.analytics import router as analytics_api
from backend.app.api.config import router as config_api

# Async context manager for database initialization
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    init_db()
    yield
    # Shutdown actions (if any)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Dynamic confidence-based multi-agent routing system for cost optimization.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configurations
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.staticfiles import StaticFiles

# Include API router components
app.include_router(router_api, prefix=f"{settings.API_V1_STR}/router", tags=["router"])
app.include_router(analytics_api, prefix=f"{settings.API_V1_STR}/analytics", tags=["analytics"])
app.include_router(config_api, prefix=f"{settings.API_V1_STR}/config", tags=["config"])

# Serve dashboard static files at root
app.mount("/", StaticFiles(directory="backend/app/static", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
