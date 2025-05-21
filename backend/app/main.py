from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware # Corrected import

from app.core.logging_config import setup_logging
from app.core.config import settings
from app.api.v1.api import api_router # Import the main API router from app.api.v1.api
from app.db.session import engine
from app.db.base_class import Base # Corrected: Import Base from base_class.py
from app.services.redis_service import get_redis_client, close_redis_client # Redis service
# from app.core.middleware import ApiTokenValidationMiddleware # Commented out as per plan

setup_logging() # Initialize logging

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json" # Customize openapi URL if needed
)

# Event handlers for Redis and DB
@app.on_event("startup")
async def startup_event():
    await get_redis_client() # Initialize Redis
    # Initialize DB (e.g. create tables if not using Alembic and they don't exist)
    # This is a simplistic way; for production, Alembic is preferred.
    async with engine.begin() as conn:
        # await conn.run_sync(Base.metadata.drop_all) # Use with caution, drops all tables
        await conn.run_sync(Base.metadata.create_all)
    print("INFO:     Application startup complete. Connected to DB and Redis.")

@app.on_event("shutdown")
async def shutdown_event():
    await close_redis_client() # Close Redis
    # Dispose of the SQLAlchemy engine's connection pool
    await engine.dispose()
    print("INFO:     Application shutdown complete. Disconnected from DB and Redis.")


# CORS Configuration / Middleware
if settings.FRONTEND_URL:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(settings.FRONTEND_URL)], 
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Include the main API router from app/api/v1/api.py
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/", tags=["Root"])
async def read_root():
    return {"message": f"Welcome to {settings.PROJECT_NAME}! Visit /docs for API documentation."}
