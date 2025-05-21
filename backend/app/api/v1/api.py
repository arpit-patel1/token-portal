from fastapi import APIRouter

# Assuming standard endpoint modules, adjust imports as per your actual structure
from app.api.v1.endpoints import auth
from app.api.v1.endpoints import users
from app.api.v1.endpoints import tokens
from app.api.v1.endpoints import admin
from app.api.v1.endpoints import public_api_proxy # Newly added router

api_router = APIRouter()

# Include existing routers - these are placeholders if not yet created
# Ensure these .py files and their `router` objects exist in app/api/v1/endpoints/
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(tokens.router, prefix="/tokens", tags=["User Tokens"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])

# Include the new public API router
api_router.include_router(public_api_proxy.router, prefix="/public", tags=["Public API"]) 