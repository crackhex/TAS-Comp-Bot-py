"""
Info / Status Command
=====================

Module path:
    src/adapters/discord/commands/info_command.py

Summary:
    Direct-message command that lets a competitor query the details of their
    current submission, whether it is a solo run or a team run.

The command is competition-agnostic:

* Common fields (time, URL, upload date, DQ) are always shown.
* Extra fields (character / vehicle) are included **only** when present in the
  underlying SubmissionFile entity (e.g. Mario Kart Wii).
"""
from __future__ import annotations

import discord
from discord.ext import commands

from adapters.discord.utils.time_format import fmt_time


def pad_row(embed: discord.Embed) -> None:
    """Add an invisible 3rd column so this row owns exactly 3 inline cells."""
    embed.add_field(name="\u200b", value="\u200b", inline=True)  # zero-width pad

# --------------------------------------------------------------------------- #
# MKW-specific lookup tables (used only when the submission has those attrs)  #
# --------------------------------------------------------------------------- #
MKW_CHARACTERS = {
    0: "Mario",
    1: "Baby Peach",
    2: "Waluigi",
    3: "Bowser",
    4: "Baby Daisy",
    5: "Dry Bones",
    6: "Baby Mario",
    7: "Luigi",
    8: "Toad",
    9: "Donkey Kong",
    10: "Yoshi",
    11: "Wario",
    12: "Baby Luigi",
    13: "Toadette",
    14: "Koopa Troopa",
    15: "Daisy",
    16: "Peach",
    17: "Birdo",
    18: "Diddy Kong",
    19: "King Boo",
    20: "Bowser Jr.",
    21: "Dry Bowser",
    22: "Funky Kong",
    23: "Rosalina",
    24: "Small Mii Outfit A (Male)",
    25: "Small Mii Outfit A (Female)",
    26: "Small Mii Outfit B (Male)",
    27: "Small Mii Outfit B (Female)",
    28: "Small Mii Outfit C (Male)",
    29: "Small Mii Outfit C (Female)",
    30: "Medium Mii Outfit A (Male)",
    31: "Medium Mii Outfit A (Female)",
    32: "Medium Mii Outfit B (Male)",
    33: "Medium Mii Outfit B (Female)",
    34: "Medium Mii Outfit C (Male)",
    35: "Medium Mii Outfit C (Female)",
    36: "Large Mii Outfit A (Male)",
    37: "Large Mii Outfit A (Female)",
    38: "Large Mii Outfit B (Male)",
    39: "Large Mii Outfit B (Female)",
    40: "Large Mii Outfit C (Male)",
    41: "Large Mii Outfit C (Female)",
    42: "Medium Mii",
    43: "Small Mii",
    44: "Large Mii",
    45: "Peach Biker Outfit",
    46: "Daisy Biker Outfit",
    47: "Rosalina Biker Outfit",
}
MKW_VEHICLES = {
    0: "Standard Kart S",
    1: "Standard Kart M",
    2: "Standard Kart L",
    3: "Baby Booster",
    4: "Classic Dragster",
    5: "Offroader",
    6: "Mini Beast",
    7: "Wild Wing",
    8: "Flame Flyer",
    9: "Cheep Charger",
    10: "Super Blooper",
    11: "Piranha Prowler",
    12: "Rally Romper",
    13: "Daytripper",
    14: "Jetsetter",
    15: "Blue Falcon",
    16: "Sprinter",
    17: "Honeycoupe",
    18: "Standard Bike S",
    19: "Standard Bike M",
    20: "Standard Bike L",
    21: "Bullet Bike",
    22: "Mach Bike",
    23: "Flame runner",
    24: "Bit Bike",
    25: "Sugarscoot",
    26: "Wario Bike",
    27: "Quacker",
    28: "Zip Zip",
    29: "Shooting Star",
    30: "Magikruiser",
    31: "Sneakster",
    32: "Spear",
    33: "Jet Bubble",
    34: "Dolphin Dasher",
    35: "Phantom",
}


class InfoCommand(commands.Cog):
    """DM-only command that returns an embed with the user’s / team’s submission."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot


    @commands.command(
        name="info",
        aliases=["status"],
        usage = "$info",
        help = ("""
                Shows information about your submission, e.g. time, upload date, DQ status, etc. This is a DM only command. 
    
                Parameters:
                None.
        """),

    )
    @commands.dm_only()
    async def info(self, ctx: commands.Context) -> None:
        """Reply with an embed describing the current submission."""
        user_id           = ctx.author.id
        submission_svc    = self.bot.submission_service
        team_svc          = self.bot.team_service
        task_mgr          = self.bot.task_manager
        cfg_svc           = self.bot.config_service

        # 1) Retrieve task
        task = await task_mgr.get_active_task() or await task_mgr.get_last_task()
        if task is None:
            await ctx.reply("There is no active or historical task.")
            return

        # 2) solo or team?
        team = None
        if task.team_size > 1 and not task.speed_task:
            team = await team_svc.get_team_by_member(user_id)

        # 3) submission lookup
        submissions = await submission_svc.get_submissions()
        sub = next(
            (
                s for s in submissions
                if (team and s.team and s.team.id == team.id)
                or (s.submitted_by.discord_id == user_id)
            ),
            None,
        )
        if sub is None:
            await ctx.reply("You (or your team) have not submitted yet.")
            return

        embed = discord.Embed(
            title=f"Task {sub.task.number} submission",
            colour=discord.Colour.green(),
        )

        # row 0  – file
        embed.add_field(name="File", value=sub.url or "(no URL)", inline=False)

        # row 1  – Time │ Uploaded │
        embed.add_field(name="Time", value=fmt_time(sub.time), inline=True)
        uploaded = (
            f"<t:{sub.file.uploaded_at}:F>"
            if sub.file and sub.file.uploaded_at else "unknown"
        )
        embed.add_field(name="Uploaded", value=uploaded, inline=True)
        pad_row(embed)

        # row 2  – Character │ Vehicle │
        embed.add_field(
            name="Character",
            value=MKW_CHARACTERS.get(int(sub.character), f"ID {sub.character}")
            if getattr(sub, "character", None) is not None else "—",
            inline=True,
        )
        embed.add_field(
            name="Vehicle",
            value=MKW_VEHICLES.get(int(sub.vehicle), f"ID {sub.vehicle}")
            if getattr(sub, "vehicle", None) is not None else "—",
            inline=True,
        )
        pad_row(embed)

        # row 3  – DQ │ DQ reason │
        embed.add_field(name="DQ", value=str(bool(sub.dq)), inline=True)
        embed.add_field(
            name="DQ reason",
            value=sub.dq_reason if sub.dq and sub.dq_reason else "—",
            inline=True,
        )
        pad_row(embed)


        # Retrieve guild (to get server icon)
        guild_list = await cfg_svc.list_guild_configs()
        guild_id = guild_list[0].guild_id
        guild = self.bot.get_guild(guild_id)

        embed.set_footer(text="TAS Competition Info", icon_url=guild.icon.url if guild.icon else None)

        await ctx.reply(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(InfoCommand(bot))
