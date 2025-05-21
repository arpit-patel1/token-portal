from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload # For eager loading relationships if needed later
from sqlalchemy import func # For func.now()
from datetime import datetime # For type hinting and setting expiry
from typing import Optional # For optional types

from app.db import models # Adjusted import for models
from app.schemas import UserCreate, UserRead, ApiTokenCreate, ApiUsageLogCreate # Added ApiUsageLogCreate
from pydantic import EmailStr

# User CRUD operations

async def get_user_by_id(db: AsyncSession, user_id: int) -> models.User | None:
    """Fetch a user by their ID."""
    result = await db.execute(select(models.User).filter(models.User.id == user_id))
    return result.scalars().first()

async def get_user_by_email(db: AsyncSession, email: EmailStr) -> models.User | None:
    """Fetch a user by their email address."""
    result = await db.execute(select(models.User).filter(models.User.email == email))
    return result.scalars().first()

async def create_user(db: AsyncSession, user_in: UserCreate) -> models.User:
    """Create a new user. Assumes email is unique due to model constraints."""
    db_user = models.User(email=user_in.email)
    # If UserCreate had more fields (e.g., role, is_active from an admin panel), they would be set here.
    # For OTP flow, user might be created with default role and active status.
    db.add(db_user)
    await db.flush() # Use flush to get the ID before commit if needed elsewhere, or if commit is handled by get_db_session
    await db.refresh(db_user) # Refresh to get DB-generated defaults like created_at
    return db_user

async def get_or_create_user(db: AsyncSession, user_in: UserCreate) -> models.User:
    """Get a user by email, or create them if they don't exist."""
    existing_user = await get_user_by_email(db=db, email=user_in.email)
    if existing_user:
        return existing_user
    return await create_user(db=db, user_in=user_in)

async def get_all_users(db: AsyncSession, skip: int = 0, limit: int = 100) -> list[models.User]:
    """Fetch all users with pagination."""
    result = await db.execute(
        select(models.User)
        .order_by(models.User.id)
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())

# ApiToken CRUD operations

async def create_api_token(
    db: AsyncSession, 
    token_in: ApiTokenCreate, 
    user_id: int, 
    hashed_token: str, 
    token_preview: str
) -> models.ApiToken:
    """Create a new API token for a user."""
    db_token = models.ApiToken(
        name=token_in.name,
        hashed_token=hashed_token,
        token_preview=token_preview,
        expires_at=token_in.expires_at,
        user_id=user_id
    )
    db.add(db_token)
    await db.flush()
    await db.refresh(db_token)
    return db_token

async def get_api_token_by_id_and_user_id(db: AsyncSession, token_id: int, user_id: int) -> models.ApiToken | None:
    """Get a specific API token by its ID, scoped to a user."""
    stmt = (
        select(models.ApiToken)
        .filter(models.ApiToken.id == token_id)
        .filter(models.ApiToken.user_id == user_id)
    )
    result = await db.execute(stmt)
    return result.scalars().first()

async def get_api_token_by_hashed_token(db: AsyncSession, hashed_token: str) -> models.ApiToken | None:
    """Get an API token by its hashed value (for validation)."""
    # Ensure this query is efficient, hashed_token should be indexed.
    stmt = select(models.ApiToken).filter(models.ApiToken.hashed_token == hashed_token)
    result = await db.execute(stmt)
    return result.scalars().first()

async def get_api_tokens_by_user_id(db: AsyncSession, user_id: int, skip: int = 0, limit: int = 100) -> list[models.ApiToken]:
    """List API tokens for a specific user."""
    stmt = (
        select(models.ApiToken)
        .filter(models.ApiToken.user_id == user_id)
        .order_by(models.ApiToken.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())

async def get_all_api_tokens(db: AsyncSession, skip: int = 0, limit: int = 100) -> list[models.ApiToken]:
    """List all API tokens (for admin view). Eager loads user email for convenience."""
    stmt = (
        select(models.ApiToken)
        .options(selectinload(models.ApiToken.user).load_only(models.User.email, models.User.id)) # Load only user email and id
        .order_by(models.ApiToken.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())

async def revoke_api_token(db: AsyncSession, api_token: models.ApiToken) -> models.ApiToken:
    """Mark the given API token as revoked and sets last_used_at if not already set (e.g. if revoked before use)."""
    if not api_token.is_revoked:
        api_token.is_revoked = True
        # Optionally, update last_used_at to now if it's an admin revoking an active token
        # api_token.last_used_at = api_token.last_used_at or datetime.utcnow()
        db.add(api_token)
        await db.flush()
        await db.refresh(api_token)
    return api_token

# ApiUsageLog CRUD operations

async def create_api_usage_log(db: AsyncSession, log_in: ApiUsageLogCreate) -> models.ApiUsageLog:
    """Create a new API usage log entry."""
    db_log = models.ApiUsageLog(
        **log_in.model_dump(exclude_unset=True) # Pass all fields from the schema
        # request_timestamp is handled by default=func.now() in the model
    )
    db.add(db_log)
    await db.flush()
    await db.refresh(db_log)
    return db_log

async def get_all_api_usage_logs(db: AsyncSession, skip: int = 0, limit: int = 100) -> list[models.ApiUsageLog]:
    """Fetch all API usage logs with pagination, ordered by most recent first."""
    result = await db.execute(
        select(models.ApiUsageLog)
        .order_by(models.ApiUsageLog.request_timestamp.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all()) 