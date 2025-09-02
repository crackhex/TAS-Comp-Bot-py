"""
DM Submission Listener
======================

Module path:
    src/adapters/discord/events/dm_submission_listener.py

Summary:
    Cog that listens for direct messages (DMs) sent to the bot
    and processes valid competition submissions.

Responsibilities:
    - Validate file type based on general allowed extensions and
      competition-specific settings.
    - Check active competition and speed-task sessions when required.
    - Delegate the actual submission creation to SubmissionService.
    - Refresh the public submissions list.
    - Assign the "submitted" role to users (except in speed-tasks).
"""

from typing import Optional

import discord
from discord.ext import commands

from adapters.discord.utils.role_utils import add_role_to_member
from adapters.discord.utils.submission_utils import refresh_submission_list
from application.services.speed_task_service    import SpeedTaskService
from application.services.task_manager          import TaskManager
from application.services.config_service        import ConfigService


class DMSubmissionListener(commands.Cog):
    """
    Cog that processes competition submissions sent via DMs to the bot.

    Workflow:
        1. Validates the attachment file type.
        2. Verifies the active competition and any speed-task session.
        3. Submits the file using SubmissionService.
        4. Updates the public submissions list.
        5. Assigns the "submitted" role (non-speed tasks only).
    """

    bot: commands.Bot  # Will be set in setup()

    def __init__(
        self,
        speed_svc:          SpeedTaskService,
        task_mgr:           TaskManager,
        config_service:     ConfigService,
    ):
        """
        Initialize the listener.

        Args:
            speed_svc (SpeedTaskService): Service managing speed-task sessions.
            task_mgr (TaskManager): Service managing competitions/tasks.
            config_service (ConfigService): Service for retrieving configuration.
        """
        self.speed_svc = speed_svc
        self.task_mgr  = task_mgr
        self.cfg_svc   = config_service

    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        """
        Event listener that processes DMs with attachments as submissions.

        Args:
            msg (discord.Message): Incoming message object.
        """

        # Ignore bots, guild messages, or messages without attachments
        if msg.author.bot or msg.guild is not None or not msg.attachments:
            return

        filename = msg.attachments[0].filename.lower()

        # 1) ––––– Ensure there is an active task
        task = await self.task_mgr.get_active_task()
        if not task:
            await msg.channel.send("There is no ongoing task!")
            return

        # 2) Retrieve the **accepted extension for this competition
        #       (set by /set-file). If nothing is configured, submissions are
        #       disabled until an admin sets one.
        gc = await self.cfg_svc.get_guild_config(self.bot.guilds[0].id)
        if not gc:
            await msg.channel.send("This server is not bound to any competition. Ask an admin to use `/set-comp`")
            return

        ext_cfg = await self.cfg_svc.get_submission_file_extension(gc.comp)
        if not ext_cfg:
            await msg.channel.send(
                "No submission file type configured. "
                "Ask an admin to use `/set-file` first."
            )
            return

        accepted_ext = ext_cfg.ext.lower()

        if not filename.endswith(f".{accepted_ext}"):
            await msg.channel.send(
                f"This competition only accepts **.{accepted_ext}** files."
            )
            return

        # 3) Speed-task session verifications
        if task.speed_task:
            session = await self.speed_svc.get_session_for_user(msg.author.id)
            if not session:
                await msg.channel.send("You may not submit to this speed task as of now! Use `$requesttask` first.")
                return
            if not session.is_active():
                await msg.channel.send("Your speed task is already over! You cannot submit.")
                return

        # 4) Fetch file bytes & hand over to SubmissionService
        file_bytes = await msg.attachments[0].read()
        file_url = msg.attachments[0].url

        try:
            submission = await self.bot.submission_service.submit(
                user_id=msg.author.id,
                file_bytes=file_bytes,
                file_url=file_url,
            )
        except Exception as exc:
            await msg.channel.send(f"❌ Submission failed: {exc}")
            return

        # 5) Refresh the public “Current Submissions” list
        target_guild: Optional[discord.Guild] = self.bot.guilds[0] if self.bot.guilds else None
        if target_guild:
            await refresh_submission_list(
                bot=self.bot,
                cfg_svc=self.cfg_svc,
                guild=target_guild,
            )

        # 6) Assign the “submitted” role (non-speed tasks only)
        if target_guild and not task.speed_task:
            submit_cfg = await self.cfg_svc.get_submitter_role(gc.comp)
            if submit_cfg and submit_cfg.role_id:
                if submission.team:
                    for member in submission.team.members:
                        await add_role_to_member(
                            target_guild, member.discord_id, submit_cfg.role_id
                        )
                else:
                    await add_role_to_member(
                        target_guild, msg.author.id, submit_cfg.role_id
                    )

        # 7) Ack
        extension = (msg.attachments[0].filename.lower().split("."))[1]
        await msg.channel.send(f"`.{extension}` file detected!\n"
                                            f"The file was successfully saved. Type `$info` for more information "
                                            f"about the file."
                                      )



async def setup(bot: commands.Bot):
    """
    Setup function to add this Cog to the bot.

    Args:
        bot (commands.Bot): The Discord bot instance.
    """
    cog = DMSubmissionListener(
        speed_svc=         bot.speed_task_service,
        task_mgr=          bot.task_manager,
        config_service=    bot.config_service,
    )
    cog.bot = bot  # type: ignore
    await bot.add_cog(cog)
