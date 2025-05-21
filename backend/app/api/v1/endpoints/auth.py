from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session # Ensure this path is correct
from app.schemas import OtpRequest, OtpVerify, JWTToken # Added OtpVerify, JWTToken
from app.services import otp_service

router = APIRouter()

@router.post("/request-otp", status_code=status.HTTP_200_OK)
async def request_otp_endpoint(
    otp_request: OtpRequest, 
    db: AsyncSession = Depends(get_db_session)
):
    """
    Requests an OTP for the provided email address.
    The OTP is sent via email.
    """
    success = await otp_service.request_otp_for_user(db=db, otp_request=otp_request)
    if not success:
        # Generic error to avoid leaking info about whether an email exists or if another error occurred
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Could not process OTP request. Please try again later."
        )
    return {"message": "OTP has been sent to your email address if it is registered."}

@router.post("/verify-otp", response_model=JWTToken)
async def verify_otp_endpoint(
    otp_verify: OtpVerify, 
    db: AsyncSession = Depends(get_db_session)
):
    """
    Verifies the OTP and returns a JWT access token if successful.
    """
    jwt_token = await otp_service.verify_otp_and_generate_jwt(db=db, otp_verify=otp_verify)
    if not jwt_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Invalid OTP, email, or OTP has expired. Please try again."
            # Consider more specific errors if needed, but generic for security for now
        )
    return jwt_token

# /verify-otp endpoint will be added here later 