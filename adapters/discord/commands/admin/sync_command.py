"""
Slash Command Synchronization
=============================

Module path:
    src/adapters/discord/commands/admin/sync_command.py

Summary:
    Provides a simple owner-only command to force synchronization of the
    application (slash) commands with Discord.

Responsibilities:
    - Expose a `$sync` prefixed command that runs a global `app_commands` sync.
    - Report how many commands were synchronized.

Note: Only takes affect after restarting discord, or pressing 'Ctrl + R'
"""

from discord.ext import commands


class SyncCommand(commands.Cog):
    """
    Cog that exposes an owner-only `$sync` command to synchronize the bot's
    slash commands (application commands) with Discord.
    """

    def __init__(self, bot: commands.Bot):
        """
        Initialize the cog.

        Args:
            bot (commands.Bot): The bot instance whose command tree will be synced.
        """
        self.bot = bot

    @commands.command(
        name="sync",
        usage = "$sync",
        help = ("""
                Synchronization of the bot's slash commands. Usable by bot owner only!

                Parameters:
                None
        """),
    )
    @commands.is_owner()
    async def sync(self, ctx: commands.Context):
        """
        Force a global synchronization of the bot's application (slash) commands.

        Notes:
            - Only the bot owner can invoke this command.

        Args:
            ctx (commands.Context): Invocation context.

        Returns:
            None. Sends a confirmation message indicating how many commands were synced.
        """
        # Global sync of the app command tree
        synced = await self.bot.tree.sync()
        await ctx.send(f"Synchronized {len(synced)} slash commands.")


async def setup(bot: commands.Bot) -> None:
    """
    Register the SyncCommand cog with the bot.

    Args:
        bot (commands.Bot): The bot instance.
    """
    await bot.add_cog(SyncCommand(bot))
