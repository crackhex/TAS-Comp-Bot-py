"""
Host Kick Command
==================

Module path:
    src/adapters/discord/commands/host/host_kick_command.py

Summary:
    Kick a competitor from their team. If the team would drop to a single
    member after the departure, the team is dissolved.

Responsibilities:
    - Validate that a competition is configured and a task is ongoing.
    - Ensure the task is a team collab task.
    - Find the given member's team and:
        • Dissolve it if it would fall to one member, or
        • Remove the competitor from the team otherwise.
    - Refresh the public "Current Submissions" message.
"""
import discord
from discord.ext import commands

from adapters.discord.utils.submission_utils import refresh_submission_list
from application.services.team_service import TeamService
from application.services.task_manager import TaskManager
from application.services.config_service import ConfigService


class HostKickCommand(commands.Cog):
    """
    Cog exposing the `/hostkick` command.

    Attributes:
        team_svc (TeamService): Team domain/application operations.
        task_mgr (TaskManager): Provides active/last task lookup.
        cfg_svc (ConfigService): Reads guild/competition configuration.
    """

    def __init__(
            self,
            team_svc: TeamService,
            task_mgr: TaskManager,
            config_svc: ConfigService,
    ):
        self.team_svc = team_svc
        self.task_mgr = task_mgr
        self.cfg_svc = config_svc

    @commands.hybrid_command(
        name="hostkick",
        description='[Host] Kick someone from their team during a collab task',
        usage="/hostkick <member>",
        help=("""
                Removes a given user from their team. If used on someone in a team with only 1 other person, this dissolves the team and deletes their submission.

                Parameters:
                    `member`: The competitor to remove from the team.
        """),
    )
    async def host_kick(self, ctx: commands.Context, member: discord.Member):
        """
        Remove the given user from their team (or dissolve the team if only two members).

        Flow:
            1) Ensure a competition is configured for this guild.
            2) Retrieve the active or last task
            3) Verify the competition is a team competition.
            4) If team size is exactly 2, dissolve; otherwise remove the competitor.
            5) Refresh the public submissions list.

        Args:
            ctx (commands.Context): The command invocation context.
            member (discord.Member): The competitor to kick.

        Returns:
            None. Sends feedback messages to the channel.
        """
        # 1) Guild must be configured
        gc = await self.cfg_svc.get_guild_config(ctx.guild.id)
        if not gc:
            return await ctx.send("There is no competition configured for this server. Please contact an admin.")

        # 2) Retrieve task
        task = await self.task_mgr.get_active_task() or await self.task_mgr.get_last_task()
        if not task:
            return await ctx.send("There is no ongoing task!")

        # 3) Must be a team competition
        if task.team_size <= 1:
            return await ctx.send("This is not a collab task!")

        # 4) Find the competitor's team
        team = await self.team_svc.get_team_by_member(member.id)
        if not team:
            return await ctx.send("This competitor is already not in a team!")

        # 5) If the team would fall to 1 member, dissolve; else remove only the given member
        if len(team.members) == 2:
            # Remove submission if there is a submission
            try:
                await ctx.bot.submission_service.remove_submission(ctx.author.id)
            except RuntimeError:
                pass

            # Dissolve team
            await self.team_svc.dissolve_team(team.id)
            await ctx.send(f"{member.display_name}'s team has been dissolved! (there is no one left in it).")
        else:
            # Remove member
            await self.team_svc.remove_member(team.id, member.id)
            await ctx.send(f"{member.display_name} has been kicked from their team!")

        # 6) Refresh the public submissions list
        return await refresh_submission_list(
            bot=ctx.bot,
            cfg_svc=self.cfg_svc,
            guild=ctx.guild,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(
        HostKickCommand(
            team_svc=bot.team_service,
            task_mgr=bot.task_manager,
            config_svc=bot.config_service,
        )
    )
