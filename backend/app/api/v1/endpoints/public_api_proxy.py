from fastapi import APIRouter, Security, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import validate_api_key
from app.db.session import get_db_session # For DB operations if needed
from app.db import crud, models # For API usage logging
from app.schemas import ApiUsageLogCreate # For API usage logging
from datetime import datetime # For timestamping
from starlette.requests import Request # To get request details

from app.core.config import settings # May not be needed for a simple test
# If we want to access the user identified by the API token (set by middleware):
# from app.core.dependencies import get_current_user_from_token # A new dependency we might need
# from app.schemas import UserRead # If returning user info

# This router will be mounted under /api/public by main.py
# The ApiTokenValidationMiddleware in main.py should protect it.
router = APIRouter()

@router.get("/test")
async def test_public_api_endpoint():
    """
    A simple test endpoint for the public API, protected by API token middleware.
    If the middleware allows the request, this will be executed.
    """
    # The middleware should have already validated the token.
    # If we wanted to get user details associated with the token,
    # we would add a dependency here that retrieves it from request.state.user or similar
    # which the middleware would have set.
    return {"message": "Public API test endpoint reached successfully!", "status": "ok"}

@router.get("/ping", tags=["Public API"])
async def public_ping(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    api_key_data: dict = Depends(validate_api_key)
):
    """
    A public test endpoint protected by an API key.
    Logs the API usage upon successful validation.
    Returns a pong message with validated token information.
    """
    # API usage logging
    # Ensure all fields in ApiUsageLogCreate are provided or have defaults.
    log_entry = ApiUsageLogCreate(
        api_token_id=api_key_data.get("token_id"),
        user_id=api_key_data.get("user_id"),
        request_timestamp=datetime.utcnow(), 
        request_method=request.method,
        request_path=request.url.path,
        response_status_code=200, # Assuming success for a ping
        client_ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        # error_message would be null for successful ping
    )
    await crud.create_api_usage_log(db=db, log_in=log_entry)

    return {
        "message": "Pong! API key is valid.",
        "token_info": api_key_data,
        "requester_ip": request.client.host if request.client else "unknown"
    }

# You could add more public endpoints here later.
# For example, if you were proxying to another service:
# @router.get("/proxy/{path:path}")
# async def proxy_public_api(path: str):
#     # Logic to call another service using the validated token/user context
#     return {"message": f"Would proxy to {path}"} 