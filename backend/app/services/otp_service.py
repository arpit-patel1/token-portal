import random
import string
from datetime import timedelta # datetime, timezone removed as Redis handles TTL
from loguru import logger

from sqlalchemy.ext.asyncio import AsyncSession # Still needed for user operations

from app.core.config import settings
from app.core import security
from app.db import crud # Still needed for user operations
from app.schemas import UserCreate, OtpRequest, OtpVerify, JWTToken
from app.services import email_service
from app.services.redis_service import set_key, get_key, delete_key # Reverted to absolute import from app root

def generate_otp_code(length: int = 5) -> str:
    """Generates a random OTP of specified length using digits."""
    return "".join(random.choices(string.digits, k=length))

def _get_otp_redis_key(email: str) -> str:
    """Generates a consistent Redis key for storing an OTP for a given email."""
    return f"otp:{email}"

async def request_otp_for_user(db: AsyncSession, otp_request: OtpRequest) -> bool:
    """Handles the logic for requesting an OTP for a user using Redis.
    1. Gets or creates the user (from PostgreSQL).
    2. Generates a new OTP.
    3. Hashes the OTP.
    4. Stores the hashed OTP in Redis with an expiry.
    5. Sends the plain OTP via email.
    Returns True if successful, False otherwise.
    """
    try:
        user = await crud.get_or_create_user(db, user_in=UserCreate(email=otp_request.email))
        if not user:
            logger.error(f"Could not get or create user for email: {otp_request.email}")
            return False

        plain_otp = generate_otp_code()
        hashed_otp = security.hash_value(plain_otp)
        
        redis_key = _get_otp_redis_key(otp_request.email)
        expire_seconds = int(timedelta(minutes=settings.OTP_EXPIRE_MINUTES).total_seconds())

        await set_key(redis_key, hashed_otp, expire_seconds=expire_seconds)

        email_sent = await email_service.send_otp_email(email_to=user.email, otp=plain_otp)
        if not email_sent:
            logger.error(f"Failed to send OTP email to {user.email}")
            # Clean up the OTP from Redis if email sending failed
            await delete_key(redis_key)
            return False
        
        logger.info(f"OTP requested via Redis and sent successfully for user: {user.email}")
        return True

    except Exception as e:
        logger.error(f"Error during OTP request process (Redis) for {otp_request.email}: {e}")
        return False 

async def verify_otp_and_generate_jwt(db: AsyncSession, otp_verify: OtpVerify) -> JWTToken | None:
    """Handles the logic for verifying an OTP from Redis and generating a JWT.
    1. Fetches the user by email (from PostgreSQL).
    2. Hashes the provided plain OTP.
    3. Retrieves the stored OTP hash from Redis.
    4. If hashes match, deletes OTP from Redis.
    5. Generates and returns a JWT for the user.
    Returns JWTToken if successful, None otherwise.
    """
    try:
        user = await crud.get_user_by_email(db, email=otp_verify.email)
        if not user:
            logger.warning(f"OTP verification attempt (Redis) for non-existent user: {otp_verify.email}")
            return None

        hashed_otp_to_verify = security.hash_value(otp_verify.otp)
        redis_key = _get_otp_redis_key(otp_verify.email)
        
        stored_hashed_otp = await get_key(redis_key)

        if not stored_hashed_otp:
            logger.warning(f"No OTP found in Redis for user: {user.email} (likely expired or already used)")
            return None

        if stored_hashed_otp != hashed_otp_to_verify:
            logger.warning(f"Invalid OTP provided (Redis) for user: {user.email}")
            # TODO: Implement rate limiting or lockout mechanism for repeated failures here
            return None

        # OTP is valid, delete it from Redis to prevent reuse
        await delete_key(redis_key)

        # Generate JWT
        token_data = {
            "sub": user.email,
            "user_id": user.id,
            "role": user.role
        }
        access_token = security.create_access_token(data=token_data)
        
        logger.info(f"OTP verified via Redis and JWT generated for user: {user.email}")
        return JWTToken(access_token=access_token, token_type="bearer")

    except Exception as e:
        logger.error(f"Error during OTP verification process (Redis) for {otp_verify.email}: {e}")
        return None 