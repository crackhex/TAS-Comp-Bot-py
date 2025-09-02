"""
Get Submissions Command
=======================

Module path:
    src/adapters/discord/commands/host/get_submissions_command.py

Summary:
    Host-only command that lists submissions for the active task
    or the most recent task if it is past deadline. Discord's 2000
    characters limit is taken into account.

Responsibilities:
    - Resolve the active task (fallback to the last task if it's past deadline).
    - Fetch all submissions for that task via SubmissionService.
    - Split output into multiple messages under Discord size limits.
"""

import asyncio
from typing import List

import discord
from discord.ext import commands

from application.services.task_manager       import TaskManager
from adapters.discord.checks                 import host_only

MSG_LIMIT = 2_000
BUFFER    = 50


def fmt_time(run_time: float | None) -> str:
    """
    Format a run time (seconds as float) into `M:SS.mmm`.

    Args:
        run_time (float | None): Time in seconds, may be None.

    Returns:
        str: Human-readable time; "??:??.???" if missing or non-positive.
    """
    if not run_time or run_time <= 0:
        return "??:??.???"
    m, s = divmod(run_time, 60)
    ms = (s - int(s)) * 1000
    return f"{int(m)}:{int(s):02}.{int(ms):03}"


class GetSubmissionsCommand(commands.Cog):
    """
    Cog providing the `/get-submissions` host command.

    Attributes:
        task_mgr (TaskManager): Application service for task lifecycle and lookup.
    """

    def __init__(
        self,
        task_manager:       TaskManager,
    ):
        self.task_mgr = task_manager

    @commands.hybrid_command(
        name="get-submissions",
        description="[Host] Retrieves all submissions for the current task",
    )
    @host_only()
    async def get_submissions(self, ctx: commands.Context):
        """
        List all submissions for the active task or, if none is active,
        for the most recent task.

        Steps:
            1) Resolve active task, else last task; abort if none exist.
            2) Fetch submissions via service (already filtered by task).
            3) Sort by upload submission ID to preserve order of submissions
            4) Build formatted lines for solo/team entries.
            5) Chunk lines into messages under ~1950 chars.
            6) Send messages with a header on the first chunk.

        Args:
            ctx (commands.Context): Invocation context.

        Returns:
            None
        """
        # 1) Prefer active task; else fall back to last task
        task = await self.task_mgr.get_active_task()
        if not task:
            task = await self.task_mgr.get_last_task()
        if not task:
            return await ctx.send("There is no competition to retrieve submissions from.")

        # 2) Retrieve submissions for this task via submission service
        try:
            subs = await ctx.bot.submission_service.get_submissions()
        except Exception as exc:
            return await ctx.send(f"Internal error: {exc}")

        # 3) If there are no submissions
        if not subs:
            return await ctx.send(
                f"No one submitted to **Task {task.number}, {task.year}** :(")

        # 4) Sort by first submission ID
        subs.sort(key=lambda s: s.id)

        # 5) Build listing lines
        lines: List[str] = []
        for idx, sub in enumerate(subs, 1):
            if sub.team:
                members = " & ".join(m.display_name for m in sub.team.members)
                if sub.team.name and sub.team.name.strip():
                    who = f"{sub.team.name} ({members})"
                else:
                    who = members
            else:
                who = sub.submitted_by.display_name

            run_t = fmt_time(sub.time)
            ts    = f"<t:{sub.file.uploaded_at}:f>"
            lines.append(
                f"{idx}. {who} : {sub.file.path} – {ts} | "
                f"Fetched time: ||{run_t}||"
            )

        # 6) Chunk output to respect message length limits
        parts: List[str] = []
        current = ""
        for line in lines:
            # +1 accounts for the newline
            if len(current) + len(line) + 1 > MSG_LIMIT - BUFFER:
                parts.append(current)
                current = ""
            current += line + "\n"
        if current:
            parts.append(current)

        # 7) Send output
        header = (
            f"__**Task {task.number} submissions**__:\n"
            f"-# (Total submissions: {len(lines)})\n\n"
        )
        for i, part in enumerate(parts):
            await ctx.reply(
                header + part if i == 0 else part,
                allowed_mentions=discord.AllowedMentions.none(),
                suppress_embeds=True,
            )
            # Small delay to avoid rate limits
            await asyncio.sleep(1)

        return None


async def setup(bot: commands.Bot) -> None:
    """
    Register the GetSubmissionsCommand cog.

    Args:
        bot (commands.Bot): The bot instance.
    """
    await bot.add_cog(
        GetSubmissionsCommand(
            task_manager=     bot.task_manager,
        )
    )
