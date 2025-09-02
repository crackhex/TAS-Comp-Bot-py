"""
Teams Command
=============

Module path:
    src/adapters/discord/commands/comp/teams_command.py

Summary:
    Command that lists all confirmed teams for the current
    competition or, if none is active, the most recent one.

Responsibilities:
    - Resolve the active task or fall back to the last task.
    - Retrieve the set of confirmed teams via TeamService.
    - Render a readable list (team name if present, otherwise member list).
    - Post the list in-channel, suppressing mentions and embeds.
"""
from typing import List

from discord.ext import commands

from application.services.team_service import TeamService
from application.services.task_manager import TaskManager
from domain.entities import Team


class TeamsCommand(commands.Cog):
    """
    Cog providing the `/teams` command.

    Usage:
        /teams

    Attributes:
        team_svc (TeamService): Application service used to query teams.
        task_mgr (TaskManager): Service used to resolve the current or last task.
    """

    def __init__(
        self,
        team_service: TeamService,
        task_manager: TaskManager,
    ):
        self.team_svc  = team_service
        self.task_mgr  = task_manager

    @commands.hybrid_command(
        name="teams",
        description="List all confirmed teams for the current or last competition.",
        with_app_command=True,
    )
    async def teams(self, ctx: commands.Context):
        """
        List confirmed teams for the active competition, or the last one if none is active.

        Steps:
            1) Retrieve the active task
            2) Query all teams from TeamService.
            3) Format each entry as either:
               - `<index>. <team name> (<member1 & member2 & ...>)`, or
               - `<index>. <member1 & member2 & ...>` if the team has no name.
            4) Send the consolidated list in a single message.

        Args:
            ctx (commands.Context): Command invocation context.

        Returns:
            None

        Raises:
            Sends user-facing errors via ctx.send on validation or service failures.
        """
        # 1) Retrieve active task, and verify if it's a collab task
        task = await self.task_mgr.get_active_task()
        if not task or task.team_size < 2:
            return await ctx.send("There is not an ongoing collab task!")

        # 2) Retrieve teams
        try:
            teams: List[Team] = await self.team_svc.get_all_teams()
        except Exception as exc:
            return await ctx.send(f"Internal error: {exc}")

        # 3) No teams
        if not teams:
            return await ctx.send("No confirmed teams for this task yet.")

        # 4) Build display lines (team name if present, otherwise member list)
        lines: List[str] = []
        for idx, team in enumerate(teams, start=1):
            members = " & ".join(u.display_name for u in team.members)
            if team.name:
                line = f"{idx}. {team.name} ({members})"
            else:
                line = f"{idx}. {members}"
            lines.append(line)

        # 5) Send message
        header = "__**Confirmed teams:**__\n"
        body   = "\n".join(lines)
        return await ctx.send(header + body)


async def setup(bot: commands.Bot) -> None:
    """
    Register the TeamsCommand cog.

    Args:
        bot (commands.Bot): The bot instance exposing application services.
    """
    await bot.add_cog(
        TeamsCommand(
            team_service= bot.team_service,
            task_manager= bot.task_manager,
        )
    )
