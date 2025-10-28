"""
SQLAlchemy Submission Repository
================================

Module path:
    src/infrastructure/repositories/sqlalchemy_submission_repo.py

Summary:
    Async SQLAlchemy implementation of the SubmissionRepository interface.

Responsibilities:
    - add(sub): insert a Submission (solo or team)
    - save(sub): save a submission with a modified state (example: editing a time)
    - remove_user_submissions(task_id, user_id): delete submissions for a solo user
    - remove_team_submissions(task_id, team_id): delete submission for a team
    - get_submission_by_user(task_id, user_id): load a solo submission
    - get_submission_by_team(task_id, team_id): load a team submission
    - get_submissions(task_id): list all submissions for a task
    - clear_all(): delete all submissions (after a competition)
"""
from typing import Optional
from sqlalchemy import select, delete

from infrastructure.db import SessionLocal
from infrastructure.orm.orm_models import SubmissionORM
from domain.entities import Submission, SubmissionFile
from domain.repositories import (
    SubmissionRepository,
    UserRepository,
    TaskRepository,
    TeamRepository,
)


class SqlAlchemySubmissionRepository(SubmissionRepository):
    """
    Async SQLAlchemy implementation of SubmissionRepository.
    Manages persistence of Submission entities, both solo and team-based.
    """

    def __init__(
        self,
        user_repo: UserRepository,
        task_repo: TaskRepository,
        team_repo: Optional[TeamRepository] = None,
        session_factory=SessionLocal,
    ):
        self._sf        = session_factory
        self._user_repo = user_repo
        self._task_repo = task_repo
        self._team_repo = team_repo

    async def add(self, sub: Submission) -> None:
        """
        Insert a submission in the database.

        Args:
            sub (Submission): the submission to persist.

        Returns:
            None
        """
        async with self._sf() as sess:
            if sub.team:
                stmt = select(SubmissionORM).where(
                    SubmissionORM.task_id == sub.task.id,
                    SubmissionORM.team_id == sub.team.id,
                )
            else:
                stmt = select(SubmissionORM).where(
                    SubmissionORM.task_id == sub.task.id,
                    SubmissionORM.user_id == sub.submitted_by.discord_id,
                )

            existing = (await sess.scalars(stmt)).first()

            orm = SubmissionORM.from_domain(sub)
            if existing:
                # IMPORTANT:
                # We do NOT want to create a new row and get a new PK,
                # we want to UPDATE the existing row so ordering is stable.
                orm.id = existing.id

            await sess.merge(orm)
            await sess.commit()

            # Push the PK back to the domain entity
            sub.id = orm.id

    async def save(self, sub: Submission) -> None:
        """
        Update one or more fields of an existing Submission in the database,
        using SQLAlchemy’s merge() to persist the changes.

        Args:
            sub (Submission): the submission entity with updated state.

        Returns:
            None
        """
        async with self._sf() as sess:
            await sess.merge(SubmissionORM.from_domain(sub))
            await sess.commit()

    async def remove_user_submissions(self, task_id: int, user_id: int) -> None:
        """
        Delete the solo submission (team_id IS NULL) for a given user and task.

        Args:
            task_id (int): the ID of the task/competition.
            user_id (int): the Discord ID of the user.

        Returns:
            None
        """
        async with self._sf() as sess:
            await sess.execute(
                delete(SubmissionORM).where(
                    SubmissionORM.task_id == task_id,
                    SubmissionORM.user_id == user_id,
                    SubmissionORM.team_id.is_(None),
                )
            )
            await sess.commit()

    async def remove_team_submissions(self, task_id: int, team_id: int) -> None:
        """
        Delete the submission associated with a team for a given task.

        Args:
            task_id (int): the ID of the task/competition.
            team_id (int): the ID of the team.

        Returns:
            None
        """
        async with self._sf() as sess:
            await sess.execute(
                delete(SubmissionORM).where(
                    SubmissionORM.task_id == task_id,
                    SubmissionORM.team_id == team_id,
                )
            )
            await sess.commit()

    async def get_submission_by_user(self, task_id: int, user_id: int) -> Optional[Submission]:
        """
        Load a solo submission for a specific user and task.

        Args:
            task_id (int): the ID of the task/competition.
            user_id (int): the Discord ID of the user.

        Returns:
            Optional[Submission]: the Submission if found, else None.
        """
        async with self._sf() as sess:
            row = await sess.scalar(
                select(SubmissionORM).where(
                    SubmissionORM.task_id == task_id,
                    SubmissionORM.user_id == user_id,
                    SubmissionORM.team_id.is_(None),
                )
            )
        if not row:
            return None

        # Reconstruct domain objects
        user = await self._user_repo.get_by_discord_id(user_id)
        task = await self._task_repo.get_by_id(task_id)
        file = SubmissionFile(path=row.url, uploaded_at=row.uploaded_at)
        return row.to_domain(user=user, task=task, file=file, team=None)

    async def get_submission_by_team(self, task_id: int, team_id: int) -> Optional[Submission]:
        """
        Load a team submission for a specific team and task.

        Args:
            task_id (int): the ID of the task/competition.
            team_id (int): the ID of the team.

        Returns:
            Optional[Submission]: the Submission if found, else None.
        """
        async with self._sf() as sess:
            row = await sess.scalar(
                select(SubmissionORM).where(
                    SubmissionORM.task_id == task_id,
                    SubmissionORM.team_id == team_id,
                )
            )
        if not row:
            return None

        # Reconstruct domain objects
        user = await self._user_repo.get_by_discord_id(row.user_id)
        task = await self._task_repo.get_by_id(task_id)
        team = await self._team_repo.get_by_id(team_id) if self._team_repo else None
        file = SubmissionFile(path=row.url, uploaded_at=row.uploaded_at)
        return row.to_domain(user=user, task=task, file=file, team=team)

    async def get_submissions(self, task_id: int) -> list[Submission]:
        """
        List all submissions for a given task, in insertion order.

        Args:
            task_id (int): the ID of the task/competition.

        Returns:
            List[Submission]: all Submission objects for the task.
        """
        async with self._sf() as sess:
            rows = (await sess.scalars(
                select(SubmissionORM).where(SubmissionORM.task_id == task_id)
            )).all()

        result: list[Submission] = []
        for orm in rows:
            user = await self._user_repo.get_by_discord_id(orm.user_id)
            task = await self._task_repo.get_by_id(task_id)
            team = None

            # Verify if it's a team submission
            if orm.team_id and self._team_repo:
                team = await self._team_repo.get_by_id(orm.team_id)


            file = SubmissionFile(path=orm.url, uploaded_at=orm.uploaded_at)

            # Build domain submission object and add to list
            result.append(
                orm.to_domain(user=user, task=task, file=file, team=team)
            )
        return result

    async def clear_all(self) -> None:
        """
        Delete all Submission rows (to be called at the end of a competition).

        Returns:
            None
        """
        async with self._sf() as sess:
            await sess.execute(delete(SubmissionORM))
            await sess.commit()
