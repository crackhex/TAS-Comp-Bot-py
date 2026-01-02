"""
Host Dissolve Command
=====================

Module path:
    src/adapters/discord/commands/host/host_dissolve_command.py

Summary:
    Host-only command that dissolves a given competitor's team, removes their current submission,
    and strips the submitted role from the former members.

Responsibilities:
    - Validate guild configuration.
    - Find the member's team (if any).
    - Remove the relevant submission (solo or team)
    - Dissolve the team.
    - Remove the submitted role from all ex-members.
    - Refresh the public "Current Submissions" message.
"""

import discord
from discord.ext import commands

from adapters.discord.checks                 import host_only
from adapters.discord.utils.submission_utils import refresh_submission_list
from adapters.discord.utils.role_utils       import remove_role_from_member
from application.services.team_service       import TeamService
from application.services.config_service     import ConfigService


class HostDissolveCommand(commands.Cog):
    """
    Hybrid command cog for host team dissolution.

    Flow:
        1) Remove the user's submission (solo or team).
        2) Dissolve their team in the database.
        3) Remove the "submitted" role from all former team members.
        4) Refresh the public submissions list.

    Attributes:
        team_svc (TeamService): Team management application service.
        cfg_svc  (ConfigService): Configuration service (channels, roles, etc.).
    """

    def __init__(
        self,
        team_svc:       TeamService,
        config_svc:     ConfigService,
    ):
        self.team_svc = team_svc
        self.cfg_svc  = config_svc

    @commands.hybrid_command(
        name="hostdissolve",
        description="[Host] Dissolve a competitor's team, and remove their submission if applicable.",
        usage="$/hostdissolve <member>",
        help=("""
            Dissolves a competitor's team in a collab task. Also deletes any existing submission from the team.

            Parameters:
                `member`: The member whose team will be dissolved. 
        """),
        with_app_command=True,
    )
    @host_only()
    async def hostdissolve(
        self,
        ctx: commands.Context,
        member: discord.Member,
    ):
        """
        Remove the target member's submission, dissolve their team, and
        remove the "submitted" role from all teammates.

        Steps:
            1) Ensure a competition is configured for this guild.
            2) Locate the member's team.
            3) Remove the member's submission (solo or team), ignoring "not found".
            4) Dissolve the team.
            5) Remove the configured "submitted" role from all ex-members.
            6) Refresh the public submissions list.
            7) Confirm to the invoker.

        Args:
            ctx (commands.Context): Invocation context.
            member (discord.Member): The competitor whose team will be dissolved.

        Returns:
            None
        """
        # 1) Verify a competition is setup
        gc = await self.cfg_svc.get_guild_config(ctx.guild.id)
        if not gc:
            return await ctx.send("There is no competition configured for this server. Use `/set-comp`.")

        # 2) Resolve the team this member belongs to
        team = await self.team_svc.get_team_by_member(member.id)
        if not team:
            return await ctx.send(f"{member.display_name} is already not in a team.")

        # 3) Remove submission (team or solo). If none exists, continue gracefully.
        try:
            await ctx.bot.submission_service.remove_submission(member.id)
        except Exception:
            # No submission (solo/team) to remove
            pass

        # 4) Dissolve the team
        await self.team_svc.dissolve_team(team.id)

        # 5) Remove the "submitted" role from all former team members, if configured
        submit_cfg = await self.cfg_svc.get_submitter_role(gc.comp)
        if submit_cfg and submit_cfg.role_id:
            for u in team.members:
                try:
                    await remove_role_from_member(ctx.guild, u.discord_id, submit_cfg.role_id)
                except Exception:
                    pass

        # 6) Refresh the submission list
        await refresh_submission_list(
            bot=    ctx.bot,
            cfg_svc=self.cfg_svc,
            guild=  ctx.guild,
        )

        # 7) Confirmation
        return await ctx.send(f"{member.mention}'s team has been dissolved.")


async def setup(bot: commands.Bot):
    """
    Register the HostDissolveCommand cog.

    Args:
        bot (commands.Bot): The bot instance.
    """
    await bot.add_cog(
        HostDissolveCommand(
            team_svc   =     bot.team_service,
            config_svc =     bot.config_service,
        )
    )
