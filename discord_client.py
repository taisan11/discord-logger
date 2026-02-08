"""Discord client for message retrieval and storage with rate limit handling."""

import discord
import asyncio
from typing import Optional, Callable, Any
from db import DiscordDB
import logging

logger = logging.getLogger(__name__)


class DiscordMessageLogger:
    """Discord client with message logging capabilities."""

    # Rate limiting: Discord's limit is 100 messages per ~2 seconds
    REQUEST_DELAY = 0.5  # seconds between requests (conservative to avoid rate limiting)
    BATCH_SIZE = 100  # messages per request

    def __init__(self, token: str, db: DiscordDB):
        self.token = token
        self.db = db
        # self.intents = Intents.default()
        # self.intents.message_content = True
        # self.intents.guilds = True
        # self.intents.guild_messages = True
        self.client = discord.Client()
        self.is_syncing = False
        self.sync_progress_callback: Optional[Callable[[str, int, int], Any]] = None
        self._setup_handlers()

    def _setup_handlers(self):
        """Setup Discord event handlers."""
        @self.client.event
        async def on_ready():
            logger.info(f'Logged in as {self.client.user}')

        @self.client.event
        async def on_message(message: discord.Message):
            if message.author == self.client.user:
                return
            await self._save_message(message)

        @self.client.event
        async def on_message_edit(before: discord.Message, after: discord.Message):
            await self._save_message(after, edited=True)

        @self.client.event
        async def on_reaction_add(reaction: discord.Reaction, user: discord.User):
            if user == self.client.user:
                return
            self.db.add_reaction(reaction.message.id, str(reaction.emoji))

    async def _save_message(self, message: discord.Message, edited: bool = False):
        """Save a single message to database."""
        try:
            # Skip bot messages and system messages for now
            if message.author.bot and message.author != self.client.user:
                return

            raw_payload: Optional[dict[str, Any]] = None
            if hasattr(message, "to_dict"):
                try:
                    raw_payload = message.to_dict()
                except Exception:
                    raw_payload = None

            if raw_payload is None:
                raw_payload = {
                    "id": message.id,
                    "channel_id": message.channel.id,
                    "guild_id": message.guild.id if message.guild else None,
                    "author": {
                        "id": message.author.id,
                        "name": message.author.name,
                        "display_name": message.author.display_name,
                    },
                    "content": message.content,
                    "created_at": message.created_at.isoformat() if message.created_at else None,
                    "edited_at": message.edited_at.isoformat() if message.edited_at else None,
                    "attachments": [
                        {
                            "id": a.id,
                            "filename": a.filename,
                            "url": a.url,
                            "size": a.size,
                            "content_type": a.content_type,
                        }
                        for a in message.attachments
                    ],
                    "embeds": [e.to_dict() if hasattr(e, "to_dict") else {} for e in message.embeds],
                    "reactions": [
                        {"emoji": str(r.emoji), "count": r.count} for r in message.reactions
                    ],
                }

            # Save basic message
            self.db.add_message(
                message_id=message.id,
                channel_id=message.channel.id,
                user_id=message.author.id,
                username=message.author.display_name or message.author.name,
                content=message.content,
                created_at=message.created_at,
                avatar_url=str(message.author.avatar.url) if message.author.avatar else None,
                edited_at=message.edited_at if edited else None,
                message_type="edit" if edited else "normal",
                raw_json=raw_payload,
            )

            # Save attachments
            for attachment in message.attachments:
                self.db.add_attachment(
                    attachment_id=attachment.id,
                    message_id=message.id,
                    filename=attachment.filename,
                    url=attachment.url,
                    size=attachment.size,
                    content_type=attachment.content_type or "unknown",
                )

            # Save embeds
            for embed in message.embeds:
                self.db.add_embed(
                    message_id=message.id,
                    title=embed.title,
                    description=embed.description,
                    color=embed.color.value if embed.color else None,
                    url=embed.url,
                )

            # Save reactions
            for reaction in message.reactions:
                for _ in range(reaction.count):
                    self.db.add_reaction(message.id, str(reaction.emoji))

            logger.info(f"Saved message {message.id} from {message.author}")

        except Exception as e:
            logger.error(f"Error saving message {message.id}: {e}")

    def get_guilds(self) -> list[tuple[int, str]]:
        """Get list of accessible guilds (server ID, server name)."""
        guilds = []
        for guild in self.client.guilds:
            guilds.append((guild.id, guild.name))
        return guilds

    def get_guild_channels(self, guild_id: int) -> list[tuple[int, str]]:
        """Get list of text channels in a guild."""
        guild = self.client.get_guild(guild_id)
        if guild is None:
            logger.error(f"Guild {guild_id} not found")
            return []
        
        # Ensure the bot's Member object exists on the guild before checking permissions
        me = guild.me
        if me is None:
            logger.error(f"Bot member not found in guild {guild_id}")
            return []

        channels = []
        for channel in guild.text_channels:
            # Check if bot has permission to read this channel
            if channel.permissions_for(me).read_messages:
                channels.append((channel.id, channel.name))
                # Also save to database
                self.db.add_channel(channel.id, guild.id, channel.name)
        return channels

    def get_current_user_display(self) -> Optional[str]:
        """Get current user's display name if connected."""
        user = self.client.user
        if user is None:
            return None
        display_name = getattr(user, "display_name", None) or user.name
        return display_name


    async def sync_channel_history(self, channel_id: int, progress_callback: Optional[Callable[[str, int, int], Any]] = None):
        """Sync message history for a specific channel with rate limiting."""
        try:
            self.is_syncing = True
            self.sync_progress_callback = progress_callback

            channel = self.client.get_channel(channel_id)
            if channel is None:
                logger.error(f"Channel {channel_id} not found")
                return

            if not isinstance(channel, discord.TextChannel):
                logger.error(f"Channel {channel_id} is not a text channel")
                return

            # Add channel to database
            self.db.add_channel(
                channel_id=channel.id,
                guild_id=channel.guild.id,
                channel_name=channel.name,
            )

            # Set sync status to syncing
            self.db.set_sync_state(channel.id, None, "syncing")

            # Get the last saved message ID for this channel
            last_saved_id = self.db.get_last_message_id(channel.id)

            message_count = 0
            batch_count = 0
            last_message_id = None

            logger.info(f"Starting to sync channel {channel.name} (ID: {channel_id})")

            # Iterate through message history
            async for message in channel.history(limit=None, oldest_first=False):
                # Stop if we reach a message we've already saved
                if last_saved_id and message.id <= last_saved_id:
                    logger.info(f"Reached previously synced message {message.id}")
                    break

                await self._save_message(message)
                message_count += 1
                last_message_id = message.id

                # Rate limiting
                batch_count += 1
                if batch_count % self.BATCH_SIZE == 0:
                    if progress_callback:
                        total_count = self.db.get_message_count(channel.id)
                        progress_callback(f"Syncing {channel.name}", total_count, message_count)
                    await asyncio.sleep(self.REQUEST_DELAY * 5)  # Longer delay after batch

                await asyncio.sleep(self.REQUEST_DELAY)

            # Update sync state
            self.db.set_sync_state(channel.id, last_message_id, "completed")

            logger.info(f"Finished syncing channel {channel.name}: {message_count} messages processed")
            
            if progress_callback:
                total_count = self.db.get_message_count(channel.id)
                progress_callback(f"Completed {channel.name}", total_count, total_count)

        except Exception as e:
            logger.error(f"Error syncing channel {channel_id}: {e}")
            self.db.set_sync_state(channel_id, None, "error")
        finally:
            self.is_syncing = False

    async def start(self):
        """Start the Discord client."""
        await self.client.start(self.token)

    def stop(self):
        """Stop the Discord client."""
        try:
            asyncio.create_task(self.client.close())
        except RuntimeError:
            # No event loop running, ignore
            pass

    def get_client(self) -> discord.Client:
        """Get the underlying Discord client."""
        return self.client
