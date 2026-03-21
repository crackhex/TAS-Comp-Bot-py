"""
SQLAlchemy Speed Task Repository
================================

Module path:
    src/infrastructure/repositories/sqlalchemy_speedtask_repo.py

Summary:
    Async SQLAlchemy implementation of the SpeedTaskRepository interface.

Responsibilities:
    - add(session): insert or update a SpeedTaskSession
    - save(session): Save a speed-task session with a modified state
    - get_by_user(user_id): load a session by Discord user ID
    - list_active_sessions(): list all active sessions
    - expire_session(user_id): mark a session inactive (ended) and return it
    - cancel_session(user_id): Cancel/clear a user's session
    - clear_all(): delete all speed‑task sessions
"""
from sqlalchemy import select, delete
from infrastructure.db import SessionLocal
from infrastructure.orm.orm_models import SpeedTaskSessionORM
from domain.entities import SpeedTaskSession
from domain.repositories import SpeedTaskRepository, TaskRepository, UserRepository


class SqlAlchemySpeedTaskRepository(SpeedTaskRepository):
    """
    Async SQLAlchemy implementation of SpeedTaskRepository.
    Manages personal speed‑task sessions in the database.
    """

    def __init__(
        self,
        user_repo: UserRepository,
        task_repo: TaskRepository,
        session_factory=SessionLocal,
    ):
        self._sf        = session_factory
        self._user_repo = user_repo
        self._task_repo = task_repo

    async def add(self, sess: SpeedTaskSession) -> None:
        """
        Insert a user's SpeedTaskSession (primary key = user_id).
        This is called when a user requests to start competing in a speed task.

        Args:
            sess (SpeedTaskSession): the session to add or update.

        Returns:
            None
        """
        async with self._sf() as db:
            orm = SpeedTaskSessionORM.from_domain(sess)
            await db.merge(orm)
            await db.commit()

    async def save(self, session_obj: SpeedTaskSession) -> None:
        """
        Update one or more fields of an existing Speed task session in the database,
        using SQLAlchemy’s merge() to persist the changes.

        Args:
            session_obj (SpeedTaskSession): the session with updated state.

        Returns:
            None
        """
        async with self._sf() as sess:
            orm = SpeedTaskSessionORM.from_domain(session_obj)
            await sess.merge(orm)
            await sess.commit()

    async def get_by_user(self, user_id: int) -> SpeedTaskSession | None:
        """
        Return the SpeedTaskSession for the given Discord user ID, or None if not found.

        Args:
            user_id (int): Discord user ID.

        Returns:
            Optional[SpeedTaskSession]: the session object, or None if it does not exist.
        """
        async with self._sf() as sess:
            stmt = select(SpeedTaskSessionORM).where(
                SpeedTaskSessionORM.user_id == user_id
            )
            orm = (await sess.scalars(stmt)).first()
            if not orm:
                return None

            user = await self._user_repo.get_by_discord_id(orm.user_id)
            task = await self._task_repo.get_active()
            return SpeedTaskSession(
                user              = user,
                task              = task,
                personal_deadline = orm.end_time,
                active            = orm.active,
            )

    async def list_active_sessions(self) -> list[SpeedTaskSession]:
        """
        Return all SpeedTaskSession objects whose 'active' flag is True.
        This

        Returns:
            List[SpeedTaskSession]: list of active sessions.
        """
        async with self._sf() as db:
            orms = (await db.scalars(
                select(SpeedTaskSessionORM)
                .where(SpeedTaskSessionORM.active == True)
            )).all()

        result: list[SpeedTaskSession] = []
        for orm in orms:
            user = await self._user_repo.get_by_discord_id(orm.user_id)
            task = await self._task_repo.get_active()
            result.append(
                SpeedTaskSession(
                    user              = user,
                    task              = task,
                    personal_deadline = orm.end_time,
                    active            = orm.active,
                )
            )
        return result

    async def expire_session(self, user_id: int) -> SpeedTaskSession:
        """
        Mark the session for the given user_id as inactive (which means their time is up), then return the updated session.

        Args:
            user_id (int): Discord user ID whose session must be expired.

        Returns:
            SpeedTaskSession: the session object after expiration.

        Raises:
            RuntimeError: if no session exists or reload fails.
        """
        async with self._sf() as db:
            orm = await db.get(SpeedTaskSessionORM, user_id)
            if not orm:
                raise RuntimeError(f"No session found for user {user_id}")
            orm.active = False
            await db.commit()

        session = await self.get_by_user(user_id)
        if not session:
            raise RuntimeError("Failed to reload session after expiring.")
        return session

    async def cancel_session(self, user_id) -> None:
        """
        Delete a user's session.

        Args:
            user_id (int): Discord user ID whose session must be canceled.

        Returns:
            None
        """
        async with self._sf() as db:
            await db.execute(delete(SpeedTaskSessionORM).where(SpeedTaskSessionORM.user_id == user_id))
            await db.commit()

    async def clear_all(self) -> None:
        """
        Delete all SpeedTaskSession rows (to be called at the end of a competition).

        Returns:
            None
        """
        async with self._sf() as db:
            await db.execute(delete(SpeedTaskSessionORM))
            await db.commit()


