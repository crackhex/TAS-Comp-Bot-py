"""
Speed Task Service
==================

Module path:
    src/application/services/speed_task_service.py

Summary:
    Provides application-level operations for managing personal speed-task sessions,
    including request, listing, expiration, and cleanup.

Responsibilities:
    - request_task: start a personal speed-task session with rounded deadline
    - get_session_for_user: retrieve a user's speed-task session
    - list_active_sessions: get all active speed-task sessions
    - expire_session: mark a user's session as expired; they may no longer compete
    - clear_sessions: remove all sessions (e.g., at competition end)
"""

from datetime import datetime, timedelta
import time

from application.services.user_service import UserService
from domain.entities import SpeedTaskSession
from domain.repositories import SpeedTaskRepository, TaskRepository
from application.services.config_service import ConfigService


class SpeedTaskService:
    """
    Application service to manage speed-task sessions.
    Coordinates between repositories, configuration, and user enrollment.
    """

    def __init__(
        self,
        speed_repo: SpeedTaskRepository,
        task_repo:  TaskRepository,
        cfg_svc:    ConfigService,
        user_svc:   UserService,
    ):
        """
        Initialize with required repositories and services.

        Args:
            speed_repo (SpeedTaskRepository): repo for persisting speed-task sessions.
            task_repo (TaskRepository): repo for retrieving tasks.
            cfg_svc (ConfigService): service for reading configuration values.
            user_svc (UserService): service for ensuring user exists.
        """
        self._speed_repo = speed_repo
        self._task_repo  = task_repo
        self._cfg_svc    = cfg_svc
        self._user_svc   = user_svc

    async def request_task(
        self,
        user_discord_id: int,
        guild_id:        int,
    ) -> SpeedTaskSession:
        """
        Start a personal session for the current speed-task,
        rounding the deadline to the nearest minute.

        Args:
            user_discord_id (int): Discord user ID of the participant.
            guild_id (int): ID of the guild to fetch configuration.

        Returns:
            SpeedTaskSession: the newly created session with rounded deadline.

        Raises:
            RuntimeError: if no active speed-task or configuration is missing.
        """
        # 1) Ensure there is an active speed-task
        task = await self._task_repo.get_active()
        if not task or not task.speed_task:
            raise RuntimeError("No active speed-task.")

        # 2) Ensure the User exists in the userbase (create if missing)
        user = await self._user_svc.ensure_user(user_discord_id)

        # 3) Load configured speed-task length
        gc = await self._cfg_svc.get_guild_config(guild_id)
        if not gc:
            raise RuntimeError("Missing competition configuration.")

        length_cfg = await self._cfg_svc.get_speed_task_length(gc.comp)
        if not length_cfg or length_cfg.time <= 0:
            raise RuntimeError("Speed-task length not configured.")

        length_sec = int(length_cfg.time * 3600) # hours -> seconds

        # 4) Compute raw deadline timestamp
        now_raw = int(time.time())
        raw_deadline = now_raw + length_sec

        # 5) Round to nearest minute: seconds >= 30 -> next minute, else floor
        dt = datetime.fromtimestamp(raw_deadline)
        if dt.second >= 30:
            dt = dt.replace(second=0, microsecond=0) + timedelta(minutes=1)
        else:
            dt = dt.replace(second=0, microsecond=0)
        rounded_deadline = int(dt.timestamp())

        # 6) Build and persist the new session
        session = SpeedTaskSession(
            user=user,
            task=task,
            personal_deadline=rounded_deadline,
        )
        await self._speed_repo.add(session)

        # at this point, the user is now eligible to submit

        return session

    async def get_session_for_user(self, user_discord_id: int) -> SpeedTaskSession | None:
        """
        Retrieve the speed-task session for a given user.

        Args:
            user_discord_id (int): Discord user ID.

        Returns:
            SpeedTaskSession | None: the session if found, else None.
        """
        return await self._speed_repo.get_by_user(user_discord_id)

    async def list_active_sessions(self) -> list[SpeedTaskSession]:
        """
        List all active (non-expired) personal speed-task sessions.

        Returns:
            List[SpeedTaskSession]: active sessions.
        """
        return await self._speed_repo.list_active_sessions()

    async def expire_session(self, user_discord_id: int) -> SpeedTaskSession:
        """
        End the personal speed-task session for a user.

        Args:
            user_discord_id (int): Discord user ID.

        Returns:
            SpeedTaskSession: the expired session.

        Raises:
            RuntimeError: if no session exists for the user.
        """
        return await self._speed_repo.expire_session(user_discord_id)

