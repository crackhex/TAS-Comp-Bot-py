# """
# Submission Service
# ==================
#
# Module path:
#     src/application/services/submission_service.py
#
# Summary:
#     Application service to handle run submissions for solo, teams, and speed‑tasks.
#
# Responsibilities:
#     - submit: Validate, parse and persist a new submission
#     - remove_submission: delete an existing submission (solo or team) and return it
#     - get_submissions: retrieve all submissions for current or last task
#     - edit_submission: update time, DQ status, and reason on an existing submission
# """
#
# import time
# from typing import Optional
#
# from application.services.user_service import UserService
# from domain.entities import Submission
# from domain.repositories import (
#     SubmissionRepository,
#     TaskRepository,
#     UserRepository,
#     TeamRepository,
# )
# from application.parsers.file_parser import FileParser
# from domain.repositories import SpeedTaskRepository
#
#
# class SubmissionService:
#     """
#     Coordinates parsing, validation, and persistence of submissions.
#     Supports solo runs, team runs, and speed‑task runs.
#     """
#
#     def __init__(
#         self,
#         user_svc: UserService,
#         submission_repo: SubmissionRepository,
#         task_repo: TaskRepository,
#         user_repo: UserRepository,
#         file_parser: FileParser,
#         team_repo: Optional[TeamRepository] = None,
#         speed_repo: Optional[SpeedTaskRepository] = None,
#     ):
#         """
#         Args:
#             user_svc (UserService): service for ensuring and loading users.
#             submission_repo (SubmissionRepository): repository for persisting submissions.
#             task_repo (TaskRepository): repository for loading tasks.
#             user_repo (UserRepository): repository for loading users.
#             file_parser (FileParser): parser for submission file bytes.
#             team_repo (Optional[TeamRepository]): repository for loading teams.
#             speed_repo (Optional[SpeedTaskRepository]): repository for speed-task sessions.
#         """
#         self._user_svc    = user_svc
#         self._sub_repo    = submission_repo
#         self._task_repo   = task_repo
#         self._user_repo   = user_repo
#         self._parser      = file_parser
#         self._team_repo   = team_repo
#         self._speed_repo  = speed_repo
#
#     async def submit(
#         self,
#         user_id: int,
#         file_bytes: bytes,
#         file_url: str,
#         *,
#         uploaded_at_epoch: int | None = None,
#         team_id:           int | None = None,
#     ) -> Submission:
#         """
#         Parse and persist a new submission for the active competition.
#
#         Automatically handles team detection, replaces any prior submission
#         (solo or team), selects the correct parser strategy based on competition
#         settings, and sets time, character, and vehicle fields.
#
#         Args:
#             user_id (int): Discord ID of the submitting user.
#             file_bytes (bytes): raw bytes of the submission file.
#             file_url (str): URL or path to the submitted file.
#             uploaded_at_epoch (int | None): optional UNIX timestamp override.
#             team_id (int | None): optional team ID for team submissions.
#
#         Returns:
#             Submission: the persisted submission entity.
#
#         Raises:
#             RuntimeError: if no active competition or team not found.
#             ValueError: if the selected parser does not support the file format.
#         """
#         now = uploaded_at_epoch or int(time.time())
#
#         # 1) Check that a competition is active
#         task = await self._task_repo.get_active()
#         if not task:
#             raise RuntimeError("No active competition.")
#
#         # 2) Ensure the User exists in the database
#         user = await self._user_svc.ensure_user(user_id)
#
#         # 3) Auto-detect team if applicable (non-speed, team competitions)
#         if task.team_size > 1 and team_id is None and not task.speed_task:
#             t = await self._team_repo.get_by_member(user.discord_id)
#             team_id = t.id if t else None
#
#         # 4) Replace any prior submission for this competitor
#         if team_id is None:
#             # Solo submission: remove previous solo for this user
#             await self._sub_repo.remove_user_submissions(task.id, user.discord_id)
#             team = None
#         else:
#             # Team submission: remove prior team run, then clear any solo runs
#             await self._sub_repo.remove_team_submissions(task.id, team_id)
#             team = await self._team_repo.get_by_id(team_id)
#             if not team:
#                 raise RuntimeError(f"Team #{team_id} not found.")
#             # Remove any solo runs by any member of this team
#             for member in team.members:
#                 await self._sub_repo.remove_user_submissions(task.id, member.discord_id)
#
#         # 5) Select the file parsing strategy
#         from application.parsers.rkg_parser   import RkgParser
#         from application.parsers.rksys_parser import RksysParser
#
#         if not task.multiple_tracks:
#             # multiple_tracks = False → only .rkg allowed
#             self._parser.set_strategy(RkgParser())
#         else:
#             # multiple_tracks = True → only .rksys allowed
#             self._parser.set_strategy(RksysParser())
#
#         # 6) Parse the submission file to get metadata (run_time, etc.)
#         submission_file = self._parser.parse(file_bytes, now)
#
#         # 7) Construct the Submission domain entity
#         sub = Submission(
#             submitted_by=user,
#             task=task,
#             file=submission_file,
#             team=team,
#             url=file_url,
#         )
#
#         # 8) Store time, character, and vehicle fields from parser output
#         if hasattr(submission_file, "run_time") and submission_file.run_time is not None:
#             sub.time = submission_file.run_time
#         else:
#             sub.time = 0.0
#
#         sub.character = getattr(submission_file, "character", None)
#         sub.vehicle   = getattr(submission_file, "vehicle", None)
#
#         # 9) Validate business rules and persist
#         sub.validate()
#         await self._sub_repo.add(sub)
#         return sub
#
#
#
#     async def remove_submission(self, user_id: int) -> Submission:
#         """
#         Delete the existing submission (solo or team) for the user,
#         and return the deleted Submission entity.
#
#         Args:
#             user_id (int): Discord ID of the competitor.
#
#         Returns:
#             Submission: the entity that was deleted.
#
#         Raises:
#             RuntimeError: if no competition or no submission found.
#         """
#         # 1) Load active or last competition
#         task = await self._task_repo.get_active()
#         if not task:
#             task = await self._task_repo.get_last_task()
#         if not task:
#             raise RuntimeError("No competition available for editing.")
#
#         # 2) Determine if the user is part of a team
#         team = None
#         if task.team_size > 1 and not task.speed_task and self._team_repo:
#             team = await self._team_repo.get_by_member(user_id)
#
#         # 3) Load the existing submission
#         if team:
#             sub = await self._sub_repo.get_submission_by_team(task.id, team.id)
#         else:
#             sub = await self._sub_repo.get_submission_by_user(task.id, user_id)
#
#         if not sub:
#             raise RuntimeError("No submission found for this competitor.")
#
#         # 4) Delete via the appropriate repository method
#         if team:
#             await self._sub_repo.remove_team_submissions(task.id, team.id)
#         else:
#             await self._sub_repo.remove_user_submissions(task.id, user_id)
#
#         # 5) Return the deleted entity for command feedback
#         return sub
#
#     async def get_submissions(self) -> list[Submission]:
#         """
#         List all submissions for the active competition,
#         or if none active, the last one.
#
#         Returns:
#             List[Submission]: list of Submission entities.
#         """
#         task = await self._task_repo.get_active()
#         if not task:
#             task = await self._task_repo.get_last_task()
#         if not task:
#             return []
#
#         return await self._sub_repo.get_submissions(task.id)
#
#     async def edit_submission(
#         self,
#         user_id:    int,
#         new_time:   float,
#         dq:         bool,
#         dq_reason:  Optional[str] = None,
#     ) -> Submission:
#         """
#         Modify the time and disqualification status of a submission
#         for the active competition (or the last one if none active).
#
#         Args:
#             user_id (int): Discord ID of the competitor.
#             new_time (float): updated run time.
#             dq (bool): whether to disqualify the submission.
#             dq_reason (Optional[str]): reason for disqualification.
#
#         Returns:
#             Submission: the updated submission entity.
#
#         Raises:
#             RuntimeError: if no competition or submission found.
#         """
#         # 1) Load active or last competition
#         task = await self._task_repo.get_active()
#         if not task:
#             task = await self._task_repo.get_last_task()
#         if not task:
#             raise RuntimeError("No competition available for editing.")
#
#         # 2) Determine if user is in a team
#         team = None
#         if task.team_size > 1 and not task.speed_task and self._team_repo:
#             team = await self._team_repo.get_by_member(user_id)
#
#         # 3) Load the existing submission
#         if team:
#             sub = await self._sub_repo.get_submission_by_team(task.id, team.id)
#         else:
#             sub = await self._sub_repo.get_submission_by_user(task.id, user_id)
#
#         if not sub:
#             raise RuntimeError("No submission found for this competitor.")
#
#         # 4) Apply updates
#         sub.time = new_time
#         sub.dq = dq
#         sub.dq_reason = dq_reason if dq else None
#
#         # 5) Persist changes
#         await self._sub_repo.save(sub)
#         return sub
