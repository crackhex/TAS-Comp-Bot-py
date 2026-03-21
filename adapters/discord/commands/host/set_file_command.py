"""
Set File Command
================

Module path
-----------
    src/adapters/discord/commands/host/set_file_command.py

Summary:
    Host-only hybrid command that chooses one file extension (and therefore one
    parsing strategy) to accept for all submissions of the current competition.


Responsibilities:
    - Ensure the guild is already mapped to a competition with `/set-comp`.
    - Persist the new extension in the configuration tables.
    - Swap the parsing strategy
"""

from __future__ import annotations


from discord import app_commands, Message
from discord.ext import commands

from adapters.discord.checks import host_only
from application.parsers.registry import EXTENSION_STRATEGIES
from application.parsers.null_parser_strategy  import NullParserStrategy
from application.services.config_service import ConfigService

# --------------------------------------------------------------------------- #
# Map extensions → concrete strategy classes.                                 #
# This is to be extended by third party comps (sm64, nsmbw, etc)              #
# --------------------------------------------------------------------------- #


ALLOWED_CHOICES = [
    app_commands.Choice(name=f".{ext}", value=ext) for ext in EXTENSION_STRATEGIES
]


class SetFileCommand(commands.Cog):
    def __init__(self, cfg_svc: ConfigService) -> None:
        self.cfg_svc = cfg_svc


    @commands.hybrid_command(
        name="set-file",
        description="[Host] Define the file extension accepted for submissions.",
        usage="$/set-file <ext>",
        help=("""
            Sets the file extension accepted for submissions.

            Parameters:
                `ext`: The file extension that will be accepted for submissions. For Mario Kart Wii, this is rkg and rksys.
    """),
        with_app_command=True,
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
            One of the allowed extensions ("rkg", "dat", "zip", etc)
        """
        # 1) Make sure this guild is mapped to a competition
        gc = await self.cfg_svc.get_guild_config(ctx.guild.id)
        if not gc:
            return await ctx.send("Use `/set-comp` first to map this server to a competition.")

        # 2) Persist in the configuration layer
        await self.cfg_svc.set_submission_file_extension(
            comp     = gc.comp,
            ext      = ext.value,
            guild_id = ctx.guild.id,
        )

        # 3) Swap the strategy
        StrategyClass = EXTENSION_STRATEGIES.get(ext.value, NullParserStrategy)
        ctx.bot.file_parser.set_strategy(StrategyClass())

        # 4) Acknowledge
        return await ctx.send(f"✅ Accepted submission file extension set to **.{ext.value}**")


# --------------------------------------------------------------------------- #
# Extension setup                                                             #
# --------------------------------------------------------------------------- #
async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SetFileCommand(bot.config_service))
