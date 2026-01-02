"""
Discord Command & Event Error Logger
====================================

Module path:
    src/adapters/discord/events/discord_errors.py

Summary:
    Centralized logging for command and event errors. Non-trivial/internal
    exceptions are printed to console and forwarded to the configured log
    channel as an embed.

Responsibilities:
    - Capture unhandled command errors via on_command_error.
    - Capture event errors via on_error.
    - Distinguish trivial user errors (missing perms/args/checks) from internal errors.
    - Send an embed matching the expected formatting, with a traceback excerpt.
    - Fallback to a .txt attachment if the traceback is too long for an embed field.
"""

from __future__ import annotations

import io
import logging
import traceback
from typing import Optional

import discord
from discord.ext import commands

from application.services.config_service import ConfigService

log = logging.getLogger(__name__)

# Embed field hard limit is 1024 chars; keep headroom for code fences
_TB_SNIPPET_MAX   = 900  # characters inside the code block
_CODE_FENCE_OPEN  = "```py\n"
_CODE_FENCE_CLOSE = "```"


def _unwrap_error(exc: BaseException) -> BaseException:
    """Return the deepest/original exception if available."""
    original = getattr(exc, "original", None)
    return original or exc


def _format_traceback_excerpt(exc: BaseException) -> tuple[str, bool, str]:
    """
    Build a short traceback excerpt suitable for an embed field.
    Ensures it fits within ~1024 chars once fenced in a code block.
    """
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    snippet = tb.strip()
    truncated = False
    if len(snippet) > _TB_SNIPPET_MAX:
        # Keep head and tail a bit to show both the top frame and the raise site
        head = snippet[: int(_TB_SNIPPET_MAX * 0.65)]
        tail = snippet[-int(_TB_SNIPPET_MAX * 0.25) :]
        snippet = head.rstrip() + "\n...\n" + tail.lstrip()
        truncated = True
    fenced = f"{_CODE_FENCE_OPEN}{snippet}{_CODE_FENCE_CLOSE}"
    return fenced, truncated, tb  # (excerpt_for_embed, was_truncated, full_tb)


class ErrorHandler(commands.Cog):
    """
    Cog that logs command & event errors as a red embed with:
      • Command
      • User
      • Error
      • Traceback (excerpt)
    and prints the full traceback to the console.

    Attributes:
        bot (commands.Bot): Discord bot instance.
        cfg_svc (ConfigService): For retrieving the target log channel.
    """

    def __init__(self, bot: commands.Bot, config_service: ConfigService):
        self.bot = bot
        self.cfg_svc = config_service

    # ──────────────────────────────────────────────────────────────
    # Command errors
    # ──────────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        # 1) Ignore if already handled
        if getattr(error, "handled", False):
            return

        # 2) Filter out trivial user-facing errors
        if isinstance(
            error,
            (
                commands.MissingRequiredArgument,
                commands.BadArgument,
                commands.MissingPermissions,
                commands.CheckFailure,
                commands.CommandNotFound,
                commands.UnexpectedQuoteError,
                commands.InvalidEndOfQuotedStringError
            ),
        ):
            try:
                await ctx.send(f"❌ {error}", delete_after=10)
            except Exception:
                pass
            return

        # 3) Unwrap and log to console
        root = _unwrap_error(error)
        traceback.print_exception(type(root), root, root.__traceback__)
        log.exception("Command error in %s by %s", ctx.command, ctx.author)

        # 4) Feedback to the user (deleted shortly)
        try:
            await ctx.send(
                f"❌ Internal error occurred: `{type(root).__name__}` – {root}",
                delete_after=10,
            )
        except Exception:
            pass

        # 5) Build embed
        embed = discord.Embed(
            title=":rotating_light: Command Error",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Command", value=str(ctx.command), inline=False)
        embed.add_field(
            name="User",
            value=f"{ctx.author} ({ctx.author.id})",
            inline=False,
        )

        # The “Error” field should include the full chain if applicable (e.g., HybridCommandError → RuntimeError)
        err_line = f"{type(error).__name__}: {error}"
        if root is not error:
            err_line = f"{type(error).__name__}: {error}\n↳ {type(root).__name__}: {root}"
        embed.add_field(name="Error", value=err_line, inline=False)

        excerpt, was_truncated, full_tb = _format_traceback_excerpt(root)
        embed.add_field(name="Traceback (excerpt)", value=excerpt, inline=False)

        file: Optional[discord.File] = None
        if was_truncated:
            # Attach full traceback as a .txt if we had to truncate the embed field
            file = discord.File(io.BytesIO(full_tb.encode("utf-8")), filename="traceback.txt")

        # 6) Send to log channel
        await self._send_to_log_channel(ctx.guild, embed, file=file)

    # ──────────────────────────────────────────────────────────────
    # Event-level errors
    # ──────────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_error(self, event_method: str, *args, **kwargs):
        """
        Called by discord.py when an unhandled exception occurs in an event.
        We capture the exception information from sys.exc_info().
        """
        import sys

        exc_type, exc, tb_obj = sys.exc_info()
        if exc is None:
            return  # nothing to do

        traceback.print_exception(exc_type, exc, tb_obj)
        log.exception("Unhandled event error in %s", event_method)

        embed = discord.Embed(
            title=":rotating_light: Event Error",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Event", value=event_method, inline=False)
        embed.add_field(name="Error", value=f"{exc_type.__name__}: {exc}", inline=False)

        # Build excerpt from the current exception
        excerpt, was_truncated, full_tb = _format_traceback_excerpt(exc)
        embed.add_field(name="Traceback (excerpt)", value=excerpt, inline=False)

        file: Optional[discord.File] = None
        if was_truncated:
            file = discord.File(io.BytesIO(full_tb.encode("utf-8")), filename="traceback.txt")

        # Retrieve guild
        guild = self.bot.guilds[0] if self.bot.guilds else None
        await self._send_to_log_channel(guild, embed, file=file)

    # ──────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────
    async def _send_to_log_channel(
        self,
        guild: Optional[discord.Guild],
        embed: discord.Embed,
        file: Optional[discord.File] = None,
    ) -> None:
        """Resolve configured log channel for the guild and send the embed (+ optional file)."""
        if guild is None:
            return
        try:
            gc = await self.cfg_svc.get_guild_config(guild.id)
            if not gc:
                return
            log_cfg = await self.cfg_svc.get_log_channel(gc.comp)
            if not log_cfg or not log_cfg.channel_id:
                return
            channel = guild.get_channel(log_cfg.channel_id)
            if not isinstance(channel, discord.TextChannel):
                return

            await channel.send(embed=embed, file=file) if file else await channel.send(embed=embed)
        except discord.Forbidden:
            pass
        except Exception:
            log.exception("Failed to send error embed to log channel")


async def setup(bot: commands.Bot):
    """Register the ErrorHandler cog."""
    await bot.add_cog(ErrorHandler(bot, bot.config_service))
