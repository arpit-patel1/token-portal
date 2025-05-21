from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from loguru import logger
from datetime import datetime, timezone # For checking token expiry and updating last_used_at

from app.core import security
from app.db import crud, models
from app.db.session import AsyncSessionLocal # Import the session factory
from app.schemas import ApiUsageLogCreate
from app.core.config import settings

class ApiTokenValidationMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        # Only apply middleware to paths starting with /api/v1/public/
        # Note: settings.API_V1_STR usually is /api/v1, so public_api_path_prefix would be /api/v1/public
        public_api_path_prefix = f"{settings.API_V1_STR}/public"
        
        if not request.url.path.startswith(public_api_path_prefix):
            return await call_next(request)

        # Initialize log data (some fields will be updated based on auth outcome)
        log_data = ApiUsageLogCreate(
            request_method=request.method,
            request_path=request.url.path,
            response_status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, # Default, will be updated
            client_ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            api_token_id=None,
            user_id=None,
            error_message=None
        )

        # Get DB session manually as Depends() doesn't work directly in middleware dispatch
        async with AsyncSessionLocal() as db:
            try:
                plain_token: str | None = None
                auth_header = request.headers.get("Authorization")
                x_api_key_header = request.headers.get("X-API-Key")

                if x_api_key_header:
                    plain_token = x_api_key_header
                elif auth_header and auth_header.startswith("Bearer "):
                    plain_token = auth_header.split("Bearer ", 1)[1].strip()
                
                if not plain_token:
                    log_data.error_message = "API token not provided."
                    log_data.response_status_code = status.HTTP_401_UNAUTHORIZED
                    await crud.create_api_usage_log(db, log_in=log_data)
                    return Response("API token required.", status_code=status.HTTP_401_UNAUTHORIZED)

                # For public API tokens, we don't hash the provided token during lookup.
                # We expect the *stored* token to be hashed. The provided token is the *plain* token.
                # So, we should fetch by the plain token if we stored plain tokens (not recommended for API keys)
                # OR, hash the provided plain_token and find a match for the stored hashed_token.
                # The checklist implies hashing the token before storage, so we hash the input token.
                
                # This interpretation is based on: D.User API Token Mgmt -> Hash API token (SHA256)
                # And E.Public API Validation -> Validate token: hash comparison
                # However, standard practice for API keys is often to store a hash of the key.
                # If the API key itself IS the secure random string, and we store its hash for verification:
                
                hashed_provided_token = security.hash_value(plain_token)
                db_token = await crud.get_api_token_by_hashed_token(db, hashed_token=hashed_provided_token)

                if not db_token:
                    log_data.error_message = "Invalid API token (not found)."
                    log_data.response_status_code = status.HTTP_401_UNAUTHORIZED
                    await crud.create_api_usage_log(db, log_in=log_data)
                    return Response("Invalid API token.", status_code=status.HTTP_401_UNAUTHORIZED)
                
                log_data.api_token_id = db_token.id
                log_data.user_id = db_token.user_id

                if db_token.is_revoked:
                    log_data.error_message = "API token has been revoked."
                    log_data.response_status_code = status.HTTP_403_FORBIDDEN
                    await crud.create_api_usage_log(db, log_in=log_data)
                    return Response("API token has been revoked.", status_code=status.HTTP_403_FORBIDDEN)

                if db_token.expires_at and db_token.expires_at.replace(tzinfo=None) < datetime.utcnow(): # Naive comparison
                    log_data.error_message = "API token has expired."
                    log_data.response_status_code = status.HTTP_403_FORBIDDEN
                    await crud.create_api_usage_log(db, log_in=log_data)
                    return Response("API token has expired.", status_code=status.HTTP_403_FORBIDDEN)
                
                # Token is valid, update last_used_at (best effort)
                utc_now = datetime.now(timezone.utc)
                db_token.last_used_at = utc_now.replace(tzinfo=None) # Make it offset-naive
                db.add(db_token)
                # No need to await flush/commit here if session commit is handled by context manager
                # or if a small delay/potential miss on last_used_at is acceptable.
                # For critical updates, ensure flush. The get_db_session in endpoints auto-commits.
                # Here, AsyncSessionLocal() context manager will handle commit/rollback.

                # Store token and user in request.state for endpoint access
                request.state.current_api_token = db_token
                request.state.current_user = await crud.get_user_by_id(db, user_id=db_token.user_id)
                # Ensure user is active if that's a requirement for API token usage
                if not request.state.current_user or not request.state.current_user.is_active:
                    log_data.error_message = "User associated with API token is inactive or not found."
                    log_data.response_status_code = status.HTTP_403_FORBIDDEN
                    await crud.create_api_usage_log(db, log_in=log_data)
                    return Response("User account issue.", status_code=status.HTTP_403_FORBIDDEN)

                # If all checks pass, proceed to the endpoint
                log_data.response_status_code = status.HTTP_200_OK # Assume success now, actual endpoint will set final
                log_data.error_message = None # Clear any prior error message
                # Log successful authentication before calling next
                await crud.create_api_usage_log(db, log_in=log_data)
                
                response = await call_next(request)
                # Note: To get the *actual* response status code from the endpoint,
                # you'd need to update the log *after* call_next. This adds complexity.
                # For MVP, logging the auth outcome is sufficient.
                return response

            except HTTPException as he:
                # This might catch exceptions from downstream if not careful with request.state usage
                # For now, assume it's an auth-related problem from our direct logic.
                log_data.response_status_code = he.status_code
                log_data.error_message = str(he.detail)
                await crud.create_api_usage_log(db, log_in=log_data)
                raise # Re-raise the HTTPException
            except Exception as e:
                logger.error(f"Unhandled exception in API Token Middleware: {e}")
                log_data.error_message = f"Internal server error: {str(e)}"
                log_data.response_status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
                # Ensure this log is captured before returning generic response
                try:
                    await crud.create_api_usage_log(db, log_in=log_data)
                except Exception as log_e:
                    logger.error(f"Failed to create usage log during exception handling: {log_e}")
                return Response("Internal Server Error", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
            # finally:
            #    await db.close() # AsyncSessionLocal context manager handles this 