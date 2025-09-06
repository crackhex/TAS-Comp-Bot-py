"""
Speed-Task Configuration Commands
=================================

Module path:
    src/adapters/discord/commands/host/speed_task_config_commands.py

Summary:
    Host-only hybrid commands to configure Speed-Task parameters at runtime:
      - /speed-task-desc       → set the task description text
      - /speed-task-length     → set the Speed-Task duration (in hours)
      - /speed-task-reminders  → set up to four reminder moments (in minutes)

Responsibilities:
    - Validate that a competition is configured for the current guild.
    - Persist configuration through `ConfigService`.
"""

from discord.ext import commands
from discord.ext.commands import Greedy

from adapters.discord.checks import host_only
from application.services.config_service import ConfigService


class SpeedTaskConfigCommands(commands.Cog):
    """
    Hybrid commands to configure Speed-Task settings.

    Attributes:
        cfg_svc (ConfigService): Service used to load and persist configuration values.
    """

    def __init__(self, config_service: ConfigService):
        self.cfg_svc = config_service

    @commands.hybrid_command(
        name="speed-task-desc",
        description="[Host] Set the Speed-Task description text.",
        usage="$speed-task-desc <desc>",
        help=("""
            Set the task description for a speed task. This must be used before starting the speed task.

            Parameters:
                `desc`: The speed task description
        """),
        with_app_command=True,
    )
    @host_only()
    async def speed_task_desc(
        self,
        ctx: commands.Context,
        *,
        desc: str,
    ):
        """
        Set (or replace) the Speed-Task description for the guild's current competition.

        Steps:
            1) Ensure the guild has a configured competition.
            2) Save the description via `ConfigService`.
            3) Confirm to the user.

        Args:
            ctx (commands.Context): Invocation context.
            desc (str): The description text to store.

        Returns:
            None
        """
        # 1) Ensure a competition is configured for this guild
        gc = await self.cfg_svc.get_guild_config(ctx.guild.id)
        if not gc:
            return await ctx.send("There is no competition configured for this server. Use `/set-comp`.")

        # 2) Persist
        await self.cfg_svc.set_speed_task_desc(
            comp     = gc.comp,
            desc     = desc,
            guild_id = ctx.guild.id,
        )

        # 3) Feedback
        return await ctx.send(f"Succesfully set speed task text \n\n {desc}")

    @commands.hybrid_command(
        name="speed-task-length",
        description="[Host] Set the Speed-Task duration (in hours).",
        usage="$speed-task-length <hours>",
        help=("""
            Set the amount of time player have upon requesting the speed task (or when it's publicly revealed)

            Parameters:
                `length`: The speed task length, in hours.
        """),
        with_app_command=True,
    )
    @host_only()
    async def speed_task_length(
        self,
        ctx: commands.Context,
        hours: float,
    ):
        """
        Define the Speed-Task total duration in hours (must be > 0).

        Steps:
            1) Ensure the guild has a configured competition.
            2) Validate `hours`.
            3) Persist via `ConfigService`.
            4) Confirm to the user.

        Args:
            ctx (commands.Context): Invocation context.
            hours (float): Duration in hours (strictly positive).

        Returns:
            None
        """
        gc = await self.cfg_svc.get_guild_config(ctx.guild.id)
        if not gc:
            return await ctx.send("There is no competition configured for this server. Use `/set-comp`.")

        if hours <= 0:
            return await ctx.send("The length must be strictly positive.")

        await self.cfg_svc.set_speed_task_length(
            comp     = gc.comp,
            time     = hours,
            guild_id = ctx.guild.id,
        )

        return await ctx.send(f"The speed task length has been updated! → **{hours}** hour(s).")

    @commands.hybrid_command(
        name="speed-task-reminders",
        description="[Host] Set 1–4 reminder times (in minutes) before the speed task session ends.",
        usage="$speed-task-reminders <minutes>",
        help=("""
            Set up to 4 reminders times before the speed task session ends.

            Parameters:
                `minutes`: The reminders, which happens at X minutes before someone's deadline (or the general deadline).
                Separate the reminders by a space.
        """),
        with_app_command=True,
    )
    @host_only()
    async def speed_task_reminders(
        self,
        ctx: commands.Context,
        minutes: Greedy[int],
    ):
        """
        Configure up to four reminder moments (in minutes) before the personal or public deadline.

        Notes:
            - At least one reminder is required.
            - A maximum of four reminders is allowed.
            - All reminders must be strictly positive integers.
            - Reminders are stored sorted from largest to smallest.

        Steps:
            1) Ensure the guild has a configured competition.
            2) Validate input list.
            3) Sort and map to reminder1..reminder4.
            4) Persist via `ConfigService`.
            5) Confirm to the user.

        Args:
            ctx (commands.Context): Invocation context.
            minutes (Greedy[int]): 1–4 integers representing minutes before deadline.

        Returns:
            None
        """
        gc = await self.cfg_svc.get_guild_config(ctx.guild.id)
        if not gc:
            return await ctx.send("There is no competition configured for this server. Use `/set-comp`.")

        if not minutes:
            return await ctx.send("You must provide atleast 1 reminder (in minutes)")
        if len(minutes) > 4:
            return await ctx.send("Only up to 4 reminders is supported.")
        if any(m <= 0 for m in minutes):
            return await ctx.send("Your reminders must be strictly positive integers.")

        # Order from largest to smallest (e.g., 60, 30, 10, 5)
        m = sorted(minutes, reverse=True)
        r1 = m[0]
        r2 = m[1] if len(m) > 1 else None
        r3 = m[2] if len(m) > 2 else None
        r4 = m[3] if len(m) > 3 else None

        await self.cfg_svc.set_speed_task_reminders(
            comp       = gc.comp,
            reminder1  = r1,
            reminder2  = r2,
            reminder3  = r3,
            reminder4  = r4,
            guild_id   = ctx.guild.id,
        )

        list_of_reminders = ", ".join(f"{x}min" for x in m)
        await ctx.send(f"The speed task reminders have been set! → **{list_of_reminders}**.")


async def setup(bot: commands.Bot):
    """
    Register the SpeedTaskConfigCommands cog with the bot.

    Args:
        bot (commands.Bot): The bot instance.
    """
    await bot.add_cog(
        SpeedTaskConfigCommands(bot.config_service)
    )
