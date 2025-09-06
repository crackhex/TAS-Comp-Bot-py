"""
Set-Deadline Command
====================

Module path:
    src/adapters/discord/commands/host/set_deadline_command.py

Summary:
    Host-only command to update the active competition's deadline
    using a UNIX timestamp.

Responsibilities:
    - Validate that a task is currently active.
    - Ensure the provided timestamp is in the future.
    - Delegate the update to `TaskManager.set_deadline`.
"""

import time
from discord.ext import commands

from adapters.discord.checks import host_only
from application.services.task_manager import TaskManager


class SetDeadlineCommand(commands.Cog):
    """
    Hybrid command cog to change the active competition's absolute deadline.

    Attributes:
        task_manager (TaskManager): Application service that manages task lifecycle.
    """

    def __init__(self, task_manager: TaskManager):
        self.task_manager = task_manager

    @commands.hybrid_command(
        name="set-deadline",
        description="[Host] Change the active competition's deadline (UNIX)",
        usage="$/set-deadline <deadline>",
        help=("""
            Change the deadline of the competition.

            Parameters:
                `deadline`: UNIX timestamp of the new deadline. Use https://www.hammertime.cyou
    """),
        with_app_command=True,
    )
    @host_only()
    async def set_deadline(
        self,
        ctx: commands.Context,
        new_deadline: int,  # UNIX
    ):
        """
        Update the active competition's deadline.

        Steps:
            1) Verify that a competition is active.
            2) Validate that `new_deadline` is in the future.
            3) Apply the change via `TaskManager.set_deadline`.
            4) Confirm to the user using Discord's timestamp formatting.

        Args:
            ctx (commands.Context): Invocation context.
            new_deadline (int): UNIX timestamp for the new deadline.

        Returns:
            None
        """
        # 1) Ensure a task is active
        task = await self.task_manager.get_active_task()
        if not task:
            return await ctx.send("There is no ongoing task!")

        # 2) Validate the timestamp is in the future
        now = int(time.time())
        if new_deadline <= now:
            return await ctx.send("The updated deadline must be in the future!")

        # 3) Persist the new deadline via the task manager service
        try:
            await self.task_manager.set_deadline(new_deadline)
        except Exception as exc:
            return await ctx.send(f"Couldn't update deadline due to error: {exc}")

        # 4) User-friendly confirmation (Discord renders <t:...:F>)
        return await ctx.send(f"The deadline has been updated! → <t:{new_deadline}:F>.")


async def setup(bot: commands.Bot):
    """
    Register the SetDeadlineCommand cog.

    Args:
        bot (commands.Bot): The bot instance.
    """
    await bot.add_cog(SetDeadlineCommand(bot.task_manager))
