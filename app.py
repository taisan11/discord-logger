"""Main Textual TUI application for Discord Logger with guild/channel selection."""

from textual.app import ComposeResult
from textual._on import on
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Header, Footer, Static, Button, ListItem, ListView, Label
from textual.reactive import reactive
from textual.binding import Binding
import asyncio
import logging
from typing import Optional
from db import DiscordDB
from discord_client import DiscordMessageLogger

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GuildListItem(ListItem):
    """Custom list item for guilds/servers."""

    def __init__(self, guild_id: int, guild_name: str):
        super().__init__()
        self.guild_id = guild_id
        self.guild_name = guild_name

    def render(self) -> str:
        return f"🏢 {self.guild_name}"


class ChannelListItem(ListItem):
    """Custom list item for channels."""

    def __init__(self, channel_id: int, channel_name: str, guild_id: int, message_count: int):
        super().__init__()
        self.channel_id = channel_id
        self.channel_name = channel_name
        self.guild_id = guild_id
        self.message_count = message_count

    def render(self) -> str:
        return f"#{self.channel_name} ({self.message_count} messages)"


class DMListItem(ListItem):
    """Custom list item for direct messages."""

    def __init__(self, channel_id: int, recipient_name: str, recipient_id: int, message_count: int):
        super().__init__()
        self.channel_id = channel_id
        self.recipient_name = recipient_name
        self.recipient_id = recipient_id
        self.message_count = message_count
        self.is_dm = True

    def render(self) -> str:
        return f"💬 {self.recipient_name} ({self.message_count} messages)"


class SyncStatusPanel(Static):
    """Panel showing sync status and progress."""

    status_text = reactive("Ready")
    progress_value = reactive(0)

    def render(self) -> str:
        progress_bar = "█" * self.progress_value + "░" * (50 - self.progress_value)
        return f"""
[bold cyan]Sync Status[/bold cyan]
{self.status_text}
[{progress_bar}] {self.progress_value * 2}%
"""


class MessageViewerWidget(Static):
    """Widget for displaying messages from selected channel."""

    current_channel_id: Optional[int] = None
    current_offset: int = 0
    db: Optional[DiscordDB] = None
    MESSAGES_PER_PAGE = 15

    def set_channel(self, channel_id: int):
        """Set the current channel to view."""
        self.current_channel_id = channel_id
        self.current_offset = 0
        self.refresh()

    def render(self) -> str:
        if not self.current_channel_id:
            return "[dim]No channel selected[/dim]"

        if not self.db:
            return "[dim]Database not initialized[/dim]"

        messages = self.db.get_messages(self.current_channel_id, limit=self.MESSAGES_PER_PAGE, offset=self.current_offset)

        if not messages:
            return "[dim]No messages to display[/dim]"

        output = ["[bold cyan]Messages[/bold cyan]", ""]
        for msg in reversed(messages):
            timestamp = msg["created_at"][:19]
            username = msg["username"]
            content = msg["content"]
            
            if msg["edited_at"]:
                edit_mark = " [yellow](edited)[/yellow]"
            else:
                edit_mark = ""
            
            lines = content.split("\n")
            short_content = lines[0][:80]
            if len(lines) > 1 or len(lines[0]) > 80:
                short_content += "..."
            
            output.append(f"[cyan]{username}[/cyan] {timestamp}{edit_mark}")
            output.append(f"  {short_content}")
            output.append("")

        return "\n".join(output)


class ControlPanel(Static):
    """Control panel for sync and navigation."""

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Button("[S]ync History", id="btn-sync", variant="primary")
            yield Button("[V]iew", id="btn-view", variant="success")
            yield Button("[R]efresh", id="btn-refresh", variant="warning")
            yield Button("E[x]it", id="btn-exit", variant="error")


def create_app_class(token: str, db: DiscordDB, discord_logger: DiscordMessageLogger):
    """Factory function to create a Textual app class."""
    from textual.app import ComposeResult, App

    class MainApp(App):
        """Main Textual application."""

        BINDINGS = [
            Binding("s", "sync", "Sync"),
            Binding("v", "view", "View"),
            Binding("r", "refresh", "Refresh"),
            Binding("q", "quit", "Quit"),
        ]

        CSS = """
        Screen {
            layout: vertical;
            background: $surface;
        }

        #main-container {
            width: 1fr;
            height: 1fr;
        }

        #content {
            width: 1fr;
            height: 1fr;
        }

        #left-panel {
            width: 30;
            height: 1fr;
            border: solid $primary;
        }

        #guild-panel {
            height: 8;
            border: solid $accent;
        }

        #dm-panel {
            height: 6;
            border: solid $accent;
        }

        #channel-panel {
            height: 1fr;
            border: solid $accent;
        }

        #guild-list {
            width: 1fr;
            height: 1fr;
        }

        #dm-list {
            width: 1fr;
            height: 1fr;
        }

        #channel-list {
            width: 1fr;
            height: 1fr;
        }

        #right-panel {
            width: 1fr;
            height: 1fr;
            border: solid $secondary;
        }

        #status-panel {
            width: 1fr;
            height: 8;
            border: solid $warning;
        }

        #message-viewer {
            width: 1fr;
            height: 1fr;
            border: solid $success;
            overflow: auto;
        }

        #controls {
            width: 1fr;
            height: 3;
            border: solid $secondary;
        }

        Button {
            width: 1fr;
        }
        """

        selected_guild: Optional[int] = None
        selected_channel: Optional[int] = None

        def compose(self) -> ComposeResult:
            """Compose the UI layout."""
            yield Header()

            with Vertical(id="main-container"):
                yield Label("[bold]Discord Message Logger[/bold]", id="title")

                with Horizontal(id="content"):
                    # Left panel: Guild, DM, and Channel selection
                    with Vertical(id="left-panel"):
                        with Vertical(id="guild-panel"):
                            yield Label("[bold cyan]Servers[/bold cyan]")
                            yield ListView(id="guild-list")
                        
                        with Vertical(id="dm-panel"):
                            yield Label("[bold cyan]Direct Messages[/bold cyan]")
                            yield ListView(id="dm-list")
                        
                        with Vertical(id="channel-panel"):
                            yield Label("[bold cyan]Channels[/bold cyan]")
                            yield ListView(id="channel-list")

                    # Right panel: Message viewer and status
                    with Vertical(id="right-panel"):
                        yield SyncStatusPanel(id="status-panel")
                        with ScrollableContainer(id="message-container"):
                            yield MessageViewerWidget(id="message-viewer")

                # Bottom: Controls
                yield ControlPanel(id="controls")

            yield Footer()

        def on_mount(self) -> None:
            """When app is mounted."""
            # Set up database reference in message viewer
            message_viewer = self.query_one("#message-viewer", MessageViewerWidget)
            message_viewer.db = db

            # Start Discord client
            def start_discord():
                async def _start():
                    try:
                        await discord_logger.start()
                    except Exception as e:
                        logger.error(f"Error starting Discord client: {e}")
                
                asyncio.create_task(_start())
            
            self.call_later(start_discord)
            
            # Load guilds after Discord connects
            async def load_guilds_later():
                await asyncio.sleep(2)
                user_name = discord_logger.get_current_user_display()
                if user_name:
                    title = self.query_one("#title", Label)
                    title.update(f"[bold]Discord Message Logger[/bold] ({user_name})")
                self.action_refresh()
            
            self.call_later(load_guilds_later)

        def on_list_view_selected(self, message: ListView.Selected) -> None:
            """Handle list selection."""
            item = message.item
            
            if isinstance(item, GuildListItem):
                self.selected_guild = item.guild_id
                self.notify(f"Selected server: {item.guild_name}")
                asyncio.create_task(self._load_channels_for_guild(item.guild_id))
            
            elif isinstance(item, DMListItem):
                self.selected_channel = item.channel_id
                message_viewer = self.query_one("#message-viewer", MessageViewerWidget)
                message_viewer.set_channel(item.channel_id)
                self.notify(f"Selected DM: {item.recipient_name}")
            
            elif isinstance(item, ChannelListItem):
                self.selected_channel = item.channel_id
                message_viewer = self.query_one("#message-viewer", MessageViewerWidget)
                message_viewer.set_channel(item.channel_id)
                self.notify(f"Selected channel: #{item.channel_name}")

        async def _load_channels_for_guild(self, guild_id: int) -> None:
            """Load channels for a specific guild."""
            try:
                channels = await discord_logger.get_guild_channels(guild_id)
                channel_list = self.query_one("#channel-list", ListView)
                channel_list.clear()
                message_counts = db.get_message_counts([channel_id for channel_id, _ in channels])
                
                for channel_id, channel_name in channels:
                    item = ChannelListItem(
                        channel_id=channel_id,
                        channel_name=channel_name,
                        guild_id=guild_id,
                        message_count=message_counts.get(channel_id, 0),
                    )
                    channel_list.append(item)
                
                self.notify(f"Loaded {len(channels)} channels")
            except Exception as e:
                logger.error(f"Error loading channels: {e}")
                self.notify(f"Error loading channels: {e}", severity="error")

        @on(Button.Pressed, "#btn-sync")
        def action_sync(self) -> None:
            """Sync history action."""
            if not self.selected_channel:
                self.notify("Please select a channel or DM first", severity="warning")
                return

            if discord_logger.is_syncing:
                self.notify("Already syncing", severity="warning")
                return

            channel_id = self.selected_channel
            assert channel_id is not None

            status_panel = self.query_one("#status-panel", SyncStatusPanel)

            def progress_callback(status: str, total: int, current: int):
                """Update progress."""
                if total > 0:
                    progress = int((current / total) * 50)
                    status_panel.progress_value = min(progress, 50)
                status_panel.status_text = f"{status}: {current}/{total}"

            async def do_sync():
                # Check if this is a DM channel by querying the database
                channel_info = db.get_channel(channel_id)
                is_dm = channel_info and channel_info.get("guild_id") is None and channel_info.get("channel_type") == "dm"
                
                if is_dm:
                    await discord_logger.sync_dm_history(
                        channel_id,
                        progress_callback=progress_callback
                    )
                else:
                    await discord_logger.sync_channel_history(
                        channel_id,
                        progress_callback=progress_callback
                    )
                message_viewer = self.query_one("#message-viewer", MessageViewerWidget)
                message_viewer.refresh()

            asyncio.create_task(do_sync())

        @on(Button.Pressed, "#btn-view")
        def action_view(self) -> None:
            """View action."""
            if not self.selected_channel:
                self.notify("Please select a channel first", severity="warning")
                return
            message_viewer = self.query_one("#message-viewer", MessageViewerWidget)
            message_viewer.refresh()
            self.notify("Messages refreshed")

        @on(Button.Pressed, "#btn-refresh")
        def action_refresh(self) -> None:
            """Refresh action - reload guilds, DMs, and channels."""
            try:
                # Load guilds
                guilds = discord_logger.get_guilds()
                
                if not guilds:
                    self.notify("No servers found. Make sure Discord client is connected.", severity="warning")
                
                guild_list = self.query_one("#guild-list", ListView)
                guild_list.clear()
                
                for guild_id, guild_name in guilds:
                    item = GuildListItem(guild_id=guild_id, guild_name=guild_name)
                    guild_list.append(item)
                
                guild_count = len(guilds)
                
                # Load DMs
                dms = discord_logger.get_direct_messages()
                dm_list = self.query_one("#dm-list", ListView)
                dm_list.clear()
                dm_message_counts = db.get_message_counts([channel_id for channel_id, _, _ in dms])
                
                for channel_id, recipient_name, recipient_id in dms:
                    item = DMListItem(
                        channel_id=channel_id,
                        recipient_name=recipient_name,
                        recipient_id=recipient_id,
                        message_count=dm_message_counts.get(channel_id, 0),
                    )
                    dm_list.append(item)
                
                dm_count = len(dms)
                
                self.notify(f"Loaded {guild_count} servers and {dm_count} DMs")
                
                # Auto-select first guild
                if guilds:
                    first_guild_id, _ = guilds[0]
                    self.selected_guild = first_guild_id
                    asyncio.create_task(self._load_channels_for_guild(first_guild_id))
            
            except Exception as e:
                logger.error(f"Error refreshing: {e}")
                self.notify(f"Error refreshing: {e}", severity="error")

        @on(Button.Pressed, "#btn-exit")
        def action_exit(self) -> None:
            """Exit action."""
            self.exit()

    return MainApp()
