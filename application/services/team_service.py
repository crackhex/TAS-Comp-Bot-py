"""
Team Service
============

Module path:
    src/application/services/team_service.py

Summary:
    Application service to manage teams, including creation,
    member management, deletion, and retrieval.

Responsibilities:
    - create_team: create a new team with leader and members
    - add_member: add a user to an existing team
    - remove_member: remove a user from a team
    - dissolve_team: delete a team entirely
    - get_team_by_member: fetch the team a user belongs to
    - get_all_teams: list all teams
    - rename_team: change a team's name
"""

from typing import List, Optional

from application.services.user_service import UserService
from domain.entities import Team
from domain.repositories import TeamRepository, UserRepository, TaskRepository


class TeamService:
    """
    Coordinates domain and repository operations for team management.
    """

    def __init__(
        self,
        user_svc: UserService,
        team_repo: TeamRepository,
        user_repo: UserRepository,
        task_repo: TaskRepository,
    ):
        """
        Initialize TeamService with required dependencies.

        Args:
            user_svc (UserService): service to ensure or fetch users.
            team_repo (TeamRepository): repository for persisting teams.
            user_repo (UserRepository): repository for fetching users.
            task_repo (TaskRepository): repository for fetching current task.
        """
        self._user_svc = user_svc
        self._team_repo = team_repo
        self._user_repo = user_repo
        self._task_repo = task_repo

    async def create_team(
        self,
        leader_discord_id: int,
        member_ids: List[int],
        name: Optional[str] = None,
    ) -> Team:
        """
        Create a new team with a designated leader and optional members.

        Args:
            leader_discord_id (int): Discord ID of the team leader.
            member_ids (List[int]): Discord IDs of additional members.
            name (Optional[str]): optional team name.

        Returns:
            Team: the newly created team domain entity.

        Raises:
            RuntimeError: if no active competition, teams are not allowed,
                          or team size exceeds the configured limit.
        """
        # 1) Verify there is an active team-based competition
        task = await self._task_repo.get_active()
        if not task:
            raise RuntimeError("No active competition.")
        if task.team_size <= 1:
            raise RuntimeError("This competition does not allow teams.")

        # 2) Ensure the leader user exists or is created
        leader = await self._user_svc.ensure_user(leader_discord_id)

        # 3) Instantiate the Team domain entity
        team = Team(name=name, leader=leader)

        # 4) Add each provided member, enforcing team size limit
        for uid in member_ids:
            if uid == leader_discord_id:
                continue
            user = await self._user_svc.ensure_user(uid)

            if len(team.members) >= task.team_size:
                raise RuntimeError(
                    f"Maximum team size reached ({len(team.members)}/{task.team_size})."
                )
            team.add_member(user)

        # 5) Persist the new team via repository
        await self._team_repo.add(team)
        return team

    async def add_member(
        self,
        team_id: int,
        user_discord_id: int,
    ) -> Team:
        """
        Add a single user to an existing team.

        Args:
            team_id (int): ID of the team to update.
            user_discord_id (int): Discord ID of the user to add.

        Returns:
            Team: the updated team domain entity.

        Raises:
            RuntimeError: if team not found, no active competition,
                          teams not allowed, or team is already full.
        """
        # 1) Fetch the existing team
        team = await self._team_repo.get_by_id(team_id)
        if not team:
            raise RuntimeError(f"Team #{team_id} not found.")

        # 2) Verify there is an active team-based competition
        task = await self._task_repo.get_active()
        if not task:
            raise RuntimeError("No active competition.")
        if task.team_size <= 1:
            raise RuntimeError("This competition does not allow teams.")

        # 3) Enforce capacity constraint
        if len(team.members) >= task.team_size:
            raise RuntimeError(
                f"Maximum team size reached ({len(team.members)}/{task.team_size})."
            )

        # 4) Ensure the user exists, if not, add him to database.
        user = await self._user_svc.ensure_user(user_discord_id)

        # 5) Add member and persist changes
        team.add_member(user)
        await self._team_repo.save(team)
        return team

    async def remove_member(self, team_id: int, user_discord_id: int) -> Team:
        """
        Remove a user from an existing team.

        Args:
            team_id (int): ID of the team.
            user_discord_id (int): Discord ID of the user to remove.

        Returns:
            Team: the updated team domain entity.

        Raises:
            RuntimeError: if team or user not found.
        """
        # 1) Fetch team and user
        team = await self._team_repo.get_by_id(team_id)
        if not team:
            raise RuntimeError(f"Team #{team_id} not found.")
        user = await self._user_repo.get_by_discord_id(user_discord_id)
        if not user:
            raise RuntimeError(f"User {user_discord_id} not found.")

        # 2) Remove member via domain logic and persist
        team.remove_member(user)
        await self._team_repo.save(team)
        return team

    async def dissolve_team(self, team_id: int) -> None:
        """
        Delete a team entirely.

        Args:
            team_id (int): ID of the team to remove.

        Raises:
            RuntimeError: if the team does not exist.
        """
        # 1) Verify the team exists
        team = await self._team_repo.get_by_id(team_id)
        if not team:
            raise RuntimeError(f"Team #{team_id} not found.")

        # 2) Delegate removal to the repository
        await self._team_repo.remove(team_id)

    async def get_team_by_member(self, user_id: int) -> Team | None:
        """
        Retrieve the team that a given user belongs to.

        Args:
            user_id (int): Discord ID of the user.

        Returns:
            Team | None: the team entity or None if user has no team.
        """
        return await self._team_repo.get_by_member(user_id)

    async def get_all_teams(self) -> List[Team] | None:
        """
        List all existing teams.

        Returns:
            List[Team] | None: list of all teams, or None if none exist.
        """
        return await self._team_repo.get_teams()

    async def rename_team(self, team_id: int, new_name: str) -> None:
        """
        Change the name of an existing team.

        Args:
            team_id (int): ID of the team to rename.
            new_name (str): the new team name.

        Raises:
            RuntimeError: if team not found.
        """
        team = await self._team_repo.get_by_id(team_id)
        if not team:
            raise RuntimeError("Team not found.")
        team.name = new_name.strip()
        await self._team_repo.save(team)
