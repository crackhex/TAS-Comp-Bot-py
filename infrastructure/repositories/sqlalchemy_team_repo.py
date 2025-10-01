"""
SQLAlchemy Team Repository
==========================

Module path:
    src/infrastructure/repositories/sqlalchemy_team_repo.py

Summary:
    Async SQLAlchemy implementation of the TeamRepository interface.

Responsibilities:
    - add(team): insert a new Team and assign its ID
    - save(team): update a Team
    - get_by_id(team_id): load a Team by its primary key
    - get_by_member(user_id): find a Team containing a specific member
    - get_teams(): list all Teams
    - remove(team_id): delete a Team by its ID
    - clear_all(): delete all Team records
"""
from typing import List, Optional

from sqlalchemy import select, or_, delete

from infrastructure.db import SessionLocal
from infrastructure.orm.orm_models import TeamORM
from domain.entities import Team
from domain.repositories import TeamRepository, UserRepository


class SqlAlchemyTeamRepository(TeamRepository):
    """
    Async SQLAlchemy implementation of TeamRepository.
    Handles Team persistence and reconstruction.
    """

    def __init__(
        self,
        user_repo: UserRepository,
        session_factory=SessionLocal,
    ):
        """
        Initialize with a UserRepository and a session factory.

        Args:
            user_repo (UserRepository): repository for loading User entities.
            session_factory: callable returning an async SQLAlchemy Session.
        """
        self._sf = session_factory
        self._user_repo = user_repo

    async def add(self, team: Team) -> None:
        """
        Insert a new Team into the database and update its domain ID.

        Args:
            team (Team): the Team entity to persist. Its `id` will be set after commit.

        Returns:
            None
        """
        async with self._sf() as sess:
            orm = TeamORM.from_domain(team)
            sess.add(orm)
            await sess.commit()
            team.id = orm.id  # propagate generated PK back to domain

    async def save(self, team: Team) -> None:
        """
        Update a Team using SQLAlchemy merge().

        Args:
            team (Team): the Team entity with updated state.

        Returns:
            None
        """
        async with self._sf() as sess:
            await sess.merge(TeamORM.from_domain(team))
            await sess.commit()

    async def get_by_id(self, team_id: int) -> Team | None:
        """
        Load a Team by its primary key.

        Args:
            team_id (int): the ID of the Team to retrieve.

        Returns:
            Team | None: the Team entity if found, otherwise None.
        """
        async with self._sf() as sess:
            orm = await sess.get(TeamORM, team_id)
            if not orm:
                return None
            # reconstruct domain Team by loading each member
            leader = await self._user_repo.get_by_discord_id(orm.leader_id)
            team = Team(name=orm.team_name, leader=leader)
            team.id = orm.id

            # add additional members if present
            for uid in (orm.user2_id, orm.user3_id, orm.user4_id):
                if uid is not None:
                    user = await self._user_repo.get_by_discord_id(uid)
                    team.add_member(user)
            return team

    async def get_by_member(self, user_id: int) -> Team | None:
        """
        Find the Team that includes a given user.

        Args:
            user_id (int): the Discord ID of the user.

        Returns:
            Team | None: the Team containing the user, or None if not found.
        """
        async with self._sf() as sess:
            # filter on leader or any member slot
            stmt = select(TeamORM).where(
                or_(
                    TeamORM.leader_id == user_id,
                    TeamORM.user2_id  == user_id,
                    TeamORM.user3_id  == user_id,
                    TeamORM.user4_id  == user_id,
                )
            )
            orm = (await sess.scalars(stmt)).first()
            if not orm:
                return None
            # same reconstruction as get_by_id
            leader = await self._user_repo.get_by_discord_id(orm.leader_id)
            team = Team(name=orm.team_name, leader=leader)
            team.id = orm.id
            for uid in (orm.user2_id, orm.user3_id, orm.user4_id):
                if uid is not None:
                    user = await self._user_repo.get_by_discord_id(uid)
                    team.add_member(user)
            return team

    async def get_teams(self) -> List[Team]:
        """
        Retrieve all existing Teams.

        Returns:
            List[Team]: list of all Team entities (empty if none).
        """
        async with self._sf() as sess:
            # 1) retrieve all ORM records
            stmt = select(TeamORM)
            result = await sess.scalars(stmt)
            orm_list = result.all()

            teams: List[Team] = []
            # 2) reconstruct each Team domain entity
            for orm in orm_list:
                leader = await self._user_repo.get_by_discord_id(orm.leader_id)
                team = Team(name=orm.team_name, leader=leader)
                team.id = orm.id

                # add members from user2_id, user3_id, user4_id
                for uid in (orm.user2_id, orm.user3_id, orm.user4_id):
                    if uid is not None:
                        user = await self._user_repo.get_by_discord_id(uid)
                        team.add_member(user)

                teams.append(team)

            return teams


    async def remove(self, team_id: int) -> None:
        """
        Delete a Team by its ID.

        Args:
            team_id (int): the ID of the Team to remove.

        Returns:
            None
        """
        async with self._sf() as sess:
            await sess.execute(
                delete(TeamORM).where(TeamORM.id == team_id)
            )
            await sess.commit()

    async def clear_all(self) -> None:
        """
        Delete all Teams (to be called at the end of a competition).

        Returns:
            None
        """
        async with self._sf() as sess:
            await sess.execute(delete(TeamORM))
            await sess.commit()
