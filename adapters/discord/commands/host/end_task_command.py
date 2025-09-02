"""
End Task Command
================

Module path:
    src/adapters/discord/commands/host/end_task_command.py

Summary:
    Host-only hybrid command that closes the currently active competition.
    This means the bot is no longer accepting submissions.

Responsibilities:
    - Verify that a task is currently active.
    - Invoke TaskManager.end_task to close it.
    - Acknowledge the action to the invoking user.
"""
from discord.ext import commands
from application.services.task_manager import TaskManager
from adapters.discord.checks import host_only


class EndTaskCommand(commands.Cog):
    """
    Cog providing the `/end-task` command.

    Attributes:
        task_manager (TaskManager): Application service handling task lifecycle.
    """

    def __init__(self, task_manager: TaskManager):
        self.task_manager = task_manager

    @commands.hybrid_command(
        name="end-task",
        description="[Host] Close the active task."
    )
    @host_only()
    async def end_task(self, ctx: commands.Context):
        """
        Close the currently active competition.

        Steps:
            1) Retrieve the active task; abort if none exists.
            2) Call TaskManager.end_task with the active task ID.
            3) Confirm closure to the user.

        Args:
            ctx (commands.Context): Invocation context.

        Returns:
            None
        """
        # 1) Retrieve active task
        task = await self.task_manager.get_active_task()
        if not task:
            return await ctx.send("There is already no ongoing task!")

        # 2) Close it via the task manager
        await self.task_manager.end_task(task.id)

        # 3) Confirm to the user
        return await ctx.send(f"Succesfully ended **Task {task.number}, {task.year}**")


async def setup(bot: commands.Bot):
    """
    Register the EndTaskCommand cog.

    Args:
        bot (commands.Bot): The bot instance.
    """
    await bot.add_cog(EndTaskCommand(bot.task_manager))
