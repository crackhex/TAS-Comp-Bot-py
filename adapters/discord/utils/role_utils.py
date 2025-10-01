"""
Role Utilities
==============

Module path:
    src/adapters/discord/utils/role_utils.py

Summary:
    Helper functions to manage Discord roles on guild members,
    with silent failure on missing permissions or HTTP errors.

Responsibilities:
    - add_role_to_member: assign a role to a single member
    - clear_role_for_guild: remove a role from all members in a guild
    - remove_role_from_member: remove a role from a specific member
"""

import discord


async def add_role_to_member(
    guild: discord.Guild,
    user_id: int,
    role_id: int,
) -> None:
    """
    Assign a role to a guild member, failing silently on errors.

    Args:
        guild (discord.Guild): the guild where the role should be assigned.
        user_id (int): Discord ID of the member to receive the role.
        role_id (int): ID of the role to assign.

    Behavior:
        - Attempts to fetch the Member object (cache first, then API).
        - Retrieves the Role object by ID.
        - If either is missing, does nothing.
        - Otherwise, calls Member.add_roles(role).
        - Silently ignores discord.HTTPException (e.g., missing permissions).
    """
    member = guild.get_member(user_id) or await guild.fetch_member(user_id)
    role = guild.get_role(role_id)
    if not member or not role:
        return
    try:
        await member.add_roles(role)
    except discord.HTTPException:
        pass


async def clear_role_for_guild(
    guild: discord.Guild,
    role_id: int,
) -> None:
    """
    Remove a role from every member in the guild who currently has it.

    Args:
        guild (discord.Guild): the guild in which to clear the role.
        role_id (int): ID of the role to remove.

    Behavior:
        - Looks up the Role by ID.
        - Iterates through guild.members and, for each who has the role,
          attempts to remove it.
        - Silently ignores discord.HTTPException (e.g., insufficient permissions).
    """
    role = guild.get_role(role_id)
    if not role:
        return

    for member in guild.members:
        if role in member.roles:
            try:
                await member.remove_roles(role)
            except discord.HTTPException:
                pass


async def remove_role_from_member(
    guild: discord.Guild,
    user_id: int,
    role_id: int,
) -> None:
    """
    Remove a specific role from a single guild member, if present.

    Args:
        guild (discord.Guild): the guild containing the member.
        user_id (int): Discord ID of the member from whom to remove the role.
        role_id (int): ID of the role to remove.

    Behavior:
        - Attempts to fetch the Member object (cache first, then API).
        - Retrieves the Role object by ID.
        - If either is missing, does nothing.
        - Otherwise, calls Member.remove_roles(role).
        - Silently ignores discord.HTTPException.
    """
    member = guild.get_member(user_id) or await guild.fetch_member(user_id)
    role = guild.get_role(role_id)
    if not member or not role:
        return

    try:
        await member.remove_roles(role)
    except discord.HTTPException:
        pass
