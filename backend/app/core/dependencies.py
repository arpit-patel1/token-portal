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
from app.services.redis_service import get_key as get_redis_key, delete_key as delete_redis_key, get_api_token_redis_key, set_key as set_redis_key # Added set_redis_key
import json
from datetime import datetime, timezone, timedelta # Added timedelta
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
    api_key_value: str = FastAPISecurity(api_key_header_auth),
    db: AsyncSession = Depends(get_db_session)  # Added db session dependency
) -> dict: # Returns a dict with token_id and user_id if valid
    """
    Validates an API key using Redis cache with a fallback to PostgreSQL.
    If valid, caches the token data in Redis.
    Raises HTTPException if invalid.
    Returns a dictionary with token_id and user_id if valid.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API Key or API Key expired"
    )
    if not api_key_value:
        logger.debug("API key validation: No API key provided in header.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated or API key missing"
        )

    hashed_api_key_to_verify = security.hash_value(api_key_value)
    redis_key_for_token = get_api_token_redis_key(hashed_api_key_to_verify)

    cached_data_str = await get_redis_key(redis_key_for_token)
    token_data_to_process = None

    if cached_data_str:
        logger.debug(f"API key validation: Found in Redis cache (Hashed Value Starts With: {hashed_api_key_to_verify[:10]}...).")
        try:
            token_data_to_process = json.loads(cached_data_str)
        except json.JSONDecodeError:
            logger.error(f"API key validation: Failed to decode JSON from Redis for key {redis_key_for_token}. Deleting corrupted key.")
            await delete_redis_key(redis_key_for_token) # Delete corrupted key from Redis
            # Fall through to DB lookup as if cache miss
            pass # Let it proceed to DB lookup
    
    if not token_data_to_process: # Not in cache or failed to parse from cache
        logger.info(f"API key validation: Not found in Redis or parse failed (Hashed Value Starts With: {hashed_api_key_to_verify[:10]}...). Attempting DB lookup.")
        token_db_record = await crud.get_api_token_by_hashed_token(db, hashed_token=hashed_api_key_to_verify)

        if not token_db_record:
            logger.warning(f"API key validation: Not found in DB (Hashed Value Starts With: {hashed_api_key_to_verify[:10]}...). Key is invalid.")
            raise credentials_exception

        # Prepare data for caching and validation logic
        expires_at_iso_str = token_db_record.expires_at.isoformat() if token_db_record.expires_at else None
        token_data_for_cache = {
            "token_id": token_db_record.id,
            "user_id": token_db_record.user_id,
            "is_revoked": token_db_record.is_revoked,
            "expires_at_iso": expires_at_iso_str,
            # Add any other fields from models.ApiToken that might be useful in cache
        }

        # Cache the data retrieved from DB
        cache_expiry_seconds = 3600 # Default 1 hour for cache entry
        if token_db_record.expires_at:
            # If token has an expiry, ensure cache expiry is not longer than token's remaining life
            # or set a max cache time (e.g. 24h) if token_expiry is very long / None
            now_utc = datetime.now(timezone.utc)
            if token_db_record.expires_at > now_utc:
                remaining_token_life_seconds = int((token_db_record.expires_at - now_utc).total_seconds())
                cache_expiry_seconds = min(cache_expiry_seconds, remaining_token_life_seconds)
            else: # Token is already expired based on DB record
                cache_expiry_seconds = 60 # Cache for a short time that it's expired
        
        if cache_expiry_seconds > 0:
          await set_redis_key(redis_key_for_token, json.dumps(token_data_for_cache), expire_seconds=cache_expiry_seconds)
          logger.info(f"API key validation: Found in DB and cached in Redis. Token ID: {token_db_record.id}, User ID: {token_db_record.user_id}. Cache Expiry: {cache_expiry_seconds}s.")
        else: # Token expired, don't cache or cache for very short time already handled
            logger.info(f"API key validation: Found in DB but token is expired. Token ID: {token_db_record.id}, User ID: {token_db_record.user_id}. Not caching beyond short period.")


        token_data_to_process = token_data_for_cache # Use data fetched from DB for current validation

    # Perform validation checks on token_data_to_process (whether from cache or fresh from DB)
    if token_data_to_process.get("is_revoked"):
        logger.warning(f"API key validation: Token ID {token_data_to_process.get('token_id')} is revoked.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API Key has been revoked"
        )

    if token_data_to_process.get("expires_at_iso"):
        try:
            aware_expires_at = datetime.fromisoformat(token_data_to_process["expires_at_iso"])
            if aware_expires_at <= datetime.now(timezone.utc):
                logger.info(f"API key validation: Token ID {token_data_to_process.get('token_id')} has expired. Deleting from Redis if was cached.")
                # Ensure it's deleted from Redis if it was the source of this expired data or if DB said it's expired
                await delete_redis_key(redis_key_for_token) 
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="API Key has expired"
                )
        except ValueError:
            logger.error(f"API key validation: Could not parse expires_at_iso ('{token_data_to_process['expires_at_iso']}') for token {token_data_to_process.get('token_id')}. Invalidating.")
            await delete_redis_key(redis_key_for_token) # Delete potentially corrupted key from Redis
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="API key validation error due to internal date format issue. Please try again later."
            )
    
    # If all checks pass, token is valid
    validated_data = {"token_id": token_data_to_process.get("token_id"), "user_id": token_data_to_process.get("user_id")}
    logger.info(f"API key validated successfully (Source: {'Cache' if cached_data_str and token_data_to_process else 'DB'}): {validated_data}")
    return validated_data

# get_current_active_admin will be added later 