from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.db import crud, models # For current_admin type hint and crud usage
from app.db.session import get_db_session
from app.schemas import UserRead, ApiTokenAdminRead, ApiUsageLogRead # Added ApiUsageLogRead
from app.core.dependencies import get_current_active_admin

router = APIRouter()

@router.get("/users", response_model=List[UserRead])
async def admin_list_users(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db_session),
    current_admin: models.User = Depends(get_current_active_admin) # Protected by admin role
):
    """
    (Admin) List all users.
    """
    if skip < 0:
        raise HTTPException(status_code=400, detail="Skip parameter cannot be negative.")
    if limit <= 0:
        raise HTTPException(status_code=400, detail="Limit parameter must be positive.")

    users = await crud.get_all_users(db=db, skip=skip, limit=limit)
    return users

@router.get("/tokens", response_model=List[ApiTokenAdminRead])
async def admin_list_api_tokens(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db_session),
    current_admin: models.User = Depends(get_current_active_admin)
):
    """
    (Admin) List all API tokens with extended metadata.
    """
    if skip < 0:
        raise HTTPException(status_code=400, detail="Skip parameter cannot be negative.")
    if limit <= 0:
        raise HTTPException(status_code=400, detail="Limit parameter must be positive.")

    tokens = await crud.get_all_api_tokens(db=db, skip=skip, limit=limit)
    # The ApiTokenAdminRead schema expects user_email to be populated.
    # crud.get_all_api_tokens eager loads user.email.
    # Pydantic should map this correctly if the relationship is set up.
    # If user_email is not directly on the token model but on token.user.email, 
    # and from_attributes (orm_mode) is True, it should work.
    # Let's verify the ApiTokenAdminRead schema and the get_all_api_tokens CRUD.
    
    # The ApiTokenAdminRead schema includes user_email and inherits other fields.
    # The get_all_api_tokens eager loads user.email via `options(selectinload(models.ApiToken.user).load_only(models.User.email))`
    # This should be sufficient for Pydantic to construct ApiTokenAdminRead correctly.
    return tokens

@router.get("/usage/logs", response_model=List[ApiUsageLogRead])
async def admin_list_api_usage_logs(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db_session),
    current_admin: models.User = Depends(get_current_active_admin)
):
    """
    (Admin) List all API usage logs.
    """
    if skip < 0:
        raise HTTPException(status_code=400, detail="Skip parameter cannot be negative.")
    if limit <= 0:
        raise HTTPException(status_code=400, detail="Limit parameter must be positive.")

    logs = await crud.get_all_api_usage_logs(db=db, skip=skip, limit=limit)
    return logs

# Other admin endpoints will be added here 