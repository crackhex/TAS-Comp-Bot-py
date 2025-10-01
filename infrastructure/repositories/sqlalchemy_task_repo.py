"""
SQLAlchemy Task Repository
==========================

Module path:
    src/infrastructure/repositories/sqlalchemy_task_repo.py

Summary:
    Async SQLAlchemy implementation of the TaskRepository interface.

Responsibilities:
    - add(task): insert a new Task and assign its ID
    - save(task): update an existing Task via merge()
    - get_by_id(id): load a Task by its primary key
    - get_last_task(): fetch the most recently inserted Task
    - get_active(): fetch the currently active Task (is_active == True)
"""
from sqlalchemy import select, desc
from infrastructure.db import SessionLocal
from infrastructure.orm.orm_models import TaskORM
from domain.entities import Task
from domain.repositories import TaskRepository


class SqlAlchemyTaskRepository(TaskRepository):
    """
    Async SQLAlchemy implementation of TaskRepository.
    Manages persistence of Task entities in the database.
    """

    def __init__(self, session_factory=SessionLocal):
        """
        Initialize with a session factory.

        Args:
            session_factory: a callable that returns an async SQLAlchemy Session.
        """
        self._sf = session_factory

    async def add(self, task: Task) -> None:
        """
        Insert a new Task into the database and update its domain ID.

        Args:
            task (Task): the Task entity to insert. Its `id` will be set after commit.

        Returns:
            None
        """
        async with self._sf() as sess:
            orm = TaskORM.from_domain(task)
            sess.add(orm)
            await sess.commit()
            task.id = orm.id  # propagate generated PK back to domain

    async def save(self, task: Task) -> None:
        """
        Update an existing Task in the database via SQLAlchemy merge().

        Args:
            task (Task): the Task entity with modified state to persist.

        Returns:
            None
        """
        async with self._sf() as sess:
            await sess.merge(TaskORM.from_domain(task))
            await sess.commit()

    async def get_by_id(self, id: int) -> Task | None:
        """
        Load a Task by its primary key.

        Args:
            id (int): the ID of the Task to retrieve.

        Returns:
            Task | None: the Task entity if found, otherwise None.
        """
        async with self._sf() as sess:
            orm = await sess.get(TaskORM, id)
            return orm.to_domain() if orm else None

    async def get_last_task(self) -> Task | None:
        """
        Fetch the most recently inserted Task, based on descending ID.

        Returns:
            Task | None: the last Task if any exist, otherwise None.
        """
        async with self._sf() as sess:
            # order by primary key descending and take first
            stmt = (
                select(TaskORM)
                .order_by(desc(TaskORM.id))
                .limit(1)
            )
            orm = await sess.scalar(stmt)
            return orm.to_domain() if orm else None

    async def get_active(self) -> Task | None:
        """
        Fetch the currently active Task (where is_active == True).

        Returns:
            Task | None: the active Task if one exists, otherwise None.
        """
        async with self._sf() as sess:
            row = (await sess.scalars(
                select(TaskORM).where(TaskORM.is_active == True)
            )).first()
            return row.to_domain() if row else None
