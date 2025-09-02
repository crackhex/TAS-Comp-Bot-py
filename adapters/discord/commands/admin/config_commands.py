"""
Configuration Commands
======================

Module path:
    src/adapters/discord/commands/config_commands.py

Summary:
    Administrative commands to bind a Discord guild to a competition and to
    configure core roles and channels used by the bot.

Responsibilities:
    - Map the current guild to a competition identifier (`/set-comp`, `/show-comp`).
    - Configure essential roles and channels for the competition (`/config`):
      Host role, Submitter role, Log channel, Submission channel, Seeking channel,
      Tasks channel, and Announcements channel.
"""

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from application.services.config_service import ConfigService
from application.services.submission_services.service_factory import build_submission_service


class ConfigCommands(commands.Cog):
    """
    Cog exposing admin-only commands that manage competition configuration
    at the guild level.
    """

    def __init__(self, config_service: ConfigService):
        """
        Initialize the cog.

        Args:
            config_service (ConfigService): Service used to persist and
                retrieve configuration entities.
        """
        self.cfg = config_service

    @commands.hybrid_command(
        name="set-comp",
        description="Associate this Discord server with a competition (e.g. MKWii).",
        with_app_command=True,
    )
    @commands.has_permissions(administrator=True)
    @app_commands.describe(
        comp="Select the competition this guild will run",
    )
    @app_commands.choices(
        comp=[
            app_commands.Choice(name="Mario Kart Wii", value="mkw"),
            # app_commands.Choice(name="New Super Mario Bros. Wii", value="nsmbw"),
            # app_commands.Choice(name="Super Mario 64", value="sm64"),
        ]
    )
    async def set_comp(
        self,
        ctx: commands.Context,
        comp: str,
    ):
        """
        Bind the current guild to the given competition key.

        Permissions:
            Administrator required.

        Args:
            ctx (commands.Context): Invocation context.
            comp (str): Competition identifier (mkw, nsmbw, sm64, etc).

        Returns:
            None. Sends a confirmation message on success.
        """
        await self.cfg.set_guild_config(ctx.guild.id, comp)

        bot: commands.Bot = ctx.bot

        bot.submission_service = build_submission_service(
            comp=comp.lower(),
            user_svc=bot.user_service,
            submission_repo=bot.submission_service._sub_repo,
            task_repo=bot.task_manager._task_repo,
            user_repo=bot.user_service._user_repo,
            team_repo=bot.team_service._team_repo,
            speed_repo=bot.speed_task_service._speed_repo,
            file_parser=bot.file_parser,
        )

        await ctx.send(
            f"Mapping guild → comp saved: **{comp}** for this server."
        )

    @commands.hybrid_command(
        name="show-comp",
        description="Display the competition associated with this server.",
    )
    async def show_comp(self, ctx: commands.Context):
        """
        Show the competition key currently bound to this guild.

        Args:
            ctx (commands.Context): Invocation context.

        Returns:
            None. Replies with the configured competition or an error if unset.
        """
        gc = await self.cfg.get_guild_config(ctx.guild.id)
        if not gc:
            return await ctx.send(
                "No competition configured. Use `/set-comp` first."
            )
        return await ctx.send(f"Current comp: **{gc.comp}**")

    # Global configuration -------------------------------------------- #
    @commands.hybrid_command(
        name="config",
        description="Configure core roles & channels",
    )
    @commands.has_permissions(administrator=True)
    async def config(
        self,
        ctx: commands.Context,
        # Converters work for both slash and prefix invocations
        host_role: Optional[discord.Role] = None,
        submitter_role: Optional[discord.Role] = None,
        log_channel: Optional[discord.TextChannel] = None,
        submission_channel: Optional[discord.TextChannel] = None,
        seeking_channel: Optional[discord.TextChannel] = None,
        tasks_channel: Optional[discord.TextChannel] = None,
        announcements_channel: Optional[discord.TextChannel] = None,
    ):
        """
        Update one or more configuration items for this guild. Omitted parameters
        are left unchanged.

        Example:
            /config host_role:@Host log_channel:#logs tasks_channel:#tasks

        Permissions:
            Administrator required.

        Args:
            ctx (commands.Context): Invocation context.
            host_role (discord.Role | None): Role with host permissions.
            submitter_role (discord.Role | None): Role given to users who submitted.
            log_channel (discord.TextChannel | None): Channel for internal logs.
            submission_channel (discord.TextChannel | None): Channel showing submissions.
            seeking_channel (discord.TextChannel | None): Channel for team seeking.
            tasks_channel (discord.TextChannel | None): Channel for task descriptions.
            announcements_channel (discord.TextChannel | None): Channel for announcements.

        Returns:
            None. Sends a summary of changes applied.
        """
        # Ensure a competition is bound to this guild
        gc = await self.cfg.get_guild_config(ctx.guild.id)
        if not gc:
            return await ctx.send("No competition configured. Use `/set-comp` first.")
        comp = gc.comp

        updates: list[str] = []

        # Apply updates only for provided parameters
        if host_role:
            await self.cfg.set_host_role(comp, host_role.id, host_role.name, ctx.guild.id)
            updates.append(f"HostRole → {host_role.mention}")

        if submitter_role:
            await self.cfg.set_submitter_role(comp, submitter_role.id, submitter_role.name, ctx.guild.id)
            updates.append(f"SubmitterRole → {submitter_role.mention}")

        if log_channel:
            await self.cfg.set_log_channel(comp, log_channel.id, ctx.guild.id)
            updates.append(f"LogChannel → {log_channel.mention}")

        if submission_channel:
            await self.cfg.set_submission_channel(comp, submission_channel.id, ctx.guild.id)
            updates.append(f"SubmissionChannel → {submission_channel.mention}")

        if seeking_channel:
            await self.cfg.set_seeking_channel(comp, seeking_channel.id, ctx.guild.id)
            updates.append(f"SeekingChannel → {seeking_channel.mention}")

        if tasks_channel:
            await self.cfg.set_tasks_channel(comp, tasks_channel.id, ctx.guild.id)
            updates.append(f"TasksChannel → {tasks_channel.mention}")

        if announcements_channel:
            await self.cfg.set_announcements_channel(comp, announcements_channel.id, ctx.guild.id)
            updates.append(f"AnnouncementsChannel → {announcements_channel.mention}")

        if not updates:
            return await ctx.send("No parameters provided; nothing to update.")

        await ctx.send("Updated:\n" + "\n".join(f"• {u}" for u in updates))


# ───────────────────────────── Extension setup ────────────────────────────── #
async def setup(bot: commands.Bot) -> None:
    """
    Register the configuration commands cog.

    Args:
        bot (commands.Bot): The bot instance.
    """
    cfg: ConfigService = bot.config_service
    await bot.add_cog(ConfigCommands(cfg))
