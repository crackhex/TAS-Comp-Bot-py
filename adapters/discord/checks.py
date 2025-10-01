"""
Discord Command Checks
======================

Module path:
    src/adapters/discord/checks.py

Summary:
    Provides decorators to enforce permission checks on Discord commands
    based on guild-specific configuration and roles.

Responsibilities:
    - host_only: only allow command execution if the author has the configured Host role
"""

from typing import Callable, Awaitable
from discord.ext import commands
import discord


def host_only() -> Callable[[commands.Context], Awaitable[bool]]:
    """
    Decorator that ensures the invoking user has the Host role in the server

    The check performs the following steps:
      1) Verifies the command is executed in a server (guild) context.
      2) Retrieves the guild’s configured competition key.
      3) Loads the configured HostRole for that competition.
      4) Confirms that the command author is a discord.Member with that role ID.

    Raises:
        commands.CheckFailure: if not in a guild, if no competition is set,
                               if the Host role is not configured, or
                               if the user lacks the Host role.

    Returns:
        Callable: a predicate function to be used with @commands.check.
    """
    async def predicate(ctx: commands.Context) -> bool:
        if not ctx.guild:
            raise commands.CheckFailure("This command must be used in a server.")

        # Access the ConfigService instance injected on the bot
        cfg_service = ctx.bot.config_service

        # 1) Retrieve the competition configuration for this guild
        guild_cfg = await cfg_service.get_guild_config(ctx.guild.id)
        if not guild_cfg:
            raise commands.CheckFailure(
                "No competition configured for this server. Use `/set-comp` first."
            )
        comp = guild_cfg.comp

        # 2) Load the HostRole for the competition
        host_cfg = await cfg_service.get_host_role(comp)
        if not host_cfg:
            raise commands.CheckFailure("Host role has not been configured for this competition.")

        # 3) Verify the author has the Host role
        member = ctx.author
        if (
            not isinstance(member, discord.Member)
            or host_cfg.role_id not in {role.id for role in member.roles}
        ):
            raise commands.CheckFailure("You do not have the required Host role.")
        return True

    return commands.check(predicate)
