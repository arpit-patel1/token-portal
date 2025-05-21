from fastapi import APIRouter, Depends

from app.db import models # For current_user type hint
from app.schemas import UserRead # Response schema
from app.core.dependencies import get_current_active_user

router = APIRouter()

@router.get("/me", response_model=UserRead)
async def read_users_me(
    current_user: models.User = Depends(get_current_active_user)
):
    """
    Get current authenticated user's details.
    """
    # The current_user object is already a SQLAlchemy model instance.
    # Pydantic will automatically serialize it according to UserRead schema,
    # including fields like id, email, role, is_active.
    return current_user 