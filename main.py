"""
Discord Message Logger entry point.

Supports the default Textual TUI and a lightweight CLI mode that only performs
history sync plus real-time message saving.
"""

import argparse
import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import dotenv

from db import DiscordDB
from discord_client import DiscordMessageLogger, HistoryTarget

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("discord_logger.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path("discord_messages.db")
CLI_PROGRESS_INTERVAL = 5.0


@dataclass(slots=True)
class CliSyncState:
    """Shared state for CLI history sync progress."""

    total_targets: int = 0
    completed_targets: int = 0
    current_target: str = ""
    current_status: str = "Waiting"
    current_messages: int = 0

    def render(self) -> str:
        """Render a single progress line."""
        if self.total_targets <= 0:
            return "[CLI] No syncable history targets found"

        percent = int((self.completed_targets / self.total_targets) * 100)
        detail = self.current_target or "No active target"
        if self.current_messages:
            detail = f"{detail} ({self.current_messages} messages saved)"
        return f"[CLI] {self.completed_targets}/{self.total_targets} ({percent}%) {self.current_status}: {detail}"


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description="Discord message logger")
    parser.add_argument("--cli", action="store_true", help="Run lightweight CLI mode")
    parser.add_argument(
        "--ui-kakodouki",
        action="store_true",
        help="Print periodic history-sync progress while running in CLI mode",
    )
    return parser


def load_token() -> str:
    """Load the Discord token from the environment."""
    dotenv.load_dotenv()
    token = os.getenv("TOKEN")
    if token is None:
        raise ValueError("No TOKEN found in environment variables. Please create a .env file with TOKEN=your_token")
    return token


def create_database() -> DiscordDB:
    """Create the SQLite database handler."""
    db = DiscordDB(str(DEFAULT_DB_PATH))
    logger.info(f"Database initialized at {DEFAULT_DB_PATH}")
    return db


async def wait_for_client_ready(discord_logger: DiscordMessageLogger, start_task: asyncio.Task[None], timeout: float = 30.0) -> None:
    """Wait for the Discord client to become ready or fail early."""
    deadline = asyncio.get_running_loop().time() + timeout
    client = discord_logger.get_client()

    while True:
        if start_task.done():
            await start_task
        if client.is_ready():
            return
        if asyncio.get_running_loop().time() >= deadline:
            raise TimeoutError("Timed out waiting for Discord client to become ready")
        await asyncio.sleep(0.2)


async def collect_history_targets(discord_logger: DiscordMessageLogger) -> list[HistoryTarget]:
    """Collect all syncable guild channel and DM targets."""
    return await discord_logger.get_history_targets()


async def run_cli_history_sync(discord_logger: DiscordMessageLogger, show_progress: bool) -> None:
    """Sync all history targets once before switching to real-time capture."""
    targets = await collect_history_targets(discord_logger)
    state = CliSyncState(total_targets=len(targets))
    stop_reporting = asyncio.Event()
    reporter_task: asyncio.Task[None] | None = None

    async def progress_reporter() -> None:
        while not stop_reporting.is_set():
            print(state.render(), flush=True)
            try:
                await asyncio.wait_for(stop_reporting.wait(), timeout=CLI_PROGRESS_INTERVAL)
            except asyncio.TimeoutError:
                continue

    if show_progress:
        reporter_task = asyncio.create_task(progress_reporter())

    try:
        if not targets:
            logger.info("No syncable history targets found")
            return

        logger.info(f"Starting CLI history sync for {len(targets)} targets")
        for index, target in enumerate(targets, start=1):
            state.current_target = target.label
            state.current_status = f"Syncing {index}/{len(targets)}"
            state.current_messages = 0
            logger.info(f"Syncing history for {target.label}")

            def progress_callback(status: str, _total: int, current: int) -> None:
                state.current_status = status
                state.current_messages = current

            if target.is_dm:
                await discord_logger.sync_dm_history(target.channel_id, progress_callback=progress_callback)
            else:
                await discord_logger.sync_channel_history(target.channel_id, progress_callback=progress_callback)

            state.completed_targets = index
            state.current_status = f"Completed {index}/{len(targets)}"
            logger.info(f"Completed history sync for {target.label}")

        logger.info("History sync complete; real-time message saving remains active")
    finally:
        stop_reporting.set()
        if reporter_task is not None:
            await reporter_task


async def run_cli(discord_logger: DiscordMessageLogger, show_progress: bool) -> None:
    """Run the lightweight CLI mode."""
    logger.info("Starting Discord Logger in CLI mode")
    start_task = asyncio.create_task(discord_logger.start())

    try:
        await wait_for_client_ready(discord_logger, start_task)
        logger.info("Discord client connected")

        await run_cli_history_sync(discord_logger, show_progress=show_progress)

        logger.info("CLI mode is now waiting for real-time message events")
        await start_task
    finally:
        discord_logger.stop()


def run_tui(token: str, db: DiscordDB, discord_logger: DiscordMessageLogger) -> None:
    """Run the Textual TUI mode."""
    from app import create_app_class

    app = create_app_class(token, db, discord_logger)

    try:
        app.run()
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")


def main() -> None:
    """Main entry point."""
    parser = build_parser()
    args = parser.parse_args()
    token = load_token()
    db = create_database()
    discord_logger = DiscordMessageLogger(token, db)

    try:
        if args.cli:
            asyncio.run(run_cli(discord_logger, show_progress=args.ui_kakodouki))
        else:
            run_tui(token, db, discord_logger)
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    finally:
        discord_logger.stop()
        db.close()
        logger.info("Discord Logger stopped")


if __name__ == "__main__":
    main()
