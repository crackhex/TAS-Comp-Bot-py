"""
DM Command
=======================

Module path:
    src/adapters/discord/commands/host/dm_command.py

Summary:
    Host-only hybrid command that DMs a user with a message

Responsibilities:
    - DM the specified user with a message
    - Log the message in the current channel
"""

import discord
from discord.ext import commands

from adapters.discord.checks import host_only


class DM(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(
        name="dm",
        description="[Host] Dm a user",
        usage="/dm <User>",
        help=("""
            DMs a user. 

            Parameters:
                `User`: The user to send a message to (ping them, or write their handle).
            """),
        with_app_command=True)
    @host_only()
    async def command(self, ctx, user: discord.Member, *, message):
        """Send a direct message to a user"""
        try:
            # Prepare the logged message
            log_message = f"Message sent to {user.display_name}: {message}"

            # Send the direct message to the user
            await user.send(message)

            # Send the logged message
            await ctx.send(log_message)
        except (discord.HTTPException, discord.Forbidden):
            await ctx.send("Failed to send message")


async def setup(bot) -> None:
    await bot.add_cog(DM(bot))