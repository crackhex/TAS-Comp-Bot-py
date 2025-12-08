"""
MKW Wii Submission Service
==========================

Module path:
    src/application/services/mkw_submission_service.py

Summary
-------
Domain-specific implementation of ``AbstractSubmissionService`` for the
**Mario Kart Wii TAS Competition**.
It understands two file formats:

<<<<<<< Updated upstream
* ``.rkg``  – single-track ghost file (Time Trials).
* ``.rksys`` – multi-track system save dump (Grand Prix / TT batch).
=======
Game-specific implementation of the base submission service for the
Mario Kart Wii TAS Competition.
It understands the following file formats:

* .rkg  – single-track ghost file (Time Trials).
* .dat – game file, used for ghosts across multiple tracks.
* .zip - sending multiple files, of different type.
>>>>>>> Stashed changes

The service chooses the proper parser **at run-time**, based on the single
“accepted file extension” stored in the guild/competition configuration.

If a user submits multiple times, previous runs are automatically replaced
according to the base‐class algorithm.
"""

from __future__ import annotations

from typing import Optional

<<<<<<< Updated upstream
from application.parsers.rkg_parser_strategy   import RkgParserStrategy
from application.parsers.rksys_parser_strategy import RksysParserStrategy
=======
from application.parsers.registry import candidates_excluding
>>>>>>> Stashed changes
from application.parsers.file_parser  import FileParser
from application.parsers.null_parser_strategy  import NullParserStrategy   # safety

from application.services.submission_services.base_submission_service import BaseSubmissionService

from application.services.user_service import UserService
from domain.repositories import (
    SubmissionRepository,
    TaskRepository,
    UserRepository,
    TeamRepository,
    SpeedTaskRepository,
)
from domain.entities import SubmissionFile, Submission


class MKWSubmissionService(BaseSubmissionService):
    """
    Concrete submission service for Mario Kart Wii competitions.

    It only needs to implement two abstract steps:

    * parse_file: translate raw bytes into a SubmissionFile.
    * populate_metadata: copy game-specific fields (run_time, character…).
    """

    # ─────────────────────────── constructor ──────────────────────────────
    def __init__(
        self,
        user_svc: UserService,
        submission_repo: SubmissionRepository,
        task_repo: TaskRepository,
        user_repo: UserRepository,
        file_parser: FileParser,
        team_repo: Optional[TeamRepository] = None,
        speed_repo: Optional[SpeedTaskRepository] = None,
    ) -> None:
        super().__init__(
            user_svc,
            submission_repo,
            task_repo,
            user_repo,
            file_parser,
            team_repo=team_repo,
            speed_repo=speed_repo
        )

    # ────────────────────────── required hooks ────────────────────────────
    # Pick the correct parser & return the parsed value object
    def parse_file(
        self,
        file_bytes: bytes,
        uploaded_at_epoch: int,
    ) -> SubmissionFile:
        """
        Figure out which MKW parser supports the bytes and return the
        corresponding SubmissionFile instance.

        Raises
        ------
        ValueError
            If the bytes do not match either .rkg nor .rksys.
        """
        # ``FileParser`` should already have the right strategy
        # (because /set-file set it), but we double-check.
        strat = self._parser.strategy
        if isinstance(strat, NullParserStrategy):
            raise RuntimeError(
                "No parser strategy configured. Use `/set-file` first."
            )

        # Check if the file supported by the current parser
        if strat.supports(file_bytes):
            return strat.parse(file_bytes, uploaded_at_epoch)

        # Otherwise, fall back to the other parser
        alt_strat = RkgParserStrategy() if isinstance(strat, RksysParserStrategy) else RksysParserStrategy()
        if alt_strat.supports(file_bytes):
            # Swap strategy for the rest of the runtime
            self._parser.set_strategy(alt_strat)
            return alt_strat.parse(file_bytes, uploaded_at_epoch)

        raise ValueError("Unsupported MKW submission file format")

    # Copy metadata from the parsed file to the Submission entity
    def populate_metadata(
        self,
        submission: Submission,
        file_obj: SubmissionFile,
    ) -> None:
        """
        Extract MKW-specific metadata and copy it onto ``submission``.

        * run_time → submission.time
        * character / vehicle if available (only on RKG), else None
        """
        # If rkg, retrieve run_time, else set to 0 if rksys (or time isn't found)
        if hasattr(file_obj, "run_time"):
            submission.time = file_obj.run_time or 0.0
        else:
            submission.time = 0.0

        submission.character = getattr(file_obj, "character", None)
        submission.vehicle   = getattr(file_obj, "vehicle",   None)
