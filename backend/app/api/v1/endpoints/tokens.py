from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import json
from datetime import datetime, timezone
from loguru import logger

from app.db.session import get_db_session
from app.db import crud, models # Added crud for new endpoint
from app.schemas import ApiTokenCreate, ApiTokenValue, ApiTokenRead # Added ApiTokenRead
from app.services import api_token_service
from app.core.dependencies import get_current_active_user
from app.services.redis_service import get_key as get_redis_key, set_key as set_redis_key, delete_key as delete_redis_key, get_api_token_redis_key

router = APIRouter()

@router.post("", response_model=ApiTokenValue, status_code=status.HTTP_201_CREATED)
async def create_user_api_token(
    token_create_data: ApiTokenCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: models.User = Depends(get_current_active_user)
):
    """
    Creates a new API token for the authenticated user.
    The plain token is returned ONCE in the response.
    """
    api_token_value = await api_token_service.create_new_api_token(
        db=db, 
        token_create_data=token_create_data, 
        user=current_user
    )
    if not api_token_value:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create API token. Please try again later."
        )
    return api_token_value

@router.get("", response_model=list[ApiTokenRead])
async def list_user_api_tokens(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db_session),
    current_user: models.User = Depends(get_current_active_user)
):
    """
    Lists API tokens for the authenticated user (metadata only).
    """
    if skip < 0:
        raise HTTPException(status_code=400, detail="Skip parameter cannot be negative.")
    if limit <= 0:
        raise HTTPException(status_code=400, detail="Limit parameter must be positive.")
        
    api_tokens = await crud.get_api_tokens_by_user_id(
        db=db, user_id=current_user.id, skip=skip, limit=limit
    )
    # ApiTokenRead schema will handle formatting, including token_preview
    return api_tokens

@router.delete("/{token_id}", response_model=ApiTokenRead)
async def revoke_user_api_token(
    token_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: models.User = Depends(get_current_active_user)
):
    """
    Revokes an API token for the authenticated user.
    Updates both PostgreSQL and Redis cache.
    Returns the updated token metadata.
    """
    db_token = await crud.get_api_token_by_id_and_user_id(
        db=db, token_id=token_id, user_id=current_user.id
    )
    if not db_token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API Token not found or you do not own this token.")

    if db_token.is_revoked:
        logger.info(f"Token ID {db_token.id} is already revoked. No action taken.")
        return db_token 
    
    updated_token_db = await crud.revoke_api_token(db=db, api_token=db_token)

    # Update Redis cache
    if updated_token_db and updated_token_db.is_revoked:
        redis_key = get_api_token_redis_key(updated_token_db.hashed_token)
        
        cached_data_str = await get_redis_key(redis_key)
        if cached_data_str:
            try:
                token_cache_data = json.loads(cached_data_str)
                token_cache_data["is_revoked"] = True
                
                redis_ttl_seconds = None
                # Check if token also expired, if so, delete from Redis, otherwise update with TTL
                if token_cache_data.get("expires_at_iso"):
                    aware_expires_at = datetime.fromisoformat(token_cache_data["expires_at_iso"])
                    now_utc = datetime.now(timezone.utc)
                    if aware_expires_at <= now_utc: # Token is expired
                        await delete_redis_key(redis_key)
                        logger.info(f"Revoked token {updated_token_db.id} was also expired. Deleted from Redis cache.")
                        return updated_token_db 
                    else: # Token not expired yet, preserve original TTL
                        redis_ttl_seconds = int((aware_expires_at - now_utc).total_seconds())
                
                await set_redis_key(
                    redis_key, 
                    json.dumps(token_cache_data),
                    # ensure positive TTL or None
                    expire_seconds=redis_ttl_seconds if redis_ttl_seconds and redis_ttl_seconds > 0 else None 
                )
                logger.info(f"API token {updated_token_db.id} updated in Redis cache to revoked (is_revoked: True).")
            except json.JSONDecodeError:
                 logger.error(f"Failed to decode JSON from Redis for key {redis_key} during revocation.")
                 # Decide if we should delete the key if it's corrupted
                 await delete_redis_key(redis_key) # Safer to delete corrupted key
            except ValueError: # from datetime.fromisoformat
                 logger.error(f"Could not parse expires_at_iso from Redis for token {updated_token_db.id} during revocation.")
                 await delete_redis_key(redis_key) # Safer to delete corrupted key
        else:
            # Token was revoked in DB but not found in Redis. This is an inconsistency.
            # Log it. Ideally, this shouldn't happen if creation path is robust.
            # For safety, we could add a new Redis entry marking it as revoked, but this implies prior issue.
            logger.warning(f"API token {updated_token_db.id} (hashed: {updated_token_db.hashed_token}) was revoked in DB, but not found in Redis cache. Logging inconsistency.")
            # As a fallback, ensure it is not wrongly active in cache by deleting (though it was not found).
            # Or, create a new entry marking it as revoked:
            # token_cache_data = {
            #     "user_id": updated_token_db.user_id,
            #     "token_id": updated_token_db.id,
            #     "is_revoked": True,
            #     "expires_at_iso": updated_token_db.expires_at.isoformat() if updated_token_db.expires_at else None
            # }
            # await set_redis_key(redis_key, json.dumps(token_cache_data)) 
            # logger.info(f"Added placeholder for revoked token {updated_token_db.id} to Redis due to cache miss.")

    return updated_token_db

# GET /tokens and DELETE /tokens/{token_id} will be added here later 