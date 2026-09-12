"""
Get Results Command
===================

Module path:
    src/adapters/discord/commands/get_results_command.py

Summary:
    Hybrid command ``$get-results`` / ``/get-results`` that prints the final
    leaderboard for the current task (active if any, otherwise the most-recent
    closed task).

    • Ranked submissions are sorted by best time; ties share the same place.
    • Disqualified (DQ) runs are listed after a blank line with their reason.
    • Output is chunked so messages never exceed Discord’s 2 000-character
      limit.

"""
from __future__ import annotations

import asyncio
from discord.ext import commands

from adapters.discord.utils.time_format import fmt_time


class GetResultsCommand(commands.Cog):
    """Return a nicely-formatted leaderboard for the latest task."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot            = bot
        self.task_mgr       = bot.task_manager
        self.sub_svc        = bot.submission_service
        self.team_svc       = bot.team_service

    # ───────────────────────────────────────────────────────────────
    @commands.hybrid_command(
        name="get-results",
        description="[Host] Show ranked results (plus DQs) for the current or last task.",
        usage="$/get-results",
        help=("""
        Shows formatted results for the current task.

        Parameters:
            None
    """),
        with_app_command=True,
    )
    async def get_results(self, ctx: commands.Context) -> None:
        # 1) Retrieve task
        task = await self.task_mgr.get_active_task() or await self.task_mgr.get_last_task()
        if task is None:
            await ctx.reply("There is no task to fetch results.")
            return

        # 2) Fetch submissions belonging to that task
        all_subs = await self.sub_svc.get_submissions()
        submissions = [s for s in all_subs if s.task.id == task.id]
        if not submissions:
            await ctx.reply(f"No submissions for Task {task.number}.")
            return

        ranked = [s for s in submissions if not s.dq]
        ranked.sort(key=lambda s: s.time or float("inf"))

        dqed = [s for s in submissions if s.dq]
        dqed.sort(key=lambda s: s.time or 0.0)

        known = [s for s in ranked if s.time and s.time > 0]
        unknown = [s for s in ranked if not s.time or s.time <= 0]

        lines: list[str] = [f"**__Task {task.number} Results__**:\n"]

        def display(sub) -> str:
            if sub.team:
                return sub.team.name or " & ".join(m.display_name for m in sub.team.members)
            return sub.submitted_by.display_name

        def ordinal(n: int) -> str:
            """Return 1st / 2nd / 3rd / 4th ..."""
            if 10 <= n % 100 <= 20:
                suffix = "th"
            else:
                suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
            return f"{n}{suffix}"

        place = 0       # displayed place
        offset = 1      # how many runs processed

        prev_time = None
        for sub in known:
            if prev_time is None or abs(sub.time - prev_time) > 1e-6:
                place = offset
            txt = f"{ordinal(place)}. {display(sub)} — {fmt_time(sub.time)}"
            if place <= 3:
                txt = f"**{txt}**"
            lines.append(txt)

            prev_time = sub.time
            offset += 1

        # 4) DQ section
        if dqed:
            lines.append("")
            for sub in dqed:
                reason = f" [{sub.dq_reason}]" if sub.dq_reason else ""
                lines.append(f"DQ. {display(sub)} — {fmt_time(sub.time)}{reason}")

        # 5) Unknown‐time runs → show at the bottom
        if unknown:
            lines.append("")
            for sub in unknown:
                lines.append(f"N/A. {display(sub)} — {fmt_time(sub.time)}")

        content = "\n".join(lines)

        # 6) Split into ≤ 2000-char chunks
        while content:
            chunk = content[:2000]
            cut   = chunk.rfind("\n")
            if cut == -1 or len(content) <= 2000:
                await ctx.reply(chunk)
                break
            await ctx.reply(chunk[:cut])
            content = content[cut + 1:]
            await asyncio.sleep(1)




# ───────── Extension entrypoint ────────────────────────────────────────────
async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GetResultsCommand(bot))
