from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from typing import AsyncGenerator

from app.core.config import settings

# Convert the PostgresDsn object to a string for SQLAlchemy
DATABASE_URL_STR = str(settings.DATABASE_URL)

# Create an async engine
engine = create_async_engine(DATABASE_URL_STR, echo=True)

# Create a sessionmaker for async sessions
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency to get an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit() # Commit changes if no exceptions
        except Exception:
            await session.rollback() # Rollback in case of an error
            raise
        finally:
            await session.close() 