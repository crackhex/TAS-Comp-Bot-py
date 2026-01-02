"""
Credits command
===================

Module path:
    src/adapters/discord/commands/credits_command.py

Summary:
    Display the list of contributors to the TAS Comp Bot project.

"""
import discord
from discord.ext import commands


class CreditsCommand(commands.Cog):
    """
    Gives a rundown on the contributors of this bot.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # All the category texts
        self.credits = """
        **TASCompBot** is a multi TAS-Comp bot, that will be supporting MKW, SM64 and NSMBW TAS Comp, and maybe even more in the future.
        
        This bot is in continuous development, and as such, the credits may be expanded over time.
        Here is the list of contributors to this project:
        
          ### Project lead
          **kierio04** — Supervising the development of bot, giving feedback & ideas, helping with tests, managing the github repo, and more
        
          ### Developers
          **DashQC** — Overall bot structure, competition structure, general & MKW submission handling, host/admin commands, fun commands, event handling,
          database.
          **Crackhex** — Overall bot structure, and SM64 specific features
          **shxd** — Competition structure, MKW submission handling, [now-removed] economy, helped with commands
          **Aurumaker72** — SM64 encoding of .m64 files to mp4
          **slither** — SM64 features, and helping with some of the [now-removed] fun commands
          **TomCube** — NSMBW submission handling
          
          ### Testers
          All the developers
          kierio04
          Gaberboo
          LirWm
          
          You can check the public GitHub repo [here](https://github.com/crackhex/TAS-Comp-Bot-py).
          
          This bot is a fork of the original [TAS-Comp-Bot](https://github.com/bxrru/TAS-Comp-Bot) by bxrru, ERGC | Xander, Eddio0141, slither, Aurumaker72, icecream17, tjk113, and Skazzy3
            """

    @commands.command(name="credits")
    async def credits(self, ctx: commands.Context):
        """
            Builds an embed with the list of contributors, and their contributions.
        """
        embed = discord.Embed(
            title=f"© Credits",
            description=self.credits,
            colour=discord.Colour.gold()
        )

        # Retrieve guild (to get server icon)
        guild_list = await ctx.bot.config_service.list_guild_configs()
        guild_id = guild_list[0].guild_id
        guild = self.bot.get_guild(guild_id)

        embed.set_footer(text="TASCompBot - A Multi TAS Comp Bot", icon_url=guild.icon.url if guild.icon else None)
        return await ctx.send(embed=embed)



async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CreditsCommand(bot))
