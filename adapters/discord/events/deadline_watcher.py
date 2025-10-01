"""
Deadline Watcher Task
=====================

Module path:
    src/adapters/discord/tasks/deadline_watcher.py

Summary:
    Background task that checks the active task's deadline at fixed intervals
    and gracefully closes the competition within a small tolerance window.

Responsibilities:
    - Align to each minute mark and, every 60 seconds, verify the active task's deadline.
    - If current time is between [deadline, deadline + LEEWAY], then:
        1) End the competition via TaskManager.end_task.
        2) Post a closure announcement in each guild's configured announcement channel.
    - Ignore all other times outside the tolerance window.
"""

import asyncio
import time
import logging
import discord
from discord.ext import commands, tasks

from application.services.task_manager    import TaskManager
from application.services.config_service  import ConfigService

log = logging.getLogger(__name__)
LEEWAY = 3  # seconds of tolerance after the exact deadline


class DeadlineWatcher(commands.Cog):
    """
    Cog that monitors the active competition's deadline.

    Every 60 seconds (aligned to the clock), it checks:
      - If there is an active competition.
      - If current time >= deadline and <= deadline + LEEWAY.
    If within that window, it closes the competition and announces the closure
    in each guild's configured announcements channel.
    Outside that window, it does nothing.
    """

    def __init__(
        self,
        bot: commands.Bot,
        task_manager: TaskManager,
        config_service: ConfigService,
    ):
        """
        Initialize the DeadlineWatcher.

        Args:
            bot (commands.Bot): the Discord bot instance.
            task_manager (TaskManager): service to manage competition lifecycle.
            config_service (ConfigService): service to access guild configuration.
        """
        self.bot = bot
        self.task_manager = task_manager
        self.config_service = config_service

        # Start the periodic check loop
        self.check_deadline_loop.start()

    def cog_unload(self):
        """
        Cancel the check loop when the Cog is unloaded.
        """
        self.check_deadline_loop.cancel()

    @tasks.loop(seconds=60)
    async def check_deadline_loop(self):
        """
        Loop executed every 60 seconds to enforce the competition deadline.
        """
        try:
            active = await self.task_manager.get_active_task()
            if not active:
                return

            now = int(time.time())
            deadline = active.deadline

            # Only proceed if within the tolerance window
            if now < deadline or now > deadline + LEEWAY:
                return


            # 1) Terminate the competition
            await self.task_manager.end_task(active.id)

            # 2) Announce in the server's configured announcements channel
            if not self.bot.guilds:
                return  # No guild connected

            guild = self.bot.guilds[0]

            gc = await self.config_service.get_guild_config(guild.id)
            if not gc:
                return

            ann_cfg = await self.config_service.get_announcements_channel(gc.comp)
            if not ann_cfg or not ann_cfg.channel_id:
                return

            channel = guild.get_channel(ann_cfg.channel_id)
            if isinstance(channel, discord.TextChannel):
                await channel.send(f"Task {active.number} is now over! Thank you to everyone who participated!")

        except Exception as e:
            log.exception(f"[DeadlineWatcher] Error in check loop: {e}")

    @check_deadline_loop.before_loop
    async def before_check(self):
        """
        Align the start of the loop to the next exact minute.

        Waits until the bot is ready, then sleeps the few seconds remaining
        until the clock hits :00 seconds.
        """
        await self.bot.wait_until_ready()
        now = discord.utils.utcnow()
        secs = (60 - now.second - now.microsecond / 1_000_000) % 60
        await asyncio.sleep(secs)


async def setup(bot: commands.Bot):
    """
    Cog setup function called by the bot loader.
    """
    await bot.add_cog(
        DeadlineWatcher(
            bot,
            task_manager=   bot.task_manager,
            config_service= bot.config_service,
        )
    )
