"""
Speed‑Task Release Event
=======================

Module path:
    src/adapters/discord/events/speed_task_release.py

Summary:
    Background task that checks, once per minute (aligned on :00), whether the
    current speed‑task should be made public. If the bot time falls within a
    small tolerance window just after the computed release instant, it marks the
    task as released and posts the appropriate announcements.

Responsibilities:
    - Align to each minute boundary and tick every 60 seconds.
    - Determine the relevant competition (comp) from the single guild configured
      for this bot instance.
    - Compute the release instant: release_epoch = task.deadline - speed_length.
    - If now ∈ [release_epoch, release_epoch + LEEWAY]:
        • Mark the task as released via TaskManager.release_speed_task.
        • Announce in the configured tasks channel and announcements channel.
    - Ignore if too early (now < release_epoch) or too late (now > release_epoch + LEEWAY).
"""

import asyncio
import time
import logging
import discord
from discord.ext import tasks, commands

from application.services.task_manager        import TaskManager
from application.services.speed_task_service  import SpeedTaskService
from application.services.config_service      import ConfigService

log = logging.getLogger(__name__)
LEEWAY = 3  # seconds of tolerance after the exact release point


class SpeedTaskReleaseCog(commands.Cog):
    """
    Cog that publishes a speed‑task at the right moment for a single-guild bot.

    The loop runs every minute (aligned on second 0) and:
      1) Verifies an active, not-yet-released speed‑task exists.
      2) Locates the competition identifier (comp) from the single configured guild.
      3) Computes the release epoch as (task.deadline - length_in_seconds).
      4) If the current time is within [release_epoch, release_epoch + LEEWAY], it:
         - calls TaskManager.release_speed_task(comp),
         - posts the description in the tasks channel,
         - posts a public announcement with a pointer to the tasks channel.
    """

    def __init__(
        self,
        bot:       commands.Bot,
        task_mgr:  TaskManager,
        speed_svc: SpeedTaskService,
        cfg_svc:   ConfigService,
    ):
        """
        Initialize the cog and start the periodic release loop.

        Args:
            bot (commands.Bot): The Discord bot instance.
            task_mgr (TaskManager): Orchestrates task lifecycle operations.
            speed_svc (SpeedTaskService): Access to speed‑task data/services.
            cfg_svc (ConfigService): Access to guild/competition configuration.
        """
        self.bot       = bot
        self.task_mgr  = task_mgr
        self.speed_svc = speed_svc
        self.cfg_svc   = cfg_svc
        self.release_loop.start()

    def cog_unload(self):
        """Ensure the background task is cancelled when the cog is unloaded."""
        self.release_loop.cancel()

    @tasks.loop(minutes=1)
    async def release_loop(self):
        """
        Minute-aligned loop that checks whether the speed‑task should be released.

        Steps:
            - Exit early if there is no active speed‑task or if it is already public.
            - Resolve the single guild and get `comp` from its guild config.
            - Load the configured speed‑task length to compute `release_epoch`.
            - If `now` ∈ [release_epoch, release_epoch + LEEWAY], publish and announce.
        """
        now = int(time.time())

        # 1) Is there an active not released speed task
        task = await self.task_mgr.get_active_task()
        if not task or not task.speed_task or task.is_released:
            return

        # 2) Resolve the guild and competition identifier (comp)
        if not self.bot.guilds:
            return  # no guild connected
        guild = self.bot.guilds[0]

        gc = await self.cfg_svc.get_guild_config(guild.id)
        if not gc:
            return
        comp = gc.comp

        # 3) Load duration (speed-task length) to compute release time
        length_cfg = await self.cfg_svc.get_speed_task_length(comp)
        if not length_cfg:
            return
        length_sec    = int(length_cfg.time * 3600)
        release_epoch = task.deadline - length_sec

        # 4) Fire only within the tolerance window [release_epoch, release_epoch + LEEWAY]
        if now < release_epoch:
            return
        if now > release_epoch + LEEWAY:
            # too late for this tick;
            return

        # 5) Mark as released (persist in DB)
        await self.task_mgr.release_speed_task(comp)

        # 6) Announce in the configured task channel of the server
        tasks_cfg = await self.cfg_svc.get_tasks_channel(comp)
        if tasks_cfg and tasks_cfg.channel_id:
            ch_tasks = guild.get_channel(tasks_cfg.channel_id)
            if isinstance(ch_tasks, discord.TextChannel):
                desc_cfg = await self.cfg_svc.get_speed_task_desc(comp)
                desc     = desc_cfg.desc if desc_cfg else "No description provided."
                await ch_tasks.send(
                    f"{desc}\n\n"
                    f"You have until <t:{task.deadline}:f> (<t:{task.deadline}:R>) to submit!"
                )

        # – announcements channel: Link to #tasks
        ann_cfg = await self.cfg_svc.get_announcements_channel(comp)
        if ann_cfg and ann_cfg.channel_id:
            ch_ann = guild.get_channel(ann_cfg.channel_id)
            if isinstance(ch_ann, discord.TextChannel):
                mention = (
                    guild.get_channel(tasks_cfg.channel_id).mention
                    if tasks_cfg and tasks_cfg.channel_id
                    else f"<#{tasks_cfg.channel_id if tasks_cfg else ''}>"
                )
                await ch_ann.send(
                    "The speed task is now public! "
                    f"Head over to {mention} for details."
                )

    @release_loop.before_loop
    async def before_check(self):
        """
        Wait until the bot is ready and align the first tick to the next minute
        boundary (sleep exactly the remaining seconds to reach :00).
        """
        await self.bot.wait_until_ready()
        now = discord.utils.utcnow()
        secs = (60 - now.second - now.microsecond / 1_000_000) % 60
        await asyncio.sleep(secs)


async def setup(bot: commands.Bot):
    """
    Register this cog on the bot.

    Args:
        bot (commands.Bot): The Discord bot instance.
    """
    await bot.add_cog(
        SpeedTaskReleaseCog(
            bot=       bot,
            task_mgr=  bot.task_manager,
            speed_svc= bot.speed_task_service,
            cfg_svc=   bot.config_service,
        )
    )
