"""
Error Test Commands
===================

Module path:
    src/adapters/discord/commands/admin/error_test_commands.py

Summary:
    Commands that intentionally raise exceptions to test the error logger and handling

Responsibilities:
    - Raise a RuntimeError from a prefix command (hits on_command_error).
    - Raise a RuntimeError from a hybrid/slash command (hits on_app_command_error).
    - Optionally trigger a "trivial" error (type mismatch) to verify it is filtered.
"""

from discord.ext import commands


class ErrorTestCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Prefix-only command → on_command_error
    @commands.command(name="test-internal-prefix")
    @commands.has_permissions(administrator=True)
    async def test_internal_prefix(self, ctx: commands.Context):
        """Raise a non-trivial error from a prefix command."""
        raise RuntimeError("Test internal error (prefix)")

    # Hybrid command → as prefix: on_command_error ; as slash: on_app_command_error
    @commands.hybrid_command(name="test-internal-hybrid", description="Raise an internal error (hybrid)")
    @commands.has_permissions(administrator=True)
    async def test_internal_hybrid(self, ctx: commands.Context):
        """Raise a non-trivial error from a hybrid command."""
        raise RuntimeError("Test internal error (hybrid)")

    # "trivial error" (BadArgument)
    @commands.hybrid_command(name="test-trivial", description="Cause a trivial type error (filtered)")
    @commands.has_permissions(administrator=True)
    async def test_trivial(self, ctx: commands.Context, must_be_int: int):
        """This will raise BadArgument if a non-int is passed (should be filtered by the handler)."""
        await ctx.send(f"OK, got int={must_be_int}")


async def setup(bot: commands.Bot):
    await bot.add_cog(ErrorTestCommands(bot))
