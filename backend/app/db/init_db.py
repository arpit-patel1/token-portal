import asyncio
import logging

from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.core.logging_config import setup_logging
from app.db.base_class import Base
# Import all models here to ensure they are registered with Base.metadata
# noinspection PyUnresolvedReferences
from app.db.models import User, AuthOtp, ApiToken, ApiUsageLog

# Initialize logging
setup_logging()
logger = logging.getLogger(__name__)

async def init_database() -> None:
    """
    Initializes the database by creating all tables.
    """
    logger.info("Initializing database...")
    logger.info(f"Database URL: {settings.DATABASE_URL}")

    # It's important to hide the password if it's in the URL string
    # Pydantic's PostgresDsn should already handle this for representation,
    # but being cautious with manual logging.
    # For production, consider more robust secret management and logging.
    
    engine = create_async_engine(str(settings.DATABASE_URL))

    async with engine.begin() as conn:
        logger.info("Dropping all existing tables (if any) before creation (for development)...")
        # In a production environment, you would use migrations (e.g., Alembic)
        # and wouldn't typically drop tables like this.
        # await conn.run_sync(Base.metadata.drop_all) # Comment out if you don't want to drop tables
        logger.info("Creating all tables...")
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Tables created successfully.")

    await engine.dispose()
    logger.info("Database initialization complete.")

async def main() -> None:
    try:
        await init_database()
    except Exception as e:
        logger.error(f"An error occurred during database initialization: {e}")
        # You might want to print the traceback in development
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main()) 