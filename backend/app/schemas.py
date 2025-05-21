from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional

# User Schemas
class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    # In this OTP-based auth, user might be created implicitly.
    # This schema can be used for explicit creation if needed, or internal use.
    pass

class UserRead(UserBase):
    id: int
    role: str = "user"
    is_active: bool = True

    model_config = {"from_attributes": True}

# OTP Schemas
class OtpRequest(BaseModel):
    email: EmailStr

class OtpVerify(BaseModel):
    email: EmailStr
    otp: str # The 5-digit OTP

# JWT Schemas
class JWTToken(BaseModel): # Schema for the JWT response after successful authentication
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel): # Schema for data encoded within the JWT
    email: Optional[EmailStr] = None
    user_id: Optional[int] = None
    role: Optional[str] = None
    # scopes: list[str] = [] # For future fine-grained permissions

# API Token Schemas (for user-generated API keys)
class ApiTokenBase(BaseModel):
    name: Optional[str] = None

class ApiTokenCreate(BaseModel):
    name: Optional[str] = None
    expires_at: Optional[datetime] = None # User can suggest an expiry, or server can set a default

class ApiTokenValue(BaseModel): # Schema to return the plain API token value ONCE
    name: Optional[str] = None
    api_token: str
    expires_at: Optional[datetime] = None
    message: str = "Please store this token securely. It will not be shown again."

class ApiTokenRead(ApiTokenBase): # For user to list their API tokens
    id: int
    token_preview: str # e.g., last 4 characters or a prefix like "sk_..."
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    is_revoked: bool = False

    model_config = {"from_attributes": True}

class ApiTokenAdminRead(ApiTokenRead): # For admin view of API tokens
    user_email: EmailStr

    model_config = {"from_attributes": True}

# API Usage Log Schemas
class ApiUsageLogBase(BaseModel):
    request_method: str
    request_path: str
    response_status_code: int
    client_ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    error_message: Optional[str] = None
    # api_token_id and user_id will be set by the system based on validated token or context

class ApiUsageLogCreate(ApiUsageLogBase):
    api_token_id: Optional[int] = None # Can be None if token is invalid/missing
    user_id: Optional[int] = None      # Can be None if token is invalid/user not identified
    # request_timestamp is set by default in model

class ApiUsageLogRead(ApiUsageLogBase):
    id: int
    api_token_id: Optional[int] = None
    user_id: Optional[int] = None
    request_timestamp: datetime

    model_config = {"from_attributes": True} 