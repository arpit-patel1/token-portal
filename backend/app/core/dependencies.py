from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError # Though verify_access_token handles it, good to be aware

from app.core import security
from app.core.config import settings # For tokenUrl if using OAuth2PasswordBearer with FastAPI's own login
from app.db import crud
from app.db import models # For type hinting User model
from app.db.session import get_db_session
from app.schemas import TokenData # For type hinting from verify_access_token

# Added imports for API Key validation
from fastapi import Security as FastAPISecurity # Renamed to avoid conflict
from fastapi.security.api_key import APIKeyHeader
from app.services.redis_service import get_key as get_redis_key, delete_key as delete_redis_key, get_api_token_redis_key
import json
from datetime import datetime, timezone
from loguru import logger

# OAuth2PasswordBearer scheme
# The tokenUrl should point to your token-issuing endpoint, e.g., /api/v1/auth/verify-otp 
# or a dedicated /token endpoint if you implement OAuth2 password flow directly.
# For OTP flow, this is more for documentation and tools like Swagger UI.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/verify-otp")

# API Key authentication setup
API_KEY_NAME = "X-API-Key" # Common header name for API keys
api_key_header_auth = APIKeyHeader(name=API_KEY_NAME, auto_error=False) # auto_error=False for custom error handling

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db_session)
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token_data = security.verify_access_token(
            token=token, 
            credentials_exception=credentials_exception
        )
    except JWTError: # verify_access_token should raise, but being explicit
        raise credentials_exception
    
    if token_data.user_id is None:
        # This case should ideally be caught by verify_access_token if user_id is mandatory in TokenData
        raise credentials_exception

    user = await crud.get_user_by_id(db, user_id=token_data.user_id)
    if user is None:
        raise credentials_exception # User not found in DB
    
    # Optional: Check if user is active (if you have an is_active flag)
    # if not user.is_active:
    #     raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
        
    return user

async def get_current_active_user(
    current_user: models.User = Depends(get_current_user)
) -> models.User:
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user

async def get_current_active_admin(
    current_user: models.User = Depends(get_current_active_user)
) -> models.User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="The user does not have enough privileges"
        )
    return current_user

# New dependency for API Key validation
async def validate_api_key(
    api_key_value: str = FastAPISecurity(api_key_header_auth) 
) -> dict: # Returns a dict with token_id and user_id if valid
    """
    Validates an API key using Redis cache.
    Raises HTTPException if invalid.
    Returns a dictionary with token_id and user_id if valid.
    """
    if not api_key_value:
        logger.debug("API key validation: No API key provided in header.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated or API key missing"
        )

    hashed_api_key_to_verify = security.hash_value(api_key_value)
    redis_key = get_api_token_redis_key(hashed_api_key_to_verify)

    cached_data_str = await get_redis_key(redis_key)

    if not cached_data_str:
        logger.warning(f"API key validation: Key not found in Redis (Hashed Value Starts With: {hashed_api_key_to_verify[:10]}...). Possible invalid key or cache miss.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key or API Key expired"
        )

    try:
        token_data = json.loads(cached_data_str)
    except json.JSONDecodeError:
        logger.error(f"API key validation: Failed to decode JSON from Redis for key {redis_key}. Deleting corrupted key.")
        await delete_redis_key(redis_key) # Delete corrupted key from Redis
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key validation error. Please try again later."
        )

    if token_data.get("is_revoked"):
        logger.warning(f"API key validation: Token ID {token_data.get('token_id')} is revoked.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API Key has been revoked"
        )

    if token_data.get("expires_at_iso"):
        try:
            aware_expires_at = datetime.fromisoformat(token_data["expires_at_iso"])
            if aware_expires_at <= datetime.now(timezone.utc):
                logger.info(f"API key validation: Token ID {token_data.get('token_id')} has expired. Deleting from Redis.")
                await delete_redis_key(redis_key) # Delete expired key from Redis
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="API Key has expired"
                )
        except ValueError:
            logger.error(f"API key validation: Could not parse expires_at_iso ('{token_data['expires_at_iso']}') from Redis for token {token_data.get('token_id')}. Deleting corrupted key.")
            await delete_redis_key(redis_key) # Delete corrupted key from Redis
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="API key validation error due to internal date format issue. Please try again later."
            )
    
    # If all checks pass, token is valid
    validated_data = {"token_id": token_data.get("token_id"), "user_id": token_data.get("user_id")}
    logger.info(f"API key validated successfully: {validated_data}")
    return validated_data

# get_current_active_admin will be added later 