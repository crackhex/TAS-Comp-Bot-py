# src/main.py

import asyncio
import logging
import os
import sys
import traceback

import discord
from discord.ext import commands
from dotenv import load_dotenv

from application.parsers.null_parser import NullParser
from application.parsers.rkg_parser import RkgParser
from application.parsers.rksys_parser import RksysParser
from application.services.submission_services.service_factory import build_submission_service
from infrastructure.db import init_db
from infrastructure.repositories.sqlalchemy_task_repo import SqlAlchemyTaskRepository
from infrastructure.repositories.sqlalchemy_user_repo import SqlAlchemyUserRepository
from infrastructure.repositories.sqlalchemy_submission_repo import SqlAlchemySubmissionRepository
from infrastructure.repositories.sqlalchemy_team_repo import SqlAlchemyTeamRepository
from infrastructure.repositories.sqlalchemy_config_repo import SqlAlchemyConfigRepository
from infrastructure.repositories.sqlalchemy_speedtask_repo import SqlAlchemySpeedTaskRepository

from application.parsers.file_parser import FileParser
from application.services.task_manager import TaskManager
from application.services.user_service import UserService
from application.services.team_service import TeamService
from application.services.config_service import ConfigService
from application.services.speed_task_service import SpeedTaskService


# ────────────────────────── ENV / TOKEN ────────────────────────────
load_dotenv()
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    print("❌TOKEN not defined in .env", file=sys.stderr)
    sys.exit(1)

# ────────────────────────── BOT ACTIVITY ───────────────────────────
activity = discord.Game(name="Dolphin Emulator")

# ────────────────────────── EXTENSIONS  ────────────────────────────
commands_ext = [
    "adapters.discord.commands.admin.config_commands",
    "adapters.discord.commands.admin.error_test_commands",
    "adapters.discord.commands.admin.sync_command",
    "adapters.discord.commands.admin.say_command",
    "adapters.discord.commands.comp.collab_command",
    "adapters.discord.commands.comp.info_command",
    "adapters.discord.commands.comp.leave_team_command",
    "adapters.discord.commands.comp.name_commands",
    "adapters.discord.commands.comp.request_task_command",
    "adapters.discord.commands.comp.stop_timer_command",
    "adapters.discord.commands.comp.teams_command",
    "adapters.discord.commands.fun.8balls_command",
    "adapters.discord.commands.fun.slots_command",
    "adapters.discord.commands.help_command",
    "adapters.discord.commands.host.delete_submission_command",
    "adapters.discord.commands.host.dm_command",
    "adapters.discord.commands.host.edit_submission_command",
    "adapters.discord.commands.host.end_task_command",
    "adapters.discord.commands.host.get_results_command",
    "adapters.discord.commands.host.get_submissions_command",
    "adapters.discord.commands.host.host_dissolve_command",
    "adapters.discord.commands.host.host_kick_command",
    "adapters.discord.commands.host.set_deadline_command",
    "adapters.discord.commands.host.set_file_command",
    "adapters.discord.commands.host.speed_task_config_commands",
    "adapters.discord.commands.host.start_task_command",
    "adapters.discord.commands.host.submit_command",
]

events_ext = [
    "adapters.discord.events.dm_logger",
    "adapters.discord.events.dm_submission_listener",
    "adapters.discord.events.discord_errors",
    "adapters.discord.events.deadline_watcher",
    "adapters.discord.events.speed_task_reminders",
    "adapters.discord.events.speed_task_release"
]

# ────────────────────────── BOT CLASS ──────────────────────────
class Bot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="$",
            intents=discord.Intents.all(),
            description="MKWii TAS Competition Bot",
            activity=activity,
        )

    async def setup_hook(self):
        # load commands
        for ext in commands_ext:
            try:
                await self.load_extension(ext)
            except Exception:
                print(f"Loading fail {ext}", file=sys.stderr)
                traceback.print_exc()

        # load listeners and events
        for ext in events_ext:
            try:
                await self.load_extension(ext)
            except Exception:
                print(f"Loading fail {ext}", file=sys.stderr)
                traceback.print_exc()

    async def on_ready(self) -> None:
        """
        Called exactly once when the WebSocket handshake is complete
        and the bot cache is fully initialised.
        """
        guild_names = ", ".join(g.name for g in self.guilds) or "no guilds"
        logging.info(
            "Bot is ready! Logged in as %s (%s) – connected to %s",
            self.user, self.user.id, guild_names,
        )
        # Pour les environnements sans logging configuré :
        print(f"Bot ready – {self.user} | Guild: {guild_names}")


async def _bootstrap() -> None:
    # 0) DB init
    await init_db()

    # 1) Bot instance
    bot = Bot()

    # 2) Repositories
    user_repo       = SqlAlchemyUserRepository()
    task_repo       = SqlAlchemyTaskRepository()
    team_repo       = SqlAlchemyTeamRepository(user_repo=user_repo)

    submission_repo = SqlAlchemySubmissionRepository(
        user_repo=user_repo, task_repo=task_repo, team_repo=team_repo
    )

    config_repo     = SqlAlchemyConfigRepository()
    speed_repo      = SqlAlchemySpeedTaskRepository(user_repo=user_repo, task_repo=task_repo)

    # 3) Services that don’t depend on comp/file yet
    config_service  = ConfigService(config_repo)
    user_service    = UserService(user_repo, bot)

    # 4) Services that depend on parameters
    # Default objects (NullParser + generic submission service)
    file_parser = FileParser(NullParser())
    comp_key = None

    guild_mappings = await config_service.list_guild_configs()
    if guild_mappings:
        comp_key = guild_mappings[0].comp  # 'mkw', 'sm64', ...
        ext_cfg = await config_service.get_submission_file_extension(comp_key)

        if ext_cfg and ext_cfg.ext == "rkg":
            file_parser.set_strategy(RkgParser())
        elif ext_cfg and ext_cfg.ext == "rksys":
            file_parser.set_strategy(RksysParser())

        # insert other comps here... (sm64, nsmbw)

        # else: keep NullParser until /set-file is run

    submission_service = build_submission_service(
        comp=comp_key,                      # None ⇒ generic/Null service
        user_svc=user_service,
        submission_repo=submission_repo,
        task_repo=task_repo,
        user_repo=user_repo,
        team_repo=team_repo,
        speed_repo=speed_repo,
        file_parser=file_parser,
    )

    # 5) Remaining services
    task_manager = TaskManager(
        task_repo=task_repo,
        config_service=config_service,
        submission_repo=submission_repo,
        team_repo=team_repo,
        speed_repo=speed_repo,
    )

    team_service = TeamService(
        user_svc=user_service,
        team_repo=team_repo,
        user_repo=user_repo,
        task_repo=task_repo,
    )

    speed_task_service = SpeedTaskService(
        speed_repo=speed_repo,
        task_repo=task_repo,
        user_svc=user_service,
        cfg_svc=config_service,
    )

    # 6) Inject into bot for global access
    bot.task_manager       = task_manager
    bot.config_service     = config_service
    bot.submission_service = submission_service
    bot.speed_task_service = speed_task_service
    bot.team_service       = team_service
    bot.user_service       = user_service
    bot.file_parser        = file_parser

    # 7) Finally run the bot
    await bot.start(TOKEN)

# ──────────── Main ───────────
def main() -> None:
    try:
        asyncio.run(_bootstrap())
    except KeyboardInterrupt:
        print("Bot stopped.")

if __name__ == "__main__":
    main()
