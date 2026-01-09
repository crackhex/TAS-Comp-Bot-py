"""
Funny Setting One Command
================

Module path
-----------
    src/adapters/discord/commands/host/funny_setting_command.py

Summary:
    Host-only hybrid command that [redacted]


Responsibilities:
    - Secret
"""
from discord import app_commands, Message
from discord.ext import commands

from adapters.discord.checks import host_only
from application.services.config_service import ConfigService

ALLOWED_CHOICES = [
    app_commands.Choice(name="True", value=1),
    app_commands.Choice(name="False", value=0),
]



class FunnySettingOneCommand(commands.Cog):
    def __init__(self, cfg_svc: ConfigService) -> None:
        self.cfg_svc = cfg_svc


    @commands.hybrid_command(
        name="set-funny-setting-one",
        description="[Host] Sets a funny setting to True or False",
        usage="$/set-funny-setting-one <True/False>",
        with_app_command=True,
    )
    @host_only()
    @app_commands.describe(enabled="Set the funny setting one to True/False")
    @app_commands.choices(enabled=ALLOWED_CHOICES)
    async def set_funny_setting_one(
        self,
        ctx: commands.Context,
        *,
        enabled: app_commands.Choice[int],
    ) -> Message | None:
        """
        Persist and toggle the funny setting to True or False.

        Parameters
        ----------
        ctx :
            Invocation context
        enabled :
            Boolean flag to enable or disable the funny setting.
        """
        # 1) Make sure this guild is mapped to a competition
        gc = await self.cfg_svc.get_guild_config(ctx.guild.id)
        if not gc:
            return await ctx.send("Use `/set-comp` first to map this server to a competition.")

        # 2) Persist in the configuration layer
        await self.cfg_svc.set_funny_setting_one(
            comp     = gc.comp,
            enabled  = bool(enabled.value),
            guild_id = ctx.guild.id,
        )

        # 3) Acknowledge
        return await ctx.send(f"✅ The funny setting 1 has been set to **{"True" if enabled.value else "False"}**.")


# --------------------------------------------------------------------------- #
# Extension setup                                                             #
# --------------------------------------------------------------------------- #
async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FunnySettingOneCommand(bot.config_service))