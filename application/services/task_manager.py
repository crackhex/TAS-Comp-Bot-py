"""
Task Manager Service
====================

Module path:
    src/application/services/task_manager.py

Summary:
    Application service for orchestrating the lifecycle of Tasks,
    including starting & ending tasks, updating deadlines, and releasing speed-tasks.

Responsibilities:
    - start_task: perform a full reset and open a new competition
    - end_task: close an existing competition and clear speed-task description
    - set_deadline: update the absolute deadline of the active competition
    - release_speed_task: Publish & reveal a speed-task once its hidden phase ends
    - get_active_task: retrieve the currently active competition
    - get_last_task: retrieve the most recently created competition
"""

import time

from domain.entities import Task
from application.models import TaskConfig
from domain.repositories import (
    TaskRepository,
    SubmissionRepository,
    TeamRepository,
    SpeedTaskRepository,
)
from application.services.config_service import ConfigService


class TaskManager:
    """
    Coordinates use cases around Task lifecycle management.
    Depends on repository interfaces and configuration service.
    """

    def __init__(
        self,
        task_repo: TaskRepository,
        config_service: ConfigService,
        submission_repo: SubmissionRepository,
        team_repo: TeamRepository,
        speed_repo: SpeedTaskRepository,
    ):
        """
        Initialize TaskManager with required dependencies.

        Args:
            task_repo (TaskRepository): for persisting Task entities.
            config_service (ConfigService): for reading/clearing config.
            submission_repo (SubmissionRepository): for clearing submissions.
            team_repo (TeamRepository): for clearing teams.
            speed_repo (SpeedTaskRepository): for clearing speed-task sessions.
        """
        self._task_repo = task_repo
        self._cfg       = config_service
        self._sub_repo  = submission_repo
        self._team_repo = team_repo
        self._speed_repo= speed_repo

    async def start_task(self, cfg: TaskConfig) -> Task:
        """
        Start a new competition with the given configuration.

        This method:
        0) Clears all previous submissions, teams, and speed-task sessions.
        1) Verifies no competition is currently active.
        2) Creates, opens, and persists the new Task.

        Args:
            cfg (TaskConfig): validated parameters for the new competition.

        Returns:
            Task: the newly created and persisted Task.

        Raises:
            RuntimeError: if a competition is already active.
        """
        # 0) "Grand reset" before starting a new competition
        await self._sub_repo.clear_all()
        await self._team_repo.clear_all()
        await self._speed_repo.clear_all()

        # 1) Ensure no active competition exists
        if await self._task_repo.get_active():
            raise RuntimeError("A competition is already in progress.")

        # 2) Instantiate domain Task and open it
        task = Task(
            number=cfg.number,
            year=cfg.year,
            team_size=cfg.team_size,
            speed_task=cfg.speed_task,
            deadline_epoch=cfg.deadline,
        )

        task.open()

        # Persist the new Task
        await self._task_repo.add(task)
        return task

    async def end_task(self, task_id: int) -> Task:
        """
        Close the competition (stop accepting submissions).

        Args:
            task_id (int): ID of the Task to close.

        Returns:
            Task: the Task entity after closing.

        Raises:
            RuntimeError: if the Task is not found.
        """
        # 1) Load the Task by ID
        task = await self._task_repo.get_by_id(task_id)
        if not task:
            raise RuntimeError("Task not found.")

        # 2) Close the Task and persist changes
        task.close()
        await self._task_repo.save(task)

        # 3) Clear any speed-task description in config
        await self._cfg.clear_speed_task_desc()
        return task

    async def set_deadline(self, new_deadline_epoch: int) -> None:
        """
        Update the absolute deadline of the active competition.

        Args:
            new_deadline_epoch (int): UNIX timestamp for the new deadline.

        Raises:
            RuntimeError: if no competition is currently active.
        """
        # 1) Retrieve active Task
        task = await self._task_repo.get_active()
        if not task:
            raise RuntimeError("No active competition.")

        # 2) Update deadline and persist
        task.deadline = new_deadline_epoch
        await self._task_repo.save(task)

    async def release_speed_task(self, comp: str) -> Task:
        """
        Publish a speed-task once its hidden phase ends.

        Args:
            comp (str): competition key to load speed-task length.

        Returns:
            Task: the Task entity after publishing.

        Raises:
            RuntimeError: if no active competition, length not configured,
                          or hidden phase still in progress.
        """
        # 1) Load the active Task
        task = await self._task_repo.get_active()
        if not task:
            raise RuntimeError("No active competition to release.")

        # 2) Load configured speed-task length
        length_cfg = await self._cfg.get_speed_task_length(comp)
        if not length_cfg:
            raise RuntimeError("Speed-task length not configured.")

        length_sec = int(length_cfg.time * 3600) # hours → seconds

        # 3) Compute release epoch and compare to now
        release_epoch = task.deadline - length_sec
        now = int(time.time())
        if now < release_epoch:
            raise RuntimeError("Hidden phase is still in progress.")

        # 4) Publish the speed-task and persist
        task.publish()
        await self._task_repo.save(task)
        return task

    async def get_active_task(self) -> Task | None:
        """
        Retrieve the currently active competition.

        Returns:
            Task | None: the active Task, or None if none active.
        """
        return await self._task_repo.get_active()

    async def get_last_task(self) -> Task | None:
        """
        Retrieve the most recently created competition.

        Returns:
            Task | None: the last Task, or None if none exist.
        """
        return await self._task_repo.get_last_task()
