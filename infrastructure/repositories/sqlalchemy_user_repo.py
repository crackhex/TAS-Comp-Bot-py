"""
SQLAlchemy User Repository
==========================

Module path:
    src/infrastructure/repositories/sqlalchemy_user_repo.py

Summary:
    Async SQLAlchemy implementation of the UserRepository interface.

Responsibilities:
    - add(user): insert a new User or update existing handle/display_name
    - save(user): update an existing User’s handle and display_name
    - get_by_discord_id(discord_id): load a User by Discord ID
"""
from typing import List

from sqlalchemy import select, update
from infrastructure.db import SessionLocal
from infrastructure.orm.orm_models import UserORM
from domain.entities import User
from domain.repositories import UserRepository


class SqlAlchemyUserRepository(UserRepository):
    """
    Async SQLAlchemy implementation of UserRepository.
    Manages persistence of User entities (handle, display_name) in the database.
    """

    def __init__(self, session_factory=SessionLocal):
        """
        Initialize with a session factory.

        Args:
            session_factory: callable returning an async SQLAlchemy Session.
        """
        self._sf = session_factory

    async def add(self, user: User) -> None:
        """
        Insert a new User in the database.

        Args:
            user (User): the User domain entity to persist. Its `id` will be set after commit.

        Returns:
            None
        """
        async with self._sf() as sess:
            orm = UserORM.from_domain(user)
            sess.add(orm)
            await sess.commit()
            user.id = orm.index

    async def save(self, user: User) -> None:
        """
        Update an existing User’s handle and/or display_name.

        Args:
            user (User): the User entity with updated state.

        Returns:
            None
        """
        async with self._sf() as sess:
            # Perform an UPDATE based on discord_id
            await sess.execute(
                update(UserORM)
                .where(UserORM.user_id == user.discord_id)
                .values(
                    user=user.handle,
                    display_name=user.display_name,
                )
            )
            await sess.commit()


    async def get_by_discord_id(self, discord_id: int) -> User | None:
        """
        Load a User by their Discord ID.

        Args:
            discord_id (int): the Discord user ID to look up.

        Returns:
            User | None: the User entity if found, otherwise None.
        """
        async with self._sf() as sess:
            row = (await sess.scalars(
                select(UserORM).where(UserORM.user_id == discord_id)
            )).first()
        return row.to_domain() if row else None

    async def list_users(self) -> List[User]:
        """
        Return the full list of users in the database as domain User objects.

        Returns:
            List[User]: all users persisted in the database.
        """
        async with self._sf() as sess:
            rows = (await sess.scalars(select(UserORM))).all()
        return [r.to_domain() for r in rows] if rows else []
