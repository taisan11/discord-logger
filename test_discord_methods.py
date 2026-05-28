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
    
    assert hasattr(discord_logger, 'get_direct_messages'), "get_direct_messages method not found"
    print("✓ get_direct_messages method exists")
    
    assert hasattr(discord_logger, 'sync_dm_history'), "sync_dm_history method not found"
    print("✓ sync_dm_history method exists")

    assert hasattr(discord_logger, 'get_history_targets'), "get_history_targets method not found"
    print("✓ get_history_targets method exists")
    
    # Test that methods are callable
    assert callable(discord_logger.get_guilds), "get_guilds is not callable"
    print("✓ get_guilds is callable")
    
    assert callable(discord_logger.get_guild_channels), "get_guild_channels is not callable"
    print("✓ get_guild_channels is callable")
    
    assert callable(discord_logger.get_direct_messages), "get_direct_messages is not callable"
    print("✓ get_direct_messages is callable")
    
    assert callable(discord_logger.sync_dm_history), "sync_dm_history is not callable"
    print("✓ sync_dm_history is callable")

    assert callable(discord_logger.get_history_targets), "get_history_targets is not callable"
    print("✓ get_history_targets is callable")
    
    # Test database add_channel
    db.add_channel(123456, 654321, "test-channel")
    channels = db.get_channels()
    assert len(channels) > 0, "No channels found after insertion"
    print("✓ add_channel works")
    
    # Test database get_channel
    channel_info = db.get_channel(123456)
    assert channel_info is not None, "get_channel returned None"
    assert channel_info["channel_id"] == 123456, "Channel ID mismatch"
    print("✓ get_channel works")
    
    # Test DM channel (guild_id = None)
    db.add_channel(789012, None, "DM with test-user", channel_type="dm")
    dm_info = db.get_channel(789012)
    assert dm_info is not None, "DM channel not found"
    assert dm_info["guild_id"] is None, "DM channel should have guild_id = None"
    assert dm_info["channel_type"] == "dm", "Channel type should be 'dm'"
    print("✓ DM channel storage works")
    
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
