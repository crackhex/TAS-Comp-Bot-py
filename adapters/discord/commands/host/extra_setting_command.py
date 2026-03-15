"""
Extra setting Command
================

Module path
-----------
    src/adapters/discord/commands/host/extra_setting_command.py
"""
from typing import Optional

from discord import app_commands, Message
from discord.ext import commands

from adapters.discord.checks import host_only
from application.services.config_service import ConfigService

ALLOWED_CHOICES = [
    app_commands.Choice(name="True", value=1),
    app_commands.Choice(name="False", value=0),
]



class ExtraSettingCommand(commands.Cog):
    def __init__(self, cfg_svc: ConfigService) -> None:
        self.cfg_svc = cfg_svc


    @commands.hybrid_command(
        name="set-extra-setting",
        description="[Host] Sets the extra setting to True or False",
        usage="$/set-extra-setting <True/False>, [lower bound] [upper bound]",
        with_app_command=True,
    )
    @host_only()
    @app_commands.describe(enabled="Set the extra setting to True/False, and the lower and upper bound in %")
    @app_commands.choices(enabled=ALLOWED_CHOICES)
    async def set_extra_setting(
        self,
        ctx: commands.Context,
        *,
        enabled: app_commands.Choice[int],
        lower_bound: Optional[int] = None,
        upper_bound: Optional[int] = None,
    ) -> Message | None:
        """
        Persist and toggle the extra setting to True or False.

        Args:
            ctx (commands.Context): Invocation context.
            enabled (bool): Whether the setting is enabled or not
            lower_bound (int): Lower bound in %
            upper_bound (int): Upper bound in %
        """
        # 1) Make sure this guild is mapped to a competition
        gc = await self.cfg_svc.get_guild_config(ctx.guild.id)
        if not gc:
            return await ctx.send("Use `/set-comp` first to map this server to a competition.")

        # 2) Load current setting and update bounds
        current = await self.cfg_svc.get_extra_setting(gc.comp)

        # Update bounds if it's the case, else keep as it was, or set to default value
        lb = lower_bound if lower_bound is not None else (current.lower_bound if current else 8)
        ub = upper_bound if upper_bound is not None else (current.upper_bound if current else 1200)

        # Validate
        if lb <= 0 or ub <= 0 or lb > ub:
            return await ctx.send("❌ Invalid bounds. Provide positive % values with lower_bound <= upper_bound.")

        # 3) Persist in the configuration layer
        await self.cfg_svc.set_extra_setting(
            comp        = gc.comp,
            enabled     = bool(enabled.value),
            lower_bound = lb,
            upper_bound = ub,
            guild_id    = ctx.guild.id,
        )

        # 4) Acknowledge
        return await ctx.send(f"✅ The extra setting has been set to **{"True" if enabled.value else "False"}**, with "
                              f"bound [{lb}, {ub}] %.")


# --------------------------------------------------------------------------- #
# Extension setup                                                             #
# --------------------------------------------------------------------------- #
async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ExtraSettingCommand(bot.config_service))