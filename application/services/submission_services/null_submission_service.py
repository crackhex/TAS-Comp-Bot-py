# src/application/services/submission_services/null_submission_service.py
from __future__ import annotations
from typing import Optional

from application.parsers.file_parser import FileParser
from application.services.submission_services.base_submission_service import (
    BaseSubmissionService,
)

from domain.entities import SubmissionFile, Submission


class NullSubmissionService(BaseSubmissionService):
    """Placeholder service used when the guild has no competition yet."""
    def __init__(
        self,
        user_svc,
        submission_repo,
        task_repo,
        user_repo,
        *,
        file_parser: Optional[FileParser] = None,
        team_repo=None,
        speed_repo=None,
    ) -> None:
        super().__init__(
            user_svc,
            submission_repo,
            task_repo,
            user_repo,
            file_parser=file_parser,
            team_repo=team_repo,
            speed_repo=speed_repo,
        )

    async def submit(self, *args, **kwargs):
        raise RuntimeError(
            "Submissions are disabled until a competition and file type are configured "
            "(use `/set-comp` and `/set-file`)."
        )

    # Base-class hooks
    def parse_file(self, *args, **kwargs) -> SubmissionFile:
        raise RuntimeError(
            "No competition configured for this guild. "
            "Please ask an admin to run `/set-comp`"
        )

    def populate_metadata(self, sub: Submission, file: SubmissionFile) -> None:
        ...
