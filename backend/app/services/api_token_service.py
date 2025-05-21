import secrets
import json # For serializing data to Redis
from datetime import datetime, timezone # For handling expiry
from loguru import logger

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.db import crud, models
from app.schemas import ApiTokenCreate, ApiTokenValue # ApiTokenValue for the response
from app.services.redis_service import set_key as set_redis_key # Reverted to absolute import
from app.services.redis_service import get_api_token_redis_key # Reverted to absolute import

# Configuration for token generation
API_TOKEN_PREFIX = "sk_live_" # Example prefix for live tokens
API_TOKEN_BYTE_LENGTH = 32    # Length of the random part in bytes
API_TOKEN_PREVIEW_RANDOM_CHARS = 4 # Number of random characters to show in preview after prefix

def generate_secure_api_token_string() -> str:
    """Generates a cryptographically secure API token string with a prefix."""
    random_part = secrets.token_urlsafe(API_TOKEN_BYTE_LENGTH)
    return f"{API_TOKEN_PREFIX}{random_part}"

def generate_token_preview(plain_token: str) -> str:
    """Generates a preview for the token (e.g., prefix + first few random chars)."""
    if plain_token.startswith(API_TOKEN_PREFIX):
        # Extract the part after the prefix
        random_part_preview = plain_token[len(API_TOKEN_PREFIX) : len(API_TOKEN_PREFIX) + API_TOKEN_PREVIEW_RANDOM_CHARS]
        return f"{API_TOKEN_PREFIX}{random_part_preview}..."
    # Fallback if prefix is not as expected (should not happen with generate_secure_api_token_string)
    return plain_token[:API_TOKEN_PREVIEW_RANDOM_CHARS+len(API_TOKEN_PREFIX)] + "..."

async def create_new_api_token(
    db: AsyncSession, 
    token_create_data: ApiTokenCreate, 
    user: models.User
) -> ApiTokenValue | None:
    """Handles the logic for creating a new API token for a user.
    Generates, hashes, stores in DB, caches in Redis, and returns the plain token value once.
    """
    try:
        plain_api_token = generate_secure_api_token_string()
        hashed_api_token = security.hash_value(plain_api_token)
        token_preview = generate_token_preview(plain_api_token)

        # Store in DB
        db_token = await crud.create_api_token(
            db=db,
            token_in=token_create_data,
            user_id=user.id,
            hashed_token=hashed_api_token,
            token_preview=token_preview
        )

        if not db_token: # Should not happen if crud operation is robust
            logger.error(f"Failed to store API token in DB for user {user.email}")
            return None

        # Cache essential data in Redis
        redis_key = get_api_token_redis_key(hashed_api_token)
        
        expires_at_iso = None
        redis_ttl_seconds = None

        if db_token.expires_at:
            aware_expires_at = db_token.expires_at.replace(tzinfo=timezone.utc) if db_token.expires_at.tzinfo is None else db_token.expires_at
            expires_at_iso = aware_expires_at.isoformat()
            
            now_utc = datetime.now(timezone.utc)
            if aware_expires_at > now_utc:
                redis_ttl_seconds = int((aware_expires_at - now_utc).total_seconds())

        token_cache_data = {
            "user_id": db_token.user_id,
            "token_id": db_token.id,
            "is_revoked": db_token.is_revoked, # Should be False for new token
            "expires_at_iso": expires_at_iso # Store as ISO string
        }
        
        await set_redis_key(
            redis_key, 
            json.dumps(token_cache_data), 
            expire_seconds=redis_ttl_seconds if redis_ttl_seconds and redis_ttl_seconds > 0 else None
        )
        logger.info(f"API token {db_token.id} cached in Redis for user {user.email}.")

        logger.info(f"New API token created for user {user.email} (ID: {user.id}), Token ID: {db_token.id}")
        
        # Return the plain token value and relevant metadata ONCE
        return ApiTokenValue(
            name=db_token.name,
            api_token=plain_api_token,
            expires_at=db_token.expires_at
            # The message is part of the ApiTokenValue schema by default
        )

    except Exception as e:
        logger.error(f"Error creating new API token for user {user.email} (ID: {user.id}): {e}")
        # Consider cleanup of DB entry if Redis caching fails, or use a transaction manager
        return None 