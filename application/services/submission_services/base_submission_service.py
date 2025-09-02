from __future__ import annotations
import time
from abc import ABC, abstractmethod
from typing import Optional

from application.parsers.file_parser import FileParser
from application.services.user_service import UserService
from domain.entities import Submission, SubmissionFile, Task
from domain.repositories import (
    SubmissionRepository, TaskRepository, UserRepository,
    TeamRepository, SpeedTaskRepository
)


class BaseSubmissionService(ABC):
    """
    Template-method base class that implements the invariant part of the
    submission workflow.  Sub-classes customise only the parsing details.
    """
    def __init__(
        self,
        user_svc: UserService,
        submission_repo: SubmissionRepository,
        task_repo: TaskRepository,
        user_repo: UserRepository,
        file_parser: FileParser,
        *,
        team_repo: Optional[TeamRepository] = None,
        speed_repo: Optional[SpeedTaskRepository] = None,
    ) -> None:
        self._user_svc   = user_svc
        self._sub_repo   = submission_repo
        self._task_repo  = task_repo
        self._user_repo  = user_repo
        self._parser     = file_parser
        self._team_repo  = team_repo
        self._speed_repo = speed_repo

    # ------------------------------------------------------------------ #
    # TEMPLATE METHOD — this method is final
    # ------------------------------------------------------------------ #
    async def submit(
        self,
        user_id: int,
        file_bytes: bytes,
        file_url: str,
        *,
        uploaded_at_epoch: int | None = None,
        team_id: int | None = None,
    ) -> Submission:
        """
        Entry point called by commands / listeners.  The overall algorithm is
        fixed, but two *hooks* (parse_file & populate_metadata) are delegated to
        subclasses.
        """
        now = uploaded_at_epoch or int(time.time())

        # 1) Make sure a competition is running
        task = await self._task_repo.get_active()
        if task is None:
            raise RuntimeError("No active competition.")

        # 2) Make sure the user exists
        user = await self._user_svc.ensure_user(user_id)

        # 3) Detect / validate team
        team = await self._resolve_team(task, user, team_id)

        # 4) Replace any previous run(s)
        await self._purge_previous_runs(task, user, team)

        # 5) --- game-specific parsing ------------------------------------
        submission_file: SubmissionFile = self.parse_file(file_bytes, now)

        # 6. Build domain entity
        sub = Submission(
            submitted_by=user,
            task=task,
            file=submission_file,
            team=team,
            url=file_url,
        )

        # Add the extra fields (exemple case: character and vehicle for mkwii)
        self.populate_metadata(sub, submission_file)

        # 7. Validate + persist
        sub.validate()
        await self._sub_repo.add(sub)
        return sub

    # ------------------------------------------------------------------ #
    # HOOKS to be overridden in concrete subclasses
    # ------------------------------------------------------------------ #
    @abstractmethod
    def parse_file(self,file_bytes: bytes,uploaded_at_epoch: int) -> SubmissionFile:...


    @abstractmethod
    def populate_metadata(self,sub: Submission,file: SubmissionFile) -> None: ...

    # ------------------------------------------------------------------ #
    # Helpers (shared across all comps)                                  #
    # ------------------------------------------------------------------ #
    async def _resolve_team(self, task: Task, user, team_id):
        if task.team_size <= 1 or task.speed_task or self._team_repo is None:
            return None

        if team_id is None:
            maybe_team = await self._team_repo.get_by_member(user.discord_id)
            team_id = maybe_team.id if maybe_team else None

        if team_id is None:
            return None

        team = await self._team_repo.get_by_id(team_id)
        if not team:
            raise RuntimeError(f"Team #{team_id} not found.")
        return team

    async def _purge_previous_runs(self, task: Task, user, team):
        if team:
            await self._sub_repo.remove_team_submissions(task.id, team.id)
            for m in team.members:
                await self._sub_repo.remove_user_submissions(task.id, m.discord_id)
        else:
            await self._sub_repo.remove_user_submissions(task.id, user.discord_id)

    # ------------------------------------------------------------------ #
    # Other methods (shared across all comps)
    # ------------------------------------------------------------------ #

    async def remove_submission(self, user_id: int) -> Submission:
        """
        Delete the existing submission (solo or team) for the user,
        and return the deleted Submission entity.

        Args:
            user_id (int): Discord ID of the competitor.

        Returns:
            Submission: the entity that was deleted.

        Raises:
            RuntimeError: if no competition or no submission found.
        """
        # 1) Load active or last competition
        task = await self._task_repo.get_active()
        if not task:
            task = await self._task_repo.get_last_task()
        if not task:
            raise RuntimeError("No competition available for editing.")

        # 2) Determine if the user is part of a team
        team = None
        if task.team_size > 1 and not task.speed_task and self._team_repo:
            team = await self._team_repo.get_by_member(user_id)

        # 3) Load the existing submission
        if team:
            sub = await self._sub_repo.get_submission_by_team(task.id, team.id)
        else:
            sub = await self._sub_repo.get_submission_by_user(task.id, user_id)

        if not sub:
            raise RuntimeError("No submission found for this competitor.")

        # 4) Delete via the appropriate repository method
        if team:
            await self._sub_repo.remove_team_submissions(task.id, team.id)
        else:
            await self._sub_repo.remove_user_submissions(task.id, user_id)

        # 5) Return the deleted entity for command feedback
        return sub

    async def get_submissions(self) -> list[Submission]:
        """
        List all submissions for the active competition,
        or if none active, the last one.

        Returns:
            List[Submission]: list of Submission entities.
        """
        task = await self._task_repo.get_active()
        if not task:
            task = await self._task_repo.get_last_task()
        if not task:
            return []

        return await self._sub_repo.get_submissions(task.id)

    async def edit_submission(
        self,
        user_id:    int,
        new_time:   float,
        dq:         bool,
        dq_reason:  Optional[str] = None,
    ) -> Submission:
        """
        Modify the time and disqualification status of a submission
        for the active competition (or the last one if none active).

        Args:
            user_id (int): Discord ID of the competitor.
            new_time (float): updated run time.
            dq (bool): whether to disqualify the submission.
            dq_reason (Optional[str]): reason for disqualification.

        Returns:
            Submission: the updated submission entity.

        Raises:
            RuntimeError: if no competition or submission found.
        """
        # 1) Load active or last competition
        task = await self._task_repo.get_active()
        if not task:
            task = await self._task_repo.get_last_task()
        if not task:
            raise RuntimeError("No competition available for editing.")

        # 2) Determine if user is in a team
        team = None
        if task.team_size > 1 and not task.speed_task and self._team_repo:
            team = await self._team_repo.get_by_member(user_id)

        # 3) Load the existing submission
        if team:
            sub = await self._sub_repo.get_submission_by_team(task.id, team.id)
        else:
            sub = await self._sub_repo.get_submission_by_user(task.id, user_id)

        if not sub:
            raise RuntimeError("No submission found for this competitor.")

        # 4) Apply updates
        sub.time = new_time
        sub.dq = dq
        sub.dq_reason = dq_reason if dq else None

        # 5) Persist changes
        await self._sub_repo.save(sub)
        return sub

