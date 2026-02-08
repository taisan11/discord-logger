"""
Discord Message Logger with Textual TUI
========================================

This application provides a TUI for managing Discord message logging.
Features:
- Channel selection and browsing
- Message history retrieval with rate limit handling
- Real-time message capture
- SQLite3 storage of all message data
- Simple message viewer
"""

import asyncio
import logging
import os
from pathlib import Path

import dotenv

from app import create_app_class
from db import DiscordDB
from discord_client import DiscordMessageLogger

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('discord_logger.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for the Discord Logger TUI."""
    
    # Load environment variables
    dotenv.load_dotenv()
    TOKEN = os.getenv('TOKEN')
    
    if TOKEN is None:
        raise ValueError("No TOKEN found in environment variables. Please create a .env file with TOKEN=your_token")
    
    logger.info("Starting Discord Logger")
    
    # Initialize database
    db_path = Path("discord_messages.db")
    db = DiscordDB(str(db_path))
    logger.info(f"Database initialized at {db_path}")
    
    # Create Discord logger
    discord_logger = DiscordMessageLogger(TOKEN, db)
    
    # Create and run TUI application
    app = create_app_class(TOKEN, db, discord_logger)
    
    try:
        app.run()
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    finally:
        discord_logger.stop()
        db.close()
        logger.info("Discord Logger stopped")


if __name__ == "__main__":
    main()
