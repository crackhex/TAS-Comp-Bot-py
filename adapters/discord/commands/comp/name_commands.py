"""
Name Management Commands
========================

Module path:
    src/adapters/discord/commands/comp/name_commands.py

Summary:
    Admin and player-facing commands to update display names and team names.
    After any change, refreshes the public "Current Submissions" list.

Responsibilities:
    - /setname (admin): update a competitor's display name.
    - /setteamname (player): rename the player's team.
    - Rebuild the public submissions list after changes.
"""

from __future__ import annotations

import re
import discord
from discord.ext import commands

from adapters.discord.utils.submission_utils import refresh_submission_list
from application.services.user_service       import UserService
from application.services.team_service       import TeamService
from application.services.task_manager       import TaskManager
from application.services.config_service     import ConfigService

MAX_LEN     = 50
INVALID_PAT = re.compile(r"[@]")


class NameCommands(commands.Cog):
    """Admin and player commands to rename users and teams."""

    def __init__(
        self,
        user_service: UserService,
        team_service: TeamService,
        task_manager: TaskManager,
        config_service: ConfigService,
    ):
        self.user_svc  = user_service
        self.team_svc  = team_service
        self.task_mgr  = task_manager
        self.cfg_svc   = config_service

    # ──────────── ADMIN : /setname ────────────
    @commands.command(
        name="setname",
        usage="$setname <member> <name>",
        help=("""
                Sets a competitor's name to a preferred alias different to their display name.

                Parameters:
                `member`: The member whose name to change.
                `name`: The name. Length must be at most 50 characters, and the name may not contain `@`.
        """),
    )

    @commands.has_permissions(administrator=True)
    async def set_name(
        self,
        ctx: commands.Context,
        member: discord.Member,
        *,
        new_name: str,
    ):
        """
        Update a competitor's display name, with basic validation.

        Args:
            ctx (commands.Context): Invocation context
            member (discord.Member): Target user.
            new_name (str): New display name (<= 50 chars, no '@').
        """
        # 1) Validate input
        if len(new_name) > MAX_LEN or INVALID_PAT.search(new_name):
            return await ctx.send("Invalid name (max 50 chars, no '@').")

        # 2) Update in domain
        try:
            user = await self.user_svc.update_display_name(member.id, new_name)
        except Exception as exc:
            return await ctx.send(f"Could not update: {exc}")

        # 3) Refresh public list (single-guild friendly: use ctx.guild directly)
        await refresh_submission_list(
            bot=ctx.bot,
            cfg_svc=self.cfg_svc,
            guild=ctx.guild,
        )

        return await ctx.send(f"✅ {member.mention}'s name updated → **{user.display_name}**")

    # ──────────── PLAYER : /setteamname ────────────
    @commands.command(
        name="setteamname",
        usage="$setteamname <name>",
        help=("""
            Changes your team name in a collab task. 

            Parameters:
            `name`: The team name. Length must be at most 50 characters, and the name may not contain `@`.
    """),
    )
    async def set_team_name(
        self,
        ctx: commands.Context,
        *,
        new_team_name: str,
    ):
        """
        Rename the calling competitor's team.

        Args:
            new_team_name (str): New team name (<= 50 chars, no '@').
        """
        # 1) Validate input
        if len(new_team_name) > MAX_LEN or INVALID_PAT.search(new_team_name):
            return await ctx.send("Invalid team name (max 50 chars, no '@').")

        # 2) Must have an active team-based competition
        task = await self.task_mgr.get_active_task()
        if not task:
            return await ctx.send("There is no active task")
        if task.team_size <= 1:
            return await ctx.send("This task is not a collab task.")

        # 3) Resolve the guild (single-guild instance)
        #    If run from a server, use that guild; otherwise, take the first connected guild.
        if ctx.guild is not None:
            guild = ctx.guild
        else:
            if not ctx.bot.guilds:
                return await ctx.send("No guild/server available for this bot instance.")
            guild = ctx.bot.guilds[0]

        # 4) Load the caller's team
        team = await self.team_svc.get_team_by_member(ctx.author.id)
        if not team:
            return await ctx.send("You are not in a team.")

        # 5) Persist the new name
        await self.team_svc.rename_team(team.id, new_team_name)

        # 6) Refresh the public submissions list for the configured server
        await refresh_submission_list(
            bot=ctx.bot,
            cfg_svc=self.cfg_svc,
            guild=guild,
        )

        return await ctx.send(f"Team name updated → **{new_team_name}**")


# ───────────────── setup ─────────────────
async def setup(bot: commands.Bot):
    """
    Cog setup hook. Registers the commands with the bot.
    """
    await bot.add_cog(
        NameCommands(
            user_service=bot.user_service,
            team_service=bot.team_service,
            task_manager=bot.task_manager,
            config_service=bot.config_service,
        )
    )
