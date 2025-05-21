from sqlalchemy import Column, Integer, String, Boolean, DateTime, func, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.db.base_class import Base # Adjusted import path

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    role = Column(String, nullable=False, default="user") # e.g., "user", "admin"
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    api_tokens = relationship("ApiToken", back_populates="user", cascade="all, delete-orphan")
    # auth_otps = relationship("AuthOtp", back_populates="user", cascade="all, delete-orphan") # Removed
    # Direct relationship to usage_logs might be added later if needed for user-centric views not via token
    # usage_logs = relationship("ApiUsageLog", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}')>"

# class AuthOtp(Base):
#     __tablename__ = "auth_otp"
# 
#     id = Column(Integer, primary_key=True, index=True)
#     otp_hash = Column(String, nullable=False)
#     expires_at = Column(DateTime, nullable=False)
#     is_used = Column(Boolean, default=False, nullable=False)
#     created_at = Column(DateTime, default=func.now(), nullable=False)
#     updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
# 
#     user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
#     user = relationship("User", back_populates="auth_otps")
# 
#     def __repr__(self):
#         return f"<AuthOtp(id={self.id}, user_id={self.user_id}, is_used={self.is_used})>"

class ApiToken(Base):
    __tablename__ = "api_tokens"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True)
    hashed_token = Column(String, nullable=False, unique=True, index=True) # Store hash of the token
    token_preview = Column(String, nullable=False) # e.g., "sk_live_AbC1" first 8-10 chars, or prefix + last 4
    expires_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    is_revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    user = relationship("User", back_populates="api_tokens")

    usage_logs = relationship("ApiUsageLog", back_populates="api_token", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ApiToken(id={self.id}, name='{self.name}', user_id={self.user_id}, is_revoked={self.is_revoked})>"

class ApiUsageLog(Base):
    __tablename__ = "api_usage_logs"

    id = Column(Integer, primary_key=True, index=True)
    request_timestamp = Column(DateTime, default=func.now(), nullable=False)
    request_method = Column(String, nullable=False)
    request_path = Column(String, nullable=False)
    response_status_code = Column(Integer, nullable=False)
    client_ip_address = Column(String, nullable=True)
    user_agent = Column(Text, nullable=True) # Can be long
    error_message = Column(Text, nullable=True) # For storing auth errors or other issues

    api_token_id = Column(Integer, ForeignKey("api_tokens.id"), nullable=True, index=True)
    api_token = relationship("ApiToken", back_populates="usage_logs")

    # user_id is directly on the log for easier querying, even if token is invalid or not present.
    # If api_token is valid, this user_id should match api_token.user_id.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    # If you want a direct relationship from ApiUsageLog to User (many-to-one):
    # user = relationship("User", back_populates="usage_logs") # This would require usage_logs on User model

    def __repr__(self):
        return f"<ApiUsageLog(id={self.id}, token_id={self.api_token_id}, path='{self.request_path}', status={self.response_status_code})>"

# Future models (ApiToken, ApiUsageLog) will be added here