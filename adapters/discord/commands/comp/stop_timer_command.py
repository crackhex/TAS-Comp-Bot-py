"""
Stop Timer Command
==================

Module path:
    src/adapters/discord/commands/comp/stop_timer_command.py

Summary:
    Hybrid command that ends a competitor's personal speed-task session early.
    Usable by:
      • A competitor (to stop **their own** timer via DM).
      • A host (to stop **someone else's** timer in a guild, after confirmation).

Responsibilities:
    - Resolve the configured guild/competition context.
    - Verify a speed-task is currently active.
    - Identify the target competitor (caller in DM, or specified member in guild).
    - Confirm the irreversible action via a two-button View.
    - Expire the personal session and grant the "submitted" role if configured.
    - Notify the caller, and DM the competitor when a host stops their timer.
"""
from __future__ import annotations

import discord
from discord.ext import commands

from application.services.speed_task_service import SpeedTaskService
from application.services.task_manager       import TaskManager
from application.services.config_service     import ConfigService
from adapters.discord.utils.role_utils       import add_role_to_member


class ConfirmView(discord.ui.View):
    """Two-button confirmation view (Confirm / Cancel)."""

    def __init__(self, author: discord.User, *, timeout: int = 60):
        """
        Initialize the confirmation view.

        Args:
            author (discord.User): Only this user can interact with the buttons.
            timeout (int): View timeout (seconds), after which the interaction ends.
        """
        super().__init__(timeout=timeout)
        self.author = author
        self.value: bool | None = None  # True = confirmed, False = canceled, None = timed out

    async def interaction_check(self, inter: discord.Interaction) -> bool:  # type: ignore
        """
        Restrict the buttons so only `author` can interact.

        Args:
            inter (discord.Interaction): The incoming interaction.

        Returns:
            bool: True if interaction is allowed; otherwise sends an ephemeral
                  warning and returns False.
        """
        if inter.user != self.author:
            await inter.response.send_message(
                "You cannot interact with this confirmation.",
                ephemeral=True,
            )
            return False
        return True

    async def _finish(self, inter: discord.Interaction):
        """
        Disable buttons and finalize the view once a decision is made.

        Args:
            inter (discord.Interaction): The interaction that triggered finishing.
        """
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        await inter.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, inter: discord.Interaction, _: discord.ui.Button):  # type: ignore
        """Mark as confirmed and finalize the view."""
        self.value = True
        await self._finish(inter)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, inter: discord.Interaction, _: discord.ui.Button):  # type: ignore
        """Mark as canceled and finalize the view."""
        self.value = False
        await self._finish(inter)


class StopTimerCommand(commands.Cog):
    """
    Cog providing `/stop-timer` (and alias `/end-timer`).

    Usage:
        • In DM with no argument: stops **your own** speed-task timer.
        • In a guild with a @member argument: stops **that member's** timer (host-only).

    Attributes:
        speed_svc (SpeedTaskService): Service to manage personal speed-task sessions.
        task_mgr  (TaskManager): Service to resolve the active task.
        cfg_svc   (ConfigService): Service for guild/competition configuration.
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
        name="stop-timer",
        aliases=["end-timer"],
        usage="$stop-timer [member]",
        help=("""
            End your speed-task early, or end another competitor’s timer if you are a host.

            Parameters:
            `member`: [Host-only] Optionally, the member whose timer to end.
    """),
    )
    async def stop_timer(
        self,
        ctx: commands.Context,
        member: discord.Member | None = None,
    ):
        """
        End the target competitor's personal speed-task session early.

        Behavior:
            - DM + no member: end the caller's own timer.
            - Guild + member provided: requires host role; ends that member's timer.

        Steps:
            0) Resolve the configured guild (for DM, find the one this bot is configured for).
            1) Ensure an active speed-task exists.
            2) Identify the target competitor and verify permissions.
            3) Validate that a session exists and is still active.
            4) Present a two-button confirmation view.
            5) On confirm, expire the session and grant the "submitted" role if configured.
            6) Notify the caller; if a host stopped someone else’s timer, DM the competitor.

        Args:
            ctx (commands.Context): Command invocation context.
            member (discord.Member | None): Optional target competitor (guild-only).

        Returns:
            None

        Raises:
            Sends user-facing errors via ctx.send on validation failures.
        """
        # ───────── 0) Resolve the configured guild ───────── #
        if ctx.guild:
            target_guild = ctx.guild
        else:
            # In DMs: find the (single) server this bot instance is configured for.
            target_guild = None
            for g in ctx.bot.guilds:  # type: ignore
                if await self.cfg_svc.get_guild_config(g.id):
                    target_guild = g
                    break
        if not target_guild:
            return await ctx.send("There is no competition configured for this server. Please contact an admin.")

        # Load competition configuration for that server
        gc = await self.cfg_svc.get_guild_config(target_guild.id)
        if not gc:
            return await ctx.send("There is no competition configured for this server. Please contact an admin.")

        # ───────── 1) Ensure a speed-task is active ───────── #
        task = await self.task_mgr.get_active_task()
        if not task or not task.speed_task:
            return await ctx.send("There is no ongoing speed task")

        # ───────── 2) Determine the target competitor & check permissions ───────── #
        if member is None:
            # In DMs, you may only end your own timer.
            if ctx.guild:
                return await ctx.send("Use this command in DM to end your timer.")
            competitor_id = ctx.author.id
            issuer_is_host = False
        else:
            # In a server, only hosts can end someone else's timer.
            if not ctx.guild:
                return await ctx.send("This usage is only available in a server.")
            host_cfg = await self.cfg_svc.get_host_role(gc.comp)

            # Check if user requesting has host role
            host_role_ok = (
                host_cfg
                and host_cfg.role_id
                and discord.utils.get(ctx.author.roles, id=host_cfg.role_id)
            )
            if not host_role_ok:
                return await ctx.send("🚫 Only a **host** can end another competitor’s timer.")
            competitor_id = member.id
            issuer_is_host = True

        # ───────── 3) Validate session existence and state ─────────
        session = await self.speed_svc.get_session_for_user(competitor_id)
        is_self = (competitor_id == ctx.author.id)

        if not session:
            return await ctx.send(
                "You don't have an active speed-task session."
                if is_self else
                "This competitor does not have an active speed-task session."
            )

        if not session.is_active():
            return await ctx.send(
                "Your speed-task session is already over!"
                if is_self else
                "This competitor's speed-task session is already over!"
            )

        # ───────── 4) Ask for explicit confirmation ───────── #
        view = ConfirmView(author=ctx.author)
        await ctx.send(
            "❗ Are you sure you want to end the speed-task? "
            "This action cannot be undone.",
            view=view,
        )
        await view.wait()

        if view.value is None:
            return await ctx.send("⏲️ Timed out — the timer continues.")
        if not view.value:
            return await ctx.send("❌ Canceled — the timer continues.")

        # ───────── 5) Expire the session and grant submitter role (if any) ───────── #
        # a) Expire the personal session
        await self.speed_svc.expire_session(competitor_id)

        # b) Add the “submitted” role if configured
        submit_cfg = await self.cfg_svc.get_submitter_role(gc.comp)
        if submit_cfg and submit_cfg.role_id:
            await add_role_to_member(
                target_guild,
                competitor_id,
                submit_cfg.role_id,
            )

        # ───────── 6) Notify caller and (if applicable) the competitor ───────── #
        await ctx.send("You have successfully ended your speed task early — thanks for participating!")

        # If a host ended someone else’s timer, DM the affected competitor
        if issuer_is_host and competitor_id != ctx.author.id:
            try:
                user = ctx.bot.get_user(competitor_id) or await ctx.bot.fetch_user(competitor_id)
                return await user.send(
                    f"Your timer was ended early by a host."
                )
            except discord.Forbidden:
                pass

        return None


async def setup(bot: commands.Bot):
    """
    Register the StopTimerCommand cog.

    Args:
        bot (commands.Bot): The bot instance exposing application services.
    """
    await bot.add_cog(
        StopTimerCommand(
            speed_svc=bot.speed_task_service,
            task_mgr= bot.task_manager,
            cfg_svc=  bot.config_service,
        )
    )
