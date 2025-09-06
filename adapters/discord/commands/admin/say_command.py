"""
Say Command
===========

Module path:
    src/adapters/discord/commands/admin/say_command.py

Summary:
    Owner/administrator utility to post an arbitrary message into a specified
    text channel via a classic (prefix) command.

Responsibilities:
    - Expose a `$say` command restricted to administrators.
    - Take a target TextChannel and a message, then post it there.
    - Acknowledge the action by replying in the invoking context.
"""

import discord
from discord.ext import commands


class Say(commands.Cog):
    """
    Cog that provides an administrator-only `$say` command to send a message to
    any specified text channel.
    """

    def __init__(self, bot: commands.Bot) -> None:
        """
        Initialize the cog.

        Args:
            bot (commands.Bot): The Discord bot instance.
        """
        self.bot = bot

    @commands.command(
        name="say",
        usage = "$say <text_channel> <message>",
        help = ("""
                Say something through the bot.
    
                Parameters:
                `text_channel`: The text channel in which the message will be sent.
                `message`: The message to send.
        """),
    )
    @commands.has_permissions(administrator=True)
    async def command(self, ctx: commands.Context, channel: discord.TextChannel, *, message: str) -> None:
        """
        Send a message to the given text channel.

        Permissions:
            Administrator required (checked by @commands.has_permissions).

        Args:
            ctx (commands.Context): Invocation context (where the command was run).
            channel (discord.TextChannel): The channel to post the message into.
            message (str): The content to send.

        Returns:
            None. Sends the provided message to the target channel and acknowledges
            the action with a reply in the invoking channel.

        """
        # Post the message to the specified channel
        await channel.send(message)

        # Acknowledge in the command context
        await ctx.reply(f"Message sent to {channel.mention}.")


async def setup(bot: commands.Bot) -> None:
    """
    Register the Say cog with the bot.

    Args:
        bot (commands.Bot): The bot instance.
    """
    await bot.add_cog(Say(bot))
