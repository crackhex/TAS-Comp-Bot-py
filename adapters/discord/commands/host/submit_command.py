"""
Host Submit Command
===================

Module path:
    src/adapters/discord/commands/host/submit_command.py

Summary:
    Command that lets a Host submit a file on behalf of a user.
    It validates the file type against current competition
    settings, delegates persistence to the SubmissionService, refreshes the
    public submissions list, and assigns the "submitter" role when applicable.


Responsibilities:
    - Enforce host-only access (via `@host_only()` check).
    - Validate that a competition is configured and currently active.
    - Enforce allowed file extension depending on /set-file config.
    - Call `SubmissionService.submit(...)` to parse & store the submission.
    - Refresh the public "Current Submissions" message.
    - Assign the submitter role to the solo user or to all team members.
"""

import discord
from discord.ext import commands

from adapters.discord.checks import host_only
from adapters.discord.utils.submission_utils import refresh_submission_list
from adapters.discord.utils.role_utils import add_role_to_member
from application.services.config_service     import ConfigService
from application.services.task_manager       import TaskManager


class SubmitCommand(commands.Cog):
    """
    /submit @user <file> — Host-only.

    Allows a Host to submit a file for a given user.
    After a successful submission, the submission list is
    refreshed and the submitter role is granted.

    Attributes:
        cfg_svc (ConfigService): Service to access competition/guild config.
        task_mgr (TaskManager): Service to query the active task.
    """

    def __init__(
        self,
        config_svc:     ConfigService,
        task_mgr:       TaskManager,
    ):
        self.cfg_svc  = config_svc
        self.task_mgr = task_mgr

    @commands.hybrid_command(
        name="submit",
        description="[Host] Submit a file on behalf of a competitor.",
        usage="/submit <member> <file>",
        help=("""
            Submits on behalf of another competitor.

            Parameters:
                `member`: The competitor for who we wanna submit
                `file`: The submission file to be submitted.
        """),
        with_app_command=True,
    )
    @host_only()
    async def submit(
        self,
        ctx:    commands.Context,
        member: discord.Member,
        file:   discord.Attachment,
    ):
        """
        Submit a submission file on behalf of `member`.

        Flow:
            1) Ensure the server is configured for a competition.
            2) Ensure an active competition exists.
            3) Enforce the allowed extension based on the allowed file.
            4) Read file bytes and call `SubmissionService.submit(...)`.
            5) Refresh the public submissions list message.
            6) Assign the submitter role (solo or team) if configured.
            7) Confirm to the Host with the parsed time and file URL.

        Args:
            ctx (commands.Context): Invocation context.
            member (discord.Member): Target user for whom we submit.
            file (discord.Attachment): The uploaded `.rkg` or `.dat` file.

        Returns:
            None
        """
        # 1) Guild/competition configured?
        gc = await self.cfg_svc.get_guild_config(ctx.guild.id)
        if not gc:
            return await ctx.send("There is no competition configured for this server. Use `/set-comp`.")
        comp_key = gc.comp

        # 2) Active competition?
        task = await self.task_mgr.get_active_task()
        if not task:
            return await ctx.send("There is no active task!")

        # 3) — enforce allowed extension ---------------------------------
        ext_cfg = await self.cfg_svc.get_submission_file_extension(comp_key)
        if not ext_cfg:
            return await ctx.send("No submission file type configured. Ask an admin to run `/set-file`.")


        filename = file.filename.lower()
        if not filename.endswith(f".{ext_cfg.ext}"):
            return await ctx.send(f"This competition only accepts `.{ext_cfg.ext}` files.")

        # 4) — read bytes & delegate to the submission-service -----------
        data = await file.read()
        try:
            submission = await ctx.bot.submission_service.submit(
                user_id=member.id,
                file_bytes=data,
                file_url=file.url,
            )
        except Exception as exc:
            return await ctx.send(f"❌ Submission failed: {exc}")


        # 5) Refresh the public submission list
        await refresh_submission_list(
            bot=    ctx.bot,
            cfg_svc=self.cfg_svc,
            guild=  ctx.guild,
        )

        # 6) Assign the submitter role (team: all members; solo: just the user)
        guild_cfg   = await self.cfg_svc.get_guild_config(ctx.guild.id)
        submit_cfg  = await self.cfg_svc.get_submitter_role(guild_cfg.comp)

        if submit_cfg and submit_cfg.role_id:
            if submission.team:
                # Team submission → grant to all teammates
                for user in submission.team.members:
                    await add_role_to_member(ctx.guild, user.discord_id, submit_cfg.role_id)
            else:
                # Solo submission → grant to the member only
                await add_role_to_member(ctx.guild, member.id, submit_cfg.role_id)

        # 7) Confirmation message with formatted time and URL
        return await ctx.send(f"Succesfully submitted for {member.mention}.")


async def setup(bot: commands.Bot):
    """
    Register the `SubmitCommand` cog.

    Args:
        bot (commands.Bot): The bot instance.
    """
    await bot.add_cog(
        SubmitCommand(
            config_svc=bot.config_service,
            task_mgr=bot.task_manager,
        )
    )
