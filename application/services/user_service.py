"""
User Service
============

Module path:
    src/application/services/user_service.py

Summary:
    Application service for user-related operations, including ensuring user existence,
    updating display names

Responsibilities:
    - ensure_user: load or create a User based on Discord ID
    - update_display_name: set a new display name for an existing user
"""
from typing import List

import discord
from domain.entities import User
from domain.repositories import UserRepository


class UserService:
    """
    Provides high-level operations on User entities.
    """

    def __init__(self, user_repo: UserRepository, discord_client: discord.Client):
        """
        Initialize UserService with required dependencies.

        Args:
            user_repo (UserRepository): repository for persisting and loading users.
            discord_client (discord.Client): Discord API client for fetching user info.
        """
        self._user_repo = user_repo
        self._discord_client = discord_client

    async def update_display_name(self, discord_id: int, new_name: str) -> User:
        """
        Update the display name of an existing user.

        Args:
            discord_id (int): Discord ID of the user.
            new_name (str): New display name to set.

        Returns:
            User: The updated User entity.

        Raises:
            RuntimeError: If the user does not exist in the repository.
        """
        # Load the user from the repository
        user = await self._user_repo.get_by_discord_id(discord_id)
        if not user:
            raise RuntimeError("User has not participated yet.")

        # Update and persist the new display name
        user.display_name = new_name
        await self._user_repo.save(user)
        return user

    async def ensure_user(self, discord_id: int) -> User:
        """
        Ensures a User entity exists for the given Discord ID; create one if not and add them to the database.

        Args:
            discord_id (int): Discord user ID.

        Returns:
            User: The existing or newly created User entity.
        """
        # 1) Attempt to load from the repository
        user = await self._user_repo.get_by_discord_id(discord_id)
        if user:
            return user

        # 2) Fallback: fetch user info from Discord API
        handle = str(discord_id) # initialize variable
        display = str(discord_id) # initialize variable
        try:
            uobj = await self._discord_client.fetch_user(discord_id)
            handle = str(uobj)               # calls __str__ from discord.User (e.g. "dashqc")
            display = uobj.display_name
        except Exception:
            # If Discord API fails, proceed with numeric defaults
            pass

        # 3) Create a new User domain entity and persist it
        user = User(
            discord_id=discord_id,
            handle=handle,
            display_name=display,
        )
        await self._user_repo.add(user)
        return user


    async def list_users(self) -> List[User]:
        """
        Return all users known to the application.
        """
        return await self._user_repo.list_users()
