"""
Domain Entities
===============

Module path:
    src/domain/entities.py

Summary:
    Core domain entities representing tasks, users, teams, submissions,
    and speed‑task sessions, along with related value objects.

Responsibilities:
    - Task: competition with lifecycle methods (open, publish, close)
    - SpeedTaskSession: individual user session for a speed-task
    - SubmissionFile, RKGFile, RKSysFile: file metadata value objects
    - User: Discord user
    - Team: group of users who collaborate in a task
    - Submission: run submission tied to a task, user/team, and file
"""

from __future__ import annotations
from typing import List, Optional
import time


class Task:
    """
    Represents a competition task, with open/close/release lifecycle.
    """

    def __init__(
        self,
        number: int,
        year: int,
        team_size: int,
        speed_task: bool,
        deadline_epoch: int,
        is_active: bool = False,
        is_released: bool = False,
    ):
        """
        Args:
            number (int): competition number.
            year (int): competition year.
            team_size (int): maximum members per team.
            speed_task (bool): is this a speed‑task?
            deadline_epoch (int): UNIX timestamp for deadline.
            is_active (bool): State of the task: running, or closed.
            is_released (bool): For normal tasks; true on intitial publish. For speed tasks; true once it's released publicly
        """
        self.id: Optional[int] = None
        self.number = number
        self.year = year
        self.team_size = team_size
        self.speed_task = speed_task
        self.deadline = deadline_epoch
        self._is_active = is_active
        self._is_released = is_released

    @property
    def is_active(self) -> bool:
        """
        Returns:
            bool: True if a task is currently ongoing.
        """
        return self._is_active

    @property
    def is_released(self) -> bool:
        """
        Returns:
            bool: True if the task is publicly visible. The only time this is False is during the "hidden" phase of a speed task.
        """
        return self._is_released

    def open(self) -> None:
        """
        Declares the task as active.
        Additionally, if the task is not a speed-task, it opens the task for submissions.

        Raises:
            RuntimeError: if the task is already open.
        """
        if self._is_active:
            raise RuntimeError("Task is already open")
        self._is_active = True
        if not self.speed_task:
            self._is_released = True

    def publish(self) -> None:
        """
        Publish a speed‑task after the hidden phase.
        Does nothing for non-speed tasks.

        Raises:
            RuntimeError: if called on a non-speed task.
        """
        if not self.speed_task:
            raise RuntimeError("publish() allowed only for speed‑tasks")
        if self._is_released:
            return
        self._is_released = True

    def close(self) -> None:
        """
        Close the task (stop accepting submissions).

        Raises:
            RuntimeError: if the task is not currently open.
        """
        if not self._is_active:
            raise RuntimeError("Task is not open")
        self._is_active = False


class SpeedTaskSession:
    """
    Represents a personal session for a speed‑task, with its own deadline.
    """

    def __init__(
        self,
        user: User,
        task: Task,
        personal_deadline: int,
        active: bool = True,
    ):
        """
        Args:
            user (User): the competitor.
            task (Task): the associated speed‑task.
            personal_deadline (int): UNIX timestamp deadline for this user.
            active (bool): whether the session is still active and the user can still submit.
        """
        self.user = user
        self.task = task
        self.personal_deadline = personal_deadline
        self.active = active

    @property
    def remaining(self) -> int:
        """
        Returns:
            int: seconds remaining until personal deadline.
        """
        return self.personal_deadline - int(time.time())

    def is_active(self) -> bool:
        """
        Returns:
            bool: True if session is active and before personal deadline.
        """
        now = time.time()
        return self.active and now < self.personal_deadline


class SubmissionFile:
    """
    Value object for submission file metadata.
    """

    def __init__(self, path: str, uploaded_at: int):
        """
        Args:
            path (str): storage path or URL.
            uploaded_at (int): UNIX timestamp when uploaded.
        """
        self.path = path
        self.uploaded_at = uploaded_at


class RKGFile(SubmissionFile):
    """
    Represents an .rkg run file with lap times and run time.
    """

    def __init__(
        self,
        path: str,
        uploaded_at: int,
        lap_times: List[str],
        character: int,
        vehicle: int,
        run_time: float,
    ):
        """
        Args:
            lap_times (List[str]): raw lap time strings.
            character (int): character ID/index.
            vehicle (int): vehicle ID/index.
            run_time (float): total run time in seconds.
        """
        super().__init__(path, uploaded_at)
        self.lap_times = lap_times
        self.character = character
        self.vehicle = vehicle
        self.run_time = run_time


class RKSysFile(SubmissionFile):
    """
    Represents an .rksys file with a system tag.
    """

    def __init__(self, path: str, uploaded_at: int, system_tag: str):
        """
        Args:
            system_tag (str): internal system identifier.
        """
        super().__init__(path, uploaded_at)
        self.system_tag = system_tag
        self.run_time = 0.0  # no run time available


class User:
    """
    Domain model for a Discord user
    """

    def __init__(
        self,
        discord_id: int,
        handle: str,
        display_name: str,
        id: int | None = None,
        coins: int = 0,
    ):
        """
        Args:
            discord_id (int): Discord user ID.
            handle (str): username
            display_name (str): server display name.
            id (int | None): internal DB primary key.
            coins (int): wallet balance.
        """
        self.id = id
        self.discord_id = discord_id
        self.handle = handle
        self.display_name = display_name
        self.coins = coins

    def award_coins(self, amount: int) -> None:
        """
        Add coins to the user’s balance.

        Args:
            amount (int): amount to add.


        """
        self.coins += amount


class Team:
    """
    Represents a team of up to `team_size` users.
    """

    def __init__(self, leader: User, members: List[User] = None, name: str | None = None):
        """
        Args:
            leader (User): team leader.
            members (List[User]): initial member list; defaults to [leader].
            name (str | None): optional team name.
        """
        self.id = None
        self.leader = leader
        self.members = members[:] if members else [leader]
        self.name = name

    def add_member(self, user: User) -> None:
        """
        Add a new member to the team.

        Args:
            user (User): user to add.

        Raises:
            RuntimeError: if the user is already in the team.
        """
        if user in self.members:
            raise RuntimeError(f"{user.display_name} is already in team “{self.name}”")
        self.members.append(user)

    def remove_member(self, user: User) -> None:
        """
        Remove a member from the team.

        Args:
            user (User): user to remove.

        Raises:
            RuntimeError: if attempting to remove the leader or a non-member.
        """
        if user == self.leader:
            raise RuntimeError("Cannot remove the team leader")
        try:
            self.members.remove(user)
        except ValueError:
            raise RuntimeError(f"{user.display_name} is not in the team")



class Submission:
    """
    Domain entity representing a run submission for a competition.
    """

    def __init__(
        self,
        submitted_by: User,
        task: Task,
        file: SubmissionFile,
        team: Optional[Team] = None,
        *,
        url: str,
    ):
        """
        Args:
            submitted_by (User): who submitted the run.
            task (Task): the task being competed on.
            file (SubmissionFile): metadata of the submission file.
            team (Team | None): optional team.
            url (str): file URL or storage path.
        """
        self.id: Optional[int]       = None
        self.submitted_by: User      = submitted_by
        self.task: Task              = task
        self.file: SubmissionFile    = file
        self.team: Optional[Team]    = team
        self.url: str                = url

        # Populated after parsing
        self.time: Optional[float]   = None
        self.character: Optional[str]= None
        self.vehicle: Optional[str]  = None

        # Disqualification fields
        self.dq: bool                = False
        self.dq_reason: Optional[str]= None

    def validate(self) -> None:
        """
        Validate that the submission is consistent with the task.

        Raises:
            RuntimeError: if time or url missing, or task closed,
                          or team size exceeded.
        """
        if self.time is None:
            raise RuntimeError("Submission time is not set")
        if not self.url:
            raise RuntimeError("Submission URL is missing")
        if not self.task.is_active:
            raise RuntimeError("Competition is closed or not started")
        if self.team and len(self.team.members) > self.task.team_size:
            raise RuntimeError(
                f"Team size exceeded ({len(self.team.members)} > {self.task.team_size})"
            )
