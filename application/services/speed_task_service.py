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
import math
import random
from datetime import datetime, timedelta
import time

from application.services.user_service import UserService
from domain.entities import SpeedTaskSession
from domain.repositories import SpeedTaskRepository, TaskRepository
from application.services.config_service import ConfigService

def _round_epoch_to_nearest_minute(epoch_seconds: int) -> int:
    """
    Round to the nearest minute:
    - seconds >= 30 => ceil to next minute
    - else => floor to current minute
    """
    dt = datetime.fromtimestamp(epoch_seconds)
    if dt.second >= 30:
        dt = dt.replace(second=0, microsecond=0) + timedelta(minutes=1)
    else:
        dt = dt.replace(second=0, microsecond=0)
    return int(dt.timestamp())


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

        base_length_sec = int(length_cfg.time * 3600)  # hours -> seconds
        now_raw = int(time.time())
        time_left = task.deadline - now_raw

        # 4) Extra setting
        extra = await self._cfg_svc.get_extra_setting(gc.comp)
        extra_enabled = bool(extra and extra.enabled)

        length_sec = base_length_sec

        if extra_enabled:
            # Calculate minimum possible time (rounded to nearest 5 minutes)
            lower_mult = max(0.001, float(extra.lower_bound) / 100.0)
            min_len_minutes = (base_length_sec * lower_mult) / 60.0
            min_len_5 = max(5, round(min_len_minutes / 5) * 5)
            min_len_sec = min_len_5 * 60

            # Deny if minimum can't fit before global deadline
            if time_left < min_len_sec:
                raise RuntimeError(f"Too late to request task.")

            # Generate random length using triangular distribution
            length_sec = _extra_setting_result(
                base_length_sec=base_length_sec,
                lower_pct=float(extra.lower_bound),
                upper_pct=float(extra.upper_bound),
            )

            # Cap at remaining time if needed
            length_sec = min(length_sec, time_left)


        # 5) Calculate and round deadline
        raw_deadline = now_raw + length_sec
        personal_deadline = _round_epoch_to_nearest_minute(raw_deadline)

        # Extra safety: never exceed global deadline
        if personal_deadline > task.deadline:
            personal_deadline = task.deadline

        # 6) Create and persist the new session
        session = SpeedTaskSession(
            user=user,
            task=task,
            personal_deadline=personal_deadline,
        )
        await self._speed_repo.add(session)

        deadline_str = datetime.fromtimestamp(personal_deadline).strftime('%Y-%m-%d %H:%M:%S')
        hours = length_sec // 3600
        minutes = (length_sec % 3600) // 60
        duration_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
        print(f"Started speed task for {user.handle}, deadline at {deadline_str} ({duration_str})")

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

    async def cancel_session(self, user_id: int) -> None:
        """
            Cancel the personal speed-task session for a user. This makes them eligible to requesttask again.

            Args:
                user_id (int): Discord user ID.

            Returns:
                SpeedTaskSession: the deleted session.

            """
        await self._speed_repo.cancel_session(user_id)

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


def _extra_setting_result(
        *,
        base_length_sec: int,
        lower_pct: float,
        upper_pct: float,
) -> int:
    """
    Generate the extra setting result using triangular distribution in log-space.

    Args:
        base_length_sec: The base length of the task in seconds
        lower_pct: The lower bound in %
        upper_pct: The upper bound in %

    Returns:
        Random extra setting length result, rounded to nearest 5 minutes.
    """
    # Convert percentages to multipliers
    lower_mult = max(0.001, lower_pct / 100.0)
    upper_mult = max(lower_mult, upper_pct / 100.0)

    # Generate triangular distribution from -1 to 1 (centered at 0)
    sample_a = random.randrange(1002)
    sample_b = random.randrange(1002)
    normal_dist = (sample_a + sample_b - 1001) / 1000.0

    # Map to log-space between lower and upper bounds
    log_lower = math.log2(lower_mult)
    log_upper = math.log2(upper_mult)

    # Interpolate in log-space: -1 -> lower, 0 -> geometric mean, 1 -> upper
    t = (normal_dist + 1) / 2  # Map [-1, 1] to [0, 1]
    log_multiplier = log_lower + t * (log_upper - log_lower)
    multiplier = 2 ** log_multiplier

    # Apply multiplier to base time
    random_time_sec = base_length_sec * multiplier

    # Convert to minutes and round to nearest 5
    total_minutes = random_time_sec / 60.0
    rounded_minutes = max(5, round(total_minutes / 5) * 5)

    return int(rounded_minutes * 60)