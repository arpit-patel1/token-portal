import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from fastapi import HTTPException, status

from app.core.config import settings
from app.schemas import TokenData # Assuming TokenData schema is defined

# Hashing functions (SHA256 for OTPs and API Tokens)
def hash_value(value: str) -> str:
    """Hashes a string value using SHA256."""
    return hashlib.sha256(value.encode()).hexdigest()

def verify_hashed_value(plain_value: str, hashed_value: str) -> bool:
    """Verifies a plain string value against its SHA256 hash."""
    return hash_value(plain_value) == hashed_value

# JWT utility functions
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def verify_access_token(token: str, credentials_exception: HTTPException) -> TokenData:
    """
    Verifies the JWT. If valid, returns TokenData.
    If invalid (e.g., signature, expiry), raises the provided credentials_exception.
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        email: Optional[str] = payload.get("sub") # Assuming 'sub' (subject) is email, common practice
        user_id: Optional[int] = payload.get("user_id")
        role: Optional[str] = payload.get("role")
        
        if email is None or user_id is None:
            raise credentials_exception # Or a more specific error
        
        # You might want to add more validation here, e.g., check if token is blacklisted
        
        return TokenData(email=email, user_id=user_id, role=role)
    except JWTError:
        raise credentials_exception
    except Exception: # Catch any other unexpected errors during parsing
        raise credentials_exception 