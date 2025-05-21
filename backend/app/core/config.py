from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Any
from pydantic import PostgresDsn, Field, computed_field # Updated import
from urllib.parse import quote_plus # To handle special characters in passwords
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "Token Portal MVP"
    API_V1_STR: str = "/api/v1"

    # Database connection (loaded from .env by Pydantic)
    DB_USER: str # Will be loaded from .env by Pydantic
    DB_PASSWORD: str = Field(default="pg_password")
    DB_HOST: str = Field(default="localhost")
    DB_PORT: str = Field(default="9972") 
    DB_NAME: str = Field(default="appdb")
    
    # DATABASE_URL is now a computed field
    @computed_field
    @property
    def DATABASE_URL(self) -> PostgresDsn:
        # This will be computed after DB_USER, DB_PASSWORD, etc., are loaded.
        # If DB_USER is not provided in .env, Pydantic will raise a ValidationError
        # for the missing DB_USER field before this computed field is accessed.
        password_encoded = quote_plus(self.DB_PASSWORD)
        url_str = f"postgresql+asyncpg://{self.DB_USER}:{password_encoded}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        return PostgresDsn(url_str)

    # Redis Connection URL
    REDIS_CONNECTION_URL: str = Field(default="redis://localhost:6379/0")

    # JWT
    JWT_SECRET_KEY: str = Field(default="your-secret-key")
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60 * 24 * 7) # 7 days

    # OTP
    OTP_EXPIRE_MINUTES: int = Field(default=5)

    # Email (for OTP)
    # Ensure you have set up an App Password for Gmail if using 2FA
    SMTP_TLS: bool = Field(default=True)
    SMTP_PORT: Optional[int] = Field(default=587)
    SMTP_HOST: Optional[str] = Field(default="smtp.gmail.com")
    SMTP_USER: Optional[str] = Field(default="your-email@gmail.com")
    SMTP_PASSWORD: Optional[str] = Field(default="your-gmail-app-password")
    EMAILS_FROM_EMAIL: Optional[str] = Field(default="your-email@gmail.com")
    EMAILS_FROM_NAME: Optional[str] = Field(default="Token Portal")

    # Frontend URL (for CORS)
    FRONTEND_URL: str = Field(default="http://localhost:3000")

    model_config = SettingsConfigDict(env_file="../../.env", extra="ignore")

settings = Settings() 