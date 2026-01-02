"""
DM Logger Event
===============

Module path:
    src/adapters/discord/events/dm_logger.py

Summary:
    Cog that listens to all direct messages (DMs) sent to the bot and logs them
    into the configured log channel for the guild.

Responsibilities:
    - Capture and log all DMs (excluding messages from bots or guild messages).
    - Include message text and attachment details in the log.
    - Send the compiled log message to the guild's log channel configured
      in ConfigService.
"""

import discord
from discord.ext import commands
from application.services.config_service import ConfigService


class DMLogger(commands.Cog):
    """
    Cog responsible for logging all direct messages (DMs) received by the bot.

    When a DM is received (from a non-bot user), the content and any attachments
    are logged into the log channel configured for the current guild.
    """

    bot: commands.Bot  # Injected in setup()

    def __init__(self, config_service: ConfigService):
        """
        Initialize the DMLogger.

        Args:
            config_service (ConfigService): The service providing access
                to guild-specific log channel configurations.
        """
        self.cfg_svc = config_service

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        Listener that triggers on every message event.
        Logs DMs into the configured log channel.

        Args:
            message (discord.Message): The message received.
        """
        # 1) Only log DMs from non-bot users (ignore bots or guild messages)
        if message.author.bot or message.guild is not None:
            return

        # 2) Build the log content
        author = message.author
        header = f"📩 DM from **{author.display_name}** (`{author}` / {author.id}):"
        body   = message.content or "*(no text)*"
        lines  = [header, body]

        # 3) Append any attachments (files, images, etc.)
        for att in message.attachments:
            lines.append(f"📎 {att.filename}: {att.url}")

        log_text = "\n".join(lines)

        # 4) Send the log to the configured log channel (if exists)
        if self.bot.guilds:
            guild = self.bot.guilds[0]
            gc = await self.cfg_svc.get_guild_config(guild.id)
            if gc:
                log_cfg = await self.cfg_svc.get_log_channel(gc.comp)
                if log_cfg and log_cfg.channel_id:
                    channel = guild.get_channel(log_cfg.channel_id)
                    if isinstance(channel, discord.TextChannel):
                        try:
                            await channel.send(log_text)
                        except discord.Forbidden:
                            # Missing permission to send message
                            pass


async def setup(bot: commands.Bot):
    """
    Setup function to add this Cog to the bot.

    Args:
        bot (commands.Bot): The Discord bot instance.
    """
    cog = DMLogger(config_service = bot.config_service)
    cog.bot = bot  # type: ignore
    await bot.add_cog(cog)
