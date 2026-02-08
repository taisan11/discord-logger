"""SQLite3 database management for Discord messages storage."""

import sqlite3
import json
import zlib
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime


class DiscordDB:
    """Database handler for Discord messages and metadata."""

    def __init__(self, db_path: str = "discord_messages.db"):
        self.db_path = Path(db_path)
        self.connection: Optional[sqlite3.Connection] = None
        self.init_db()

    def connect(self):
        """Create database connection."""
        if self.connection is None:
            self.connection = sqlite3.connect(str(self.db_path))
            self.connection.row_factory = sqlite3.Row

    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None

    def init_db(self):
        """Initialize database schema."""
        self.connect()
        assert self.connection is not None
        cursor = self.connection.cursor()

        # Channels table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                channel_id INTEGER PRIMARY KEY,
                guild_id INTEGER NOT NULL,
                channel_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                message_id INTEGER PRIMARY KEY,
                channel_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                avatar_url TEXT,
                content TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                edited_at TIMESTAMP,
                message_type TEXT DEFAULT 'normal',
                raw_json BLOB,
                FOREIGN KEY (channel_id) REFERENCES channels (channel_id)
            )
        """)

        # Attachments table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attachments (
                attachment_id INTEGER PRIMARY KEY,
                message_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                url TEXT NOT NULL,
                size INTEGER,
                content_type TEXT,
                FOREIGN KEY (message_id) REFERENCES messages (message_id)
            )
        """)

        # Embeds table (for rich message content)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS embeds (
                embed_id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL,
                title TEXT,
                description TEXT,
                color INTEGER,
                url TEXT,
                timestamp TIMESTAMP,
                footer_text TEXT,
                FOREIGN KEY (message_id) REFERENCES messages (message_id)
            )
        """)

        # Reactions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reactions (
                reaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL,
                emoji TEXT NOT NULL,
                count INTEGER DEFAULT 1,
                FOREIGN KEY (message_id) REFERENCES messages (message_id),
                UNIQUE(message_id, emoji)
            )
        """)

        # Sync state table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_state (
                channel_id INTEGER PRIMARY KEY,
                last_message_id INTEGER,
                last_sync_at TIMESTAMP,
                sync_status TEXT DEFAULT 'pending',
                FOREIGN KEY (channel_id) REFERENCES channels (channel_id)
            )
        """)

        self.connection.commit()

        # Ensure schema upgrades for existing databases
        self._ensure_column("messages", "raw_json", "BLOB")

    def _ensure_column(self, table: str, column: str, column_type: str) -> None:
        """Ensure a column exists in a table (simple migration)."""
        assert self.connection is not None
        cursor = self.connection.cursor()
        cursor.execute(f"PRAGMA table_info({table})")
        columns = {row[1] for row in cursor.fetchall()}
        if column not in columns:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")
            self.connection.commit()

    def _compress_json(self, payload: Any) -> Optional[bytes]:
        """Compress a JSON-serializable payload to bytes."""
        if payload is None:
            return None
        raw_text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        return zlib.compress(raw_text.encode("utf-8"))

    def _decompress_json(self, payload: Optional[bytes]) -> Optional[Any]:
        """Decompress bytes to JSON payload."""
        if payload is None:
            return None
        try:
            raw_text = zlib.decompress(payload).decode("utf-8")
            return json.loads(raw_text)
        except Exception:
            return None

    def add_channel(self, channel_id: int, guild_id: int, channel_name: str):
        """Add or update a channel."""
        self.connect()
        assert self.connection is not None
        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO channels (channel_id, guild_id, channel_name, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """, (channel_id, guild_id, channel_name))
        self.connection.commit()

    def get_channels(self) -> List[Dict[str, Any]]:
        """Get all tracked channels."""
        self.connect()
        assert self.connection is not None
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM channels ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]

    def add_message(
        self,
        message_id: int,
        channel_id: int,
        user_id: int,
        username: str,
        content: str,
        created_at: datetime,
        avatar_url: Optional[str] = None,
        edited_at: Optional[datetime] = None,
        message_type: str = "normal",
        raw_json: Optional[Any] = None,
    ):
        """Add a message to database."""
        self.connect()
        assert self.connection is not None
        cursor = self.connection.cursor()
        raw_blob = self._compress_json(raw_json)
        cursor.execute("""
            INSERT OR REPLACE INTO messages 
            (message_id, channel_id, user_id, username, avatar_url, content, created_at, edited_at, message_type, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (message_id, channel_id, user_id, username, avatar_url, content, created_at, edited_at, message_type, raw_blob))
        self.connection.commit()

    def get_messages(self, channel_id: int, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get messages from a channel."""
        self.connect()
        assert self.connection is not None
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT * FROM messages 
            WHERE channel_id = ? 
            ORDER BY created_at DESC 
            LIMIT ? OFFSET ?
        """, (channel_id, limit, offset))
        return [dict(row) for row in cursor.fetchall()]

    def get_message_count(self, channel_id: int) -> int:
        """Get total message count for a channel."""
        self.connect()
        assert self.connection is not None
        cursor = self.connection.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM messages WHERE channel_id = ?", (channel_id,))
        return cursor.fetchone()["count"]

    def export_raw_messages_json(
        self,
        output_path: str,
        channel_id: Optional[int] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> int:
        """Export raw JSON messages to a file as an array."""
        self.connect()
        assert self.connection is not None
        cursor = self.connection.cursor()

        query = "SELECT message_id, channel_id, raw_json FROM messages"
        params: List[Any] = []
        if channel_id is not None:
            query += " WHERE channel_id = ?"
            params.append(channel_id)
        query += " ORDER BY created_at DESC"
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        exported: List[Dict[str, Any]] = []
        for row in rows:
            raw_payload = self._decompress_json(row["raw_json"])
            if raw_payload is None:
                raw_payload = {
                    "message_id": row["message_id"],
                    "channel_id": row["channel_id"],
                }
            exported.append(raw_payload)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(exported, f, ensure_ascii=False)

        return len(exported)

    def add_attachment(self, attachment_id: int, message_id: int, filename: str, url: str, size: int, content_type: str):
        """Add attachment metadata."""
        self.connect()
        assert self.connection is not None
        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO attachments (attachment_id, message_id, filename, url, size, content_type)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (attachment_id, message_id, filename, url, size, content_type))
        self.connection.commit()

    def add_embed(self, message_id: int, title: Optional[str], description: Optional[str], color: Optional[int], url: Optional[str]):
        """Add embed metadata."""
        self.connect()
        assert self.connection is not None
        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT INTO embeds (message_id, title, description, color, url)
            VALUES (?, ?, ?, ?, ?)
        """, (message_id, title, description, color, url))
        self.connection.commit()

    def add_reaction(self, message_id: int, emoji: str):
        """Add or update reaction count."""
        self.connect()
        assert self.connection is not None
        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT INTO reactions (message_id, emoji, count)
            VALUES (?, ?, 1)
            ON CONFLICT(message_id, emoji) DO UPDATE SET count = count + 1
        """, (message_id, emoji))
        self.connection.commit()

    def set_sync_state(self, channel_id: int, last_message_id: Optional[int], status: str = "syncing"):
        """Update channel sync state."""
        self.connect()
        assert self.connection is not None
        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO sync_state (channel_id, last_message_id, last_sync_at, sync_status)
            VALUES (?, ?, CURRENT_TIMESTAMP, ?)
        """, (channel_id, last_message_id, status))
        self.connection.commit()

    def get_sync_state(self, channel_id: int) -> Optional[Dict[str, Any]]:
        """Get channel sync state."""
        self.connect()
        assert self.connection is not None
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM sync_state WHERE channel_id = ?", (channel_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_last_message_id(self, channel_id: int) -> Optional[int]:
        """Get last saved message ID for pagination."""
        self.connect()
        assert self.connection is not None
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT message_id FROM messages 
            WHERE channel_id = ? 
            ORDER BY message_id DESC 
            LIMIT 1
        """, (channel_id,))
        row = cursor.fetchone()
        return row["message_id"] if row else None
