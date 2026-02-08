#!/usr/bin/env python3
"""
Test Discord client methods
"""

import sys
import logging
from discord_client import DiscordMessageLogger
from db import DiscordDB

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("Testing Discord client methods...")
try:
    db = DiscordDB(":memory:")
    
    # Create a mock Discord logger (won't actually connect)
    discord_logger = DiscordMessageLogger("mock_token", db)
    
    # Test method existence
    assert hasattr(discord_logger, 'get_guilds'), "get_guilds method not found"
    print("✓ get_guilds method exists")
    
    assert hasattr(discord_logger, 'get_guild_channels'), "get_guild_channels method not found"
    print("✓ get_guild_channels method exists")
    
    # Test that methods are callable
    assert callable(discord_logger.get_guilds), "get_guilds is not callable"
    print("✓ get_guilds is callable")
    
    assert callable(discord_logger.get_guild_channels), "get_guild_channels is not callable"
    print("✓ get_guild_channels is callable")
    
    # Test database add_channel
    db.add_channel(123456, 654321, "test-channel")
    channels = db.get_channels()
    assert len(channels) > 0, "No channels found after insertion"
    print("✓ add_channel works")
    
    print("\n" + "="*50)
    print("All method tests passed! ✓")
    print("="*50)
    
except Exception as e:
    print(f"✗ Test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\nNote: The Discord client will load guilds/channels")
print("  when you connect with a valid token.")
