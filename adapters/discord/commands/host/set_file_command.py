"""
Set File Command
================

Module path
-----------
    src/adapters/discord/commands/host/set_file_command.py

Summary:
    Host-only hybrid command that chooses one file extension (and therefore one
    parsing strategy) to accept for all submissions of the current competition
    (“comp”).


Responsibilities:
    - Ensure the guild is already mapped to a competition with `/set-comp`.
    - Persist the new extension in the configuration tables.
    - Swap the  parsing strategy
"""

from __future__ import annotations

from typing import Dict, Type

from discord import app_commands, Message
from discord.ext import commands

from adapters.discord.checks import host_only
from application.parsers.rkg_parser   import RkgParser
from application.parsers.rksys_parser import RksysParser
from application.parsers.null_parser  import NullParser
from application.parsers.parser_strategy import ParserStrategy
from application.services.config_service import ConfigService

# --------------------------------------------------------------------------- #
# Map extensions → concrete strategy classes.                                 #
# This is to be extended by third party comps (sm64, nsmbw, etc)              #
# --------------------------------------------------------------------------- #
EXTENSION_STRATEGIES: Dict[str, Type[ParserStrategy]] = {
    "rkg":   RkgParser,
    "rksys": RksysParser,
}

ALLOWED_CHOICES = [
    app_commands.Choice(name=f".{ext}", value=ext) for ext in EXTENSION_STRATEGIES
]


class SetFileCommand(commands.Cog):
    def __init__(self, cfg_svc: ConfigService) -> None:
        self.cfg_svc = cfg_svc


    @commands.hybrid_command(
        name="set-file",
        description="[Host] Define the file extension accepted for submissions.",
    )
    @host_only()
    @app_commands.describe(ext="Choose the extension")
    @app_commands.choices(ext=ALLOWED_CHOICES)
    async def set_file(
        self,
        ctx: commands.Context,
        *,
        ext: app_commands.Choice[str],
    ) -> Message | None:
        """
        Persist the chosen extension **and** swap the live parser.

        Parameters
        ----------
        ctx :
            Invocation context
        ext :
            One of the allowed extensions (“rkg”, “rksys”, ...)
        """
        # 1) Make sure this guild is mapped to a competition
        gc = await self.cfg_svc.get_guild_config(ctx.guild.id)
        if not gc:
            return await ctx.send("Use `/set-comp` first to map this server to a competition.")

        # 2) Persist in the configuration layer
        await self.cfg_svc.set_submission_file_extension(
            comp=gc.comp,
            ext=ext.value,
            guild_id=ctx.guild.id,
        )

        # 3) Swap the strategy
        StrategyClass = EXTENSION_STRATEGIES.get(ext.value, NullParser)
        ctx.bot.file_parser.set_strategy(StrategyClass())

        # 4) Acknowledge
        await ctx.send(f"✅ Accepted submission file extension set to **.{ext.value}**")

    # --------------------------------------------------------------------- #
    # Error handling                                                        #
    # --------------------------------------------------------------------- #
    @set_file.error
    async def on_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        await ctx.send(f"❌ {error}")


# --------------------------------------------------------------------------- #
# Extension setup                                                             #
# --------------------------------------------------------------------------- #
async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SetFileCommand(bot.config_service))
