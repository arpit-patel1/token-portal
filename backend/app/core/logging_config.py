import sys
from loguru import logger

def setup_logging():
    logger.remove()  # Remove default handler
    logger.add(sys.stderr, level="INFO")  # Console logger
    logger.add("logs/app.log", rotation="10 MB", retention="7 days", level="DEBUG", enqueue=True) # File logger

    # You can add more configurations here if needed
    # For example, structured logging with JSON:
    # logger.add("logs/app_{time}.log", format="{time} {level} {message}", serialize=True)

    logger.info("Logging configured")

# Call this function from your main application file to initialize logging 