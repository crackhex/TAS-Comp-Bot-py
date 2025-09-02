"""
Submission Utilities
====================

Module path:
    src/adapters/discord/utils/submission_utils.py

Summary:
    Helper function to maintain the public “Current Submissions” message
    in the configured Discord channel. It finds the bot’s previous post,
    retrieves the latest submissions, formats them in order of first submission,
    and either edits the existing message or sends a new one.

Responsibilities:
    - Validate guild and channel configuration
    - Locate the bot’s last submissions message
    - Fetch and sort submissions by their domain ID (earliest first)
    - Build alist of solo or team submissions
    - Edit the existing message or post a new one
"""

from typing import List, Optional

import discord
from application.services.config_service     import ConfigService
from application.services.submission_services.base_submission_service import BaseSubmissionService


async def refresh_submission_list(
    bot:        discord.Client,
    cfg_svc:    ConfigService,
    guild:      Optional[discord.Guild],
) -> None:
    """
    Update or send the “Current Submissions” message in the guild’s submissions channel.

    Args:
        bot (discord.Client): the bot instance (to identify its user and guilds).
        cfg_svc (ConfigService): service for reading guild-specific configuration.
        guild (discord.Guild | None): the target guild to update; if None, no action.

    Returns:
        None
    """
    if guild is None:
        return


    sub_svc: BaseSubmissionService = bot.submission_service

    # 1) Retrieve guild configuration and the submissions channel setting
    gc = await cfg_svc.get_guild_config(guild.id)
    if not gc:
        return
    ch_cfg = await cfg_svc.get_submission_channel(gc.comp)
    if not ch_cfg:
        return

    channel = guild.get_channel(ch_cfg.channel_id)
    if not isinstance(channel, discord.TextChannel):
        return

    # 2) Find the bot’s last message in that channel (to edit instead of repost)
    bot_msg: Optional[discord.Message] = None
    async for m in channel.history(limit=5):
        if m.author == bot.user:
            bot_msg = m
            break

    # 3) Fetch all current submissions
    subs = await sub_svc.get_submissions()

    # 4) If there are no submissions, delete the old message (if any) and exit
    if not subs:
        if bot_msg:
            try:
                await bot_msg.delete()
            except discord.HTTPException:
                pass
        return

    # 5) Sort by submission ID to reflect order of first submission
    subs.sort(key=lambda s: s.id)

    # 6) Build the ordered list of display strings
    ordered: List[str] = []
    for sub in subs:
        if sub.team:
            members = " & ".join(m.display_name for m in sub.team.members)
            if sub.team.name and sub.team.name.strip():
                display = f"{sub.team.name} ({members})"
            else:
                display = members
        else:
            display = sub.submitted_by.display_name

        ordered.append(display)

    # 7) Compose the final message content
    content = "**__Current Submissions__**:\n" + "\n".join(
        f"{i+1}. {name}" for i, name in enumerate(ordered)
    )

    # 8) Edit the existing message or send a new one
    if bot_msg:
        try:
            await bot_msg.edit(content=content)
            return
        except discord.HTTPException:
            pass

    await channel.send(content)
