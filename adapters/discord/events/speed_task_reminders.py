"""
Speed-Task Reminder Task
========================

Module path:
    src/adapters/discord/events/speed_task_reminder.py

Summary:
    Minute-aligned background task that:
      1) Sends DM reminders to users with active personal speed-task sessions,
         using a small ±LEEWAY second window at the top of each minute.
      2) Expires personal sessions at their deadline (within ±LEEWAY) and assigns
         the "submitted" role.
      3) After public release, sends public reminder messages in the guild’s
         announcement channel using the same ±LEEWAY window.

Responsibilities:
    - Align to each :00 mark and tick every 60 seconds.
    - Retrieve the single configured guild and its competition (comp).
    - For each active personal session:
        * If remaining time is within [target-LEEWAY, target] → DM reminder.
        * If remaining time <= LEEWAY → expire session and assign role.
    - If the speed-task is public:
        * If global remaining time is within [target-LEEWAY, target] → public reminder.

Notes:
    - This implementation is "stateless" (no DB or memory flags to dedupe reminders).
      It relies on the loop being aligned to :00 and a narrow window (±LEEWAY) to fire
      at most once per reminder/minute.
"""

import asyncio
import time
import logging
from typing import List

import discord
from discord.ext import tasks, commands

from application.services.speed_task_service import SpeedTaskService
from application.services.config_service     import ConfigService
from application.services.task_manager       import TaskManager

log = logging.getLogger(__name__)

LEEWAY = 3  # seconds of tolerance for reminders and expiration


def _format_minutes_en(minutes: int) -> str:
    """
    Human-readable formatter for minute counts.

    Examples:
        1   -> "1 minute"
        45  -> "45 minutes"
        60  -> "1 hour"
        61  -> "1 hour and 1 minute"
        90  -> "1 hour and 30 minutes"
        120 -> "2 hours"
    """
    h, m = divmod(minutes, 60)
    if h == 0:
        return f"{m} minute" if m == 1 else f"{m} minutes"
    if m == 0:
        return f"{h} hour" if h == 1 else f"{h} hours"
    # both hours and minutes
    hours_part = f"{h} hour" if h == 1 else f"{h} hours"
    minutes_part = f"{m} minute" if m == 1 else f"{m} minutes"
    return f"{hours_part} and {minutes_part}"


class SpeedTaskReminderCog(commands.Cog):
    """
    Sends DM and public reminders for speed-tasks in a single-guild deployment.

    The loop runs every 60 seconds (aligned to :00) and:
      - DMs users N minutes before their personal deadline (N ∈ reminders),
        using a ±LEEWAY seconds window.
      - Expires personal sessions (<= LEEWAY seconds left) and assigns the
        "submitted" role in the single configured guild.
      - After public release, posts N-minute reminders to the announcements channel.
    """

    def __init__(
        self,
        bot:       commands.Bot,
        speed_svc: SpeedTaskService,
        task_mgr:  TaskManager,
        cfg_svc:   ConfigService,
    ):
        """
        Args:
            bot (commands.Bot): The Discord bot instance.
            speed_svc (SpeedTaskService): Service for speed-task sessions.
            task_mgr (TaskManager): Service to query the active task.
            cfg_svc (ConfigService): Access to channel/role/reminder settings.
        """
        self.bot       = bot
        self.speed_svc = speed_svc
        self.task_mgr  = task_mgr
        self.cfg_svc   = cfg_svc

        self.check_loop.start()

    def cog_unload(self):
        """Cancel the background loop when the cog is unloaded."""
        self.check_loop.cancel()

    @tasks.loop(seconds=60)
    async def check_loop(self):
        """
        Minute-aligned loop that sends reminders and expires sessions.

        Steps:
            0) Ensure there is an active speed-task.
            1) Load reminder minutes from the single configured guild/comp.
            2) For each active personal session:
               - DM when remaining ∈ [target-LEEWAY, target].
               - Expire when remaining ≤ LEEWAY and assign "submitted" role.
            3) If the task is public, send public reminders with the same window.
        """
        now = int(time.time())

        # 0) Active speed-task?
        task = await self.task_mgr.get_active_task()
        if not task or not task.speed_task:
            return

        # Resolve the single guild for this bot instance
        if not self.bot.guilds:
            return  # not connected to any guild
        guild = self.bot.guilds[0]

        # 1) Load reminders for this competition
        gc = await self.cfg_svc.get_guild_config(guild.id)
        if not gc:
            return

        comp = gc.comp
        rem_cfg = await self.cfg_svc.get_speed_task_reminders(comp)
        if not rem_cfg:
            return

        # Collect positive reminder minutes
        reminders: List[int] = []
        for r in (rem_cfg.reminder1, rem_cfg.reminder2, rem_cfg.reminder3, rem_cfg.reminder4):
            if r and r > 0:
                reminders.append(r)

        if not reminders:
            return


        # 2) Private (DM) reminders and per-user expiration
        sessions = await self.speed_svc.list_active_sessions()
        for sess in sessions:
            user_id  = sess.user.discord_id
            left_sec = sess.personal_deadline - now

            # 2.a) DM reminders within [target-LEEWAY, target]
            for r in reminders:
                target = r * 60
                if target - LEEWAY <= left_sec <= target:
                    human = _format_minutes_en(r)
                    user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
                    try:
                        await user.send(f"You have **{human}** left to submit!")
                    except discord.Forbidden:
                        pass

            # 2.b) Expire session and grant "submitted" role when <= LEEWAY
            if left_sec <= LEEWAY:
                await self.speed_svc.expire_session(user_id)

                # DM notification
                user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
                try:
                    await user.send("Your time is up! Thank you for participating!")
                except discord.Forbidden:
                    pass

                # Assign "submitted" role in the single guild
                sub_cfg = await self.cfg_svc.get_submitter_role(comp)
                if sub_cfg and sub_cfg.role_id:
                    member = guild.get_member(user_id)
                    if member:
                        role = guild.get_role(sub_cfg.role_id)
                        if role:
                            try:
                                await member.add_roles(role, reason="Speed-task expired") # TODO: use correct method from utils
                            except discord.Forbidden:
                                pass

        # 3) Public reminders after release
        if task.is_released:
            left_sec_global = task.deadline - now
            for r in reminders:
                target = r * 60
                if target - LEEWAY <= left_sec_global <= target:
                    human = _format_minutes_en(r)
                    ann = await self.cfg_svc.get_announcements_channel(comp)
                    if not ann or not ann.channel_id:
                        continue
                    ch = guild.get_channel(ann.channel_id)
                    if isinstance(ch, discord.TextChannel):
                        await ch.send(f"There is **{human}** remaining to submit to Task {task.number}!")

    @check_loop.before_loop
    async def before_check(self):
        """
        Wait until the bot is ready and align the first tick to the next :00.
        """
        await self.bot.wait_until_ready()

        # Align to the next minute
        now = discord.utils.utcnow()
        secs = (60 - now.second - now.microsecond / 1_000_000) % 60
        await asyncio.sleep(secs)


async def setup(bot: commands.Bot):
    """
    Register the reminder cog on the bot.

    Args:
        bot (commands.Bot): The Discord bot instance.
    """
    await bot.add_cog(
        SpeedTaskReminderCog(
            bot,
            speed_svc=bot.speed_task_service,
            task_mgr=bot.task_manager,
            cfg_svc=bot.config_service,
        )
    )
