"""
Request Task Command
====================

Module path:
    src/adapters/discord/commands/comp/request_task_command.py

Summary:
    Starts a private speed-task session for the caller, DMs the task description and
    their personal (minute-rounded) deadline, then persists the session.

Responsibilities:
    - Resolve the target guild when invoked from a server or via DM.
    - Validate that a speed-task is active and correctly configured.
    - Enforce “one session per task, per user” (no re-request after their session is over).
    - Round the personal deadline to the nearest minute.
    - DM the user the description and deadline, then persist via SpeedTaskService.
"""

import time
from datetime import datetime, timedelta

import discord
from discord.ext import commands

from application.services.speed_task_service import SpeedTaskService
from application.services.config_service import ConfigService
from application.services.task_manager import TaskManager


class RequestTaskCommand(commands.Cog):
    """
    Cog that exposes the `$requesttask` command to start a personal speed-task session.

    Attributes:
        speed_svc (SpeedTaskService): Domain/application service for speed-task sessions.
        task_mgr (TaskManager): Service to read the currently active task.
        cfg_svc (ConfigService): Service to read competition/guild configuration.
    """

    def __init__(
        self,
        speed_svc: SpeedTaskService,
        task_mgr:  TaskManager,
        cfg_svc:   ConfigService,
    ):
        self.speed_svc = speed_svc
        self.task_mgr  = task_mgr
        self.cfg_svc   = cfg_svc

    @commands.command(
        name="requesttask",
        usage="$requesttask",
        help=("""
            Requests a speed task. If one is ongoing, it will be sent to you in DMs. Warning: No confirmation

            Parameters:
            None
    """),
    )
    async def requesttask(self, ctx: commands.Context):
        """
        Start (only once per task) a personal speed-task session for the invoking user.

        Flow:
            1) Resolve the configured guild (works in server or in DM).
            2) Ensure an active speed-task exists.
            3) Enforce the “one session per task, per user” rule (block if any session already exists,
               whether still active or already expired).
            4) If the speed-task has already been publicly released, redirect the user.
            5) Load description and length; compute and minute-round the personal deadline.
            6) DM the user the details; if DM fails, abort.
            7) Persist the session and confirm in the channel/DM.
        """
        # ───── 1) Resolve configured guild (server or DM context) ───── #
        if ctx.guild:
            target_guild = ctx.guild
        else:
            target_guild = None
            for g in ctx.bot.guilds:  # type: ignore
                if await self.cfg_svc.get_guild_config(g.id):
                    target_guild = g
                    break
        if not target_guild:
            return await ctx.send("There is no competition configured for this server. Use `/set-comp`.")

        # Load config and the active task
        gc   = await self.cfg_svc.get_guild_config(target_guild.id)
        task = await self.task_mgr.get_active_task()
        if not gc or not task or not task.speed_task:
            return await ctx.send("There is no ongoing speed task!")

        user_id = ctx.author.id
        now     = int(time.time())

        # ───── 2) One /requesttask per task (even after expiry) ───── #
        existing = await self.speed_svc.get_session_for_user(user_id)
        if existing:
            # If still active, show remaining time
            if existing.is_active():
                return await ctx.send(
                    "ℹ️ You already have an ongoing session, "
                    f"your deadline is: <t:{existing.personal_deadline}:R>"
                )
            # Otherwise it already ended: deny a second attempt
            return await ctx.send(
                "Your speed task session is already over! You may not re-request."
            )

        # ───── 3) If already publicly released, redirect to #tasks ───── #
        if task.is_released:
            tasks_cfg = await self.cfg_svc.get_tasks_channel(gc.comp)
            if tasks_cfg and tasks_cfg.channel_id:
                ch = target_guild.get_channel(tasks_cfg.channel_id)
                mention = ch.mention if isinstance(ch, discord.TextChannel) else f"<#{tasks_cfg.channel_id}>"
            else:
                mention = "`#tasks`"
            return await ctx.send(
                "The speed-task is already publicly released! "
                f"See {mention}."
            )

        # ───── 4) Load description & length from config ───── #
        desc_cfg   = await self.cfg_svc.get_speed_task_desc(gc.comp)
        length_cfg = await self.cfg_svc.get_speed_task_length(gc.comp)
        if not desc_cfg or not length_cfg:
            return await ctx.send("The speed-task configuration is incomplete. Please contact the current host.")

        # ───── 5) Compute and minute-round the personal deadline ───── #
        length_sec   = int(length_cfg.time * 3600)
        raw_deadline = now + length_sec
        dt = datetime.fromtimestamp(raw_deadline)
        # Round seconds -> 0; if ≥ 30s, ceiling to next full minute
        if dt.second >= 30:
            dt = dt.replace(second=0, microsecond=0) + timedelta(minutes=1)
        else:
            dt = dt.replace(second=0, microsecond=0)
        personal_deadline = int(dt.timestamp())

        # ───── 6) DM the description + deadline ───── #
        dm_text = (
            f"🏁 **Speed-Task started**!\n\n"
            f"{desc_cfg.desc}\n\n"
            f"You have until <t:{personal_deadline}:f> (<t:{personal_deadline}:R>) to submit!\n"
            f"Good luck!"
        )
        try:
            await ctx.author.send(dm_text)
        except discord.Forbidden:
            return await ctx.send(
                "❌ I couldn’t DM you (check your privacy settings). "
                "Your speed task session was not started."
            )

        # ───── 7) Persist the session ───── #
        await self.speed_svc.request_task(
            user_discord_id=ctx.author.id,
            guild_id=       target_guild.id,
        )

        # ───── 8) Public confirmation ───── #
        if ctx.guild:
            return await ctx.send("Your speed task has started; check your DMs.")

        return None


async def setup(bot: commands.Bot):
    await bot.add_cog(
        RequestTaskCommand(
            speed_svc=bot.speed_task_service,
            task_mgr= bot.task_manager,
            cfg_svc=  bot.config_service,
        )
    )
