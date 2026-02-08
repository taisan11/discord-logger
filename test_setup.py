#!/usr/bin/env python3
"""
Quick test script to verify the Discord Logger setup.
Tests database initialization and imports.
"""

import sys
from pathlib import Path

# Test imports
print("Testing imports...")
try:
    from db import DiscordDB
    print("✓ db.py imported successfully")
except Exception as e:
    print(f"✗ Failed to import db.py: {e}")
    sys.exit(1)

try:
    from discord_client import DiscordMessageLogger
    print("✓ discord_client.py imported successfully")
except Exception as e:
    print(f"✗ Failed to import discord_client.py: {e}")
    sys.exit(1)

try:
    from app import create_app_class
    print("✓ app.py imported successfully")
except Exception as e:
    print(f"✗ Failed to import app.py: {e}")
    sys.exit(1)

# Test database initialization
print("\nTesting database initialization...")
try:
    db = DiscordDB(":memory:")  # Use in-memory database for testing
    print("✓ Database created successfully")
    
    # Test adding a channel
    db.add_channel(123456, 654321, "test-channel")
    channels = db.get_channels()
    assert len(channels) > 0, "No channels found after insertion"
    assert channels[0]["channel_name"] == "test-channel"
    print("✓ Channel insertion/retrieval works")
    
    # Test message insertion
    from datetime import datetime
    db.add_message(
        message_id=111111,
        channel_id=123456,
        user_id=222222,
        username="TestUser",
        content="Test message",
        created_at=datetime.now(),
        avatar_url="https://example.com/avatar.png",
    )
    messages = db.get_messages(123456)
    assert len(messages) > 0, "No messages found after insertion"
    assert messages[0]["content"] == "Test message"
    print("✓ Message insertion/retrieval works")
    
    # Test message count
    count = db.get_message_count(123456)
    assert count == 1, f"Expected 1 message, got {count}"
    print("✓ Message count works")
    
    # Test sync state
    db.set_sync_state(123456, 111111, "completed")
    state = db.get_sync_state(123456)
    assert state is not None, "Sync state not found"
    assert state["sync_status"] == "completed"
    print("✓ Sync state works")
    
    db.close()
    
except Exception as e:
    print(f"✗ Database test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*50)
print("All tests passed! ✓")
print("="*50)
print("\nSetup instructions:")
print("1. Create a .env file with your Discord token:")
print("   TOKEN=your_token_here")
print("\n2. Run the application:")
print("   python main.py")
print("\nNote: You need a valid Discord token to run the full application.")
