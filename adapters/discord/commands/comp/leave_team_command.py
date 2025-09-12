"""
Leave Team Command
==================

Module path:
    src/adapters/discord/commands/comp/leave_team_command.py

Summary:
    Lets a member leave their current team. If the team would drop to a single
    member after the departure, the team is dissolved.

Responsibilities:
    - Validate that a competition is configured and a task is ongoing.
    - Ensure the task is a team collab task.
    - Find the caller's team and:
        • Dissolve it if it would fall to one member, or
        • Remove the caller from the team otherwise.
    - Refresh the public "Current Submissions" message.
"""

from discord.ext import commands

from adapters.discord.utils.submission_utils import refresh_submission_list
from application.services.team_service       import TeamService
from application.services.task_manager       import TaskManager
from application.services.config_service     import ConfigService


class LeaveTeamCommand(commands.Cog):
    """
    Cog exposing the `/leaveteam` command.

    Attributes:
        team_svc (TeamService): Team domain/application operations.
        task_mgr (TaskManager): Provides active/last task lookup.
        cfg_svc (ConfigService): Reads guild/competition configuration.
    """

    def __init__(
        self,
        team_svc:       TeamService,
        task_mgr:       TaskManager,
        config_svc:     ConfigService,
    ):
        self.team_svc       = team_svc
        self.task_mgr       = task_mgr
        self.cfg_svc        = config_svc

    @commands.command(
        name="leaveteam",
        usage = "$leaveteam",
        help = ("""
                Removes you from your team in a collab task. This dissolves your team & deletes your submission if you were in a team with only 1 other person.
    
                Parameters:
                    None
        """),
    )

    async def leave_team(self, ctx: commands.Context):
        """
        Remove the invoking user from their team (or dissolve the team if only two members).

        Flow:
            1) Ensure a competition is configured for this guild.
            2) Retrieve the active task
            3) Verify the competition is a team competition.
            4) Locate the caller's team.
            5) If team size is exactly 2, dissolve; otherwise remove the caller.
            6) Refresh the public submissions list.

        Args:
            ctx (commands.Context): The command invocation context.

        Returns:
            None. Sends feedback messages to the channel.
        """
        # 1) Guild must be configured
        gc = await self.cfg_svc.get_guild_config(ctx.guild.id)
        if not gc:
            return await ctx.send("There is no competition configured for this server. Please contact an admin.")

        # 2) Active task
        task = await self.task_mgr.get_active_task()
        if not task:
            return await ctx.send("There is no ongoing task!")

        # 3) Must be a team competition
        if task.team_size <= 1:
            return await ctx.send("This is not a collab task!")

        # 4) Find the caller's team
        team = await self.team_svc.get_team_by_member(ctx.author.id)
        if not team:
            return await ctx.send("You are already not in a team!")

        # 5) If the team would fall to 1 member, dissolve; else remove only the caller
        if len(team.members) == 2:
            # Remove submission if there is a submission
            try:
                await ctx.bot.submission_service.remove_submission(ctx.author.id)
            except RuntimeError:
                pass

            # Dissolve team
            await self.team_svc.dissolve_team(team.id)
            await ctx.send("Your team has been dissolved (there is no one left in it).")
        else:
            # Remove member
            await self.team_svc.remove_member(team.id, ctx.author.id)
            await ctx.send("You have left your team")

        # 6) Refresh the public submissions list
        return await refresh_submission_list(
            bot=    ctx.bot,
            cfg_svc=self.cfg_svc,
            guild=  ctx.guild,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(
        LeaveTeamCommand(
            team_svc=       bot.team_service,
            task_mgr=       bot.task_manager,
            config_svc=     bot.config_service,
        )
    )
