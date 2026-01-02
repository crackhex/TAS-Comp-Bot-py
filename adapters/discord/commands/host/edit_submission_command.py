"""
Edit Submission Command
=======================

Module path:
    src/adapters/discord/commands/host/edit_submission_command.py

Summary:
    Host-only hybrid command to update an existing submission's recorded time
    and/or disqualification state, even after the competition has closed.

Responsibilities:
    - Validate guild configuration and retrieve the relevant competition
      (active or, if none, the most recent).
    - Enforce that a DQ update provides a reason.
    - Delegate updates to SubmissionService.edit_submission.
    - Notify affected competitor(s) by DM.
"""
import discord
from typing import Optional
from discord.ext import commands

from adapters.discord.checks import host_only
from application.services.task_manager       import TaskManager
from application.services.config_service     import ConfigService


def _format_time(seconds: Optional[float]) -> str:
    """Format seconds -> M:SS.mmm (or placeholder if missing)."""
    if seconds is None or seconds <= 0:
        return "??:??.???"
    m = int(seconds // 60)
    s = seconds - m * 60
    return f"{m}:{s:06.3f}"


class EditSubmissionCommand(commands.Cog):
    """
    Cog providing the `/edit-submission` command.

    Usage:
        /edit-submission @user <new_time: float> <dq: bool> [dq_reason]

    Attributes:
        task_mgr (TaskManager): Service to resolve the active or last competition.
        cfg_svc  (ConfigService): Service to query guild-level configuration.
    """

    def __init__(
        self,
        task_mgr:       TaskManager,
        config_svc:     ConfigService,
    ):
        self.task_mgr = task_mgr
        self.cfg_svc  = config_svc

    @commands.hybrid_command(
        name="edit-submission",
        description="[Host] Modify a submission (time and/or DQ status).",
        usage="/edit-submission <member> <new_time> <dq> [dq_reason]",
        help=("""
            Edits a competitor's submission. Notifies the competitor of the change, as well as their teammates if in a team.

            Parameters:
                `member`: Target competitor whose submission is edited.
                `new_time`: New run time (in seconds. e.g. for 1:20.456, write 80.456).
                `dq`: Whether (True/False) the submission is disqualified.
                `dq_reason`: Reason for DQ (required when dq=True).
            """),
        with_app_command=True,
    )
    @host_only()
    async def edit_submission(
        self,
        ctx: commands.Context,
        member: discord.Member,
        new_time: float,
        dq: bool,
        *,
        dq_reason: Optional[str] = None,
    ):
        """
        Update the specified competitor's submission.

        Steps:
            1) Ensure this guild is configured for a competition.
            2) Resolve the active task or, if none, the most recent task.
            3) If setting DQ to True, require a non-empty reason.
            4) Capture the current submission for summary purposes.
            5) Delegate to SubmissionService.edit_submission.
            6) DM the affected competitor(s) with the change summary.
            7) Confirm in-channel with a concise “old → new” summary.

        Args:
            ctx (commands.Context): Command invocation context.
            member (discord.Member): Target competitor whose submission is edited.
            new_time (float): New run time (in seconds).
            dq (bool): Whether the submission is disqualified.
            dq_reason (Optional[str]): Reason for DQ (required when dq=True).

        Returns:
            None
        """
        # 1) Guild configuration must exist
        gc = await self.cfg_svc.get_guild_config(ctx.guild.id)
        if not gc:
            return await ctx.send("There is no competition configured for this server. Use `/set-comp`.")

        # 2) Resolve active or last task
        task = await self.task_mgr.get_active_task()
        if not task:
            task = await self.task_mgr.get_last_task()
        if not task:
            return await ctx.send("No active or past task was found.")

        # 3) DQ requires a reason
        if dq and not dq_reason:
            return await ctx.send("Please specify a DQ reason!")

        # 4) Capture the current submission (for summary) by scanning submission table
        old_sub = None
        try:
            all_subs = await ctx.bot.submission_service.get_submissions()
            for s in all_subs:
                if s.team:
                    if any(m.discord_id == member.id for m in s.team.members):
                        old_sub = s
                        break
                else:
                    if s.submitted_by.discord_id == member.id:
                        old_sub = s
                        break
        except Exception:
            # If we can't load it for summary, we still proceed with the edit.
            old_sub = None

        old_time = old_sub.time if old_sub else None
        old_dq   = bool(old_sub.dq) if old_sub else None

        # 5) Apply the edit via the submission service
        try:
            submission = await ctx.bot.submission_service.edit_submission(
                user_id=member.id,
                new_time=new_time,
                dq=dq,
                dq_reason=dq_reason,
            )

        # This catches errors such as if the specified member hasn't submitted.
        except Exception as exc:
            return await ctx.send(f"Error while modifying submission: {exc}")

        # 6) Notify the competitor(s) via DM (team or solo)
        dm_message = (
            f"🏁 Your submission for Task **{submission.task.number}, {submission.task.year}** has been updated by a host:\n"
            f"• Time: **{_format_time(new_time)}**\n"
            f"• DQ: {'Yes' if dq else 'No'}"
        )
        if dq and dq_reason:
            dm_message += f"\n• DQ Reason: {dq_reason}"

        targets = []
        if submission.team:
            # Team: notify every member
            for u in submission.team.members:
                user_obj = ctx.bot.get_user(u.discord_id) or await ctx.bot.fetch_user(u.discord_id)
                targets.append(user_obj)
        else:
            # Solo: notify the one competitor
            user_obj = ctx.bot.get_user(member.id) or await ctx.bot.fetch_user(member.id)
            targets.append(user_obj)

        for user_obj in targets:
            try:
                await user_obj.send(dm_message)
            except discord.Forbidden:
                await ctx.send(f"Couldn't notify {user_obj.id}.")

        # 7) Confirmation with “old -> new” summary
        lines = [f"Successfully edited **{member.display_name}**’s submission:"]

        # Time summary
        if old_time is not None:
            lines.append(f"• Time: {_format_time(old_time)} → **{_format_time(submission.time)}**")
        else:
            lines.append(f"• Time: **{_format_time(submission.time)}**")
        # DQ summary
        if old_dq is not None and old_dq != submission.dq:
            if submission.dq:
                # Became DQ
                reason_txt = f" ({submission.dq_reason})" if submission.dq_reason else ""
                lines.append(f"• DQ: False → **True**{reason_txt}")
            else:
                # DQ removed
                lines.append("• DQ: True → **False**")
        else:
            lines.append(f"• DQ: **{'True' if submission.dq else 'False'}**")

        return await ctx.send("\n".join(lines))


async def setup(bot: commands.Bot):
    """
    Register the EditSubmissionCommand cog.

    Args:
        bot (commands.Bot): The bot instance exposing application services.
    """
    await bot.add_cog(
        EditSubmissionCommand(
            task_mgr=      bot.task_manager,
            config_svc=    bot.config_service,
        )
    )
