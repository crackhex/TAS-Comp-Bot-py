"""
Delete Submission Command
=========================

Module path:
    src/adapters/discord/commands/host/delete_submission_command.py

Summary:
    Host-only hybrid command that removes a competitor’s submission (solo or team),
    refreshes the public submission list, and strips the “submitted” role from the
    affected user(s).

Responsibilities:
    - Validate that a competition is configured for the guild.
    - Resolve the active task or, if none, the last task.
    - Delegate deletion to SubmissionService.remove_submission.
    - Refresh the public “Current Submissions” message.
    - Remove the configured “submitted” role from the user or the whole team.
"""
import discord
from discord.ext import commands

from adapters.discord.checks                       import host_only
from adapters.discord.utils.submission_utils       import refresh_submission_list
from adapters.discord.utils.role_utils             import remove_role_from_member
from application.services.config_service           import ConfigService
from application.services.task_manager             import TaskManager


class DeleteSubmissionCommand(commands.Cog):
    """
    Cog providing the `/delete-submission` command.

    Usage:
        /delete-submission @user

    Attributes:
        cfg_svc  (ConfigService): Service to access guild-level configuration.
        task_mgr (TaskManager): Service to resolve active/last tasks.
    """

    def __init__(
        self,
        config_svc:     ConfigService,
        task_mgr:       TaskManager,
    ):
        self.cfg_svc  = config_svc
        self.task_mgr = task_mgr

    @commands.hybrid_command(
        name="delete-submission",
        description="[Host] Delete a competitor's (or team) submission.",
        usage="/delete-submission <Member>",
        help=("""
        Deletes a submission. This removes it from the database and submission list.

        Parameters:
            `Member`: The competitor whose submission will be deleted.
        """),
        with_app_command=True,
    )
    @host_only()
    async def delete_submission(
        self,
        ctx: commands.Context,
        member: discord.Member,
    ):
        """
        Remove the specified member’s submission (solo or team).

        Steps:
            1) Ensure the guild has an associated competition.
            2) Resolve the active task or, failing that, the most recent task.
            3) Remove the submission via SubmissionService.remove_submission.
            4) Refresh the public submission list message.
            5) Remove the “submitted” role from the user or all team members.
            6) Acknowledge success.

        Args:
            ctx (commands.Context): Invocation context.
            member (discord.Member): The competitor whose submission should be removed.

        Returns:
            None

        Raises:
            Sends user-facing errors via ctx.send on validation or service failures.
        """
        # 1) Validate guild configuration
        gc = await self.cfg_svc.get_guild_config(ctx.guild.id)
        if not gc:
            return await ctx.send("There is no competition configured for this server. Use `/set-comp`.")

        # 2) Resolve active or last task (needed for user-facing messaging)
        task = await self.task_mgr.get_active_task()
        if not task:
            task = await self.task_mgr.get_last_task()
        if not task:
            return await ctx.send("There is no active (or last) task.")

        # 3) Delete the submission via the service
        try:
            # remove_submission returns the deleted Submission entity
            submission = await ctx.bot.submission_service.remove_submission(user_id=member.id)
        except Exception as exc:
            return await ctx.send(f"Unable to delete submission: {exc}")

        # 4) Refresh the public submission list
        await refresh_submission_list(
            bot=    ctx.bot,
            cfg_svc=self.cfg_svc,
            guild=  ctx.guild,
        )

        # 5) Remove the “submitted” role
        submit_cfg = await self.cfg_svc.get_submitter_role(gc.comp)
        if submit_cfg and submit_cfg.role_id:
            # If it was a team submission, remove from all members
            if submission.team:
                for u in submission.team.members:
                    await remove_role_from_member(ctx.guild, u.discord_id, submit_cfg.role_id)
            else:
                # Solo case
                await remove_role_from_member(ctx.guild, member.id, submit_cfg.role_id)

        # 6) Confirmation
        return await ctx.send(f"Submission for {member.mention} has been deleted successfully.")


async def setup(bot: commands.Bot):
    """
    Register the DeleteSubmissionCommand cog.

    Args:
        bot (commands.Bot): The bot instance exposing application services.
    """
    await bot.add_cog(
        DeleteSubmissionCommand(
            config_svc=    bot.config_service,
            task_mgr=      bot.task_manager,
        )
    )
