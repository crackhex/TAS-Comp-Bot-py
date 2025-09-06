"""
Submission-Service Factory
==========================

Module path:
    src/application/services/submission_services/service_factory.py

Summary:
    Central place that maps a competition key ("mkw", "sm64", ...) to the
    concreteSubmissionService class able to parse, validate and persist runs for
    that game.

    Adding support for a new game requires:

    1. Implementing a concrete XXXSubmissionService that derives fromBaseSubmissionService`.
    2. Importing it here and registering a new key in
        SubmissionServiceFactory – the rest of the bot remains unchanged.
    3. Register the file extension in main, and in entities.

"""
from typing import Dict, Type

from application.services.submission_services.base_submission_service import BaseSubmissionService
from application.services.submission_services.mkw_submission_service  import (
    MKWSubmissionService,
)
from application.services.submission_services.null_submission_service import (
    NullSubmissionService,
)

SubmissionServiceFactory: Dict[str, Type[BaseSubmissionService]] = {
    "mkw": MKWSubmissionService,          # Mario Kart Wii
    # "nsmbw": NSMBWSubmissionService,
    # "sm64":  SM64SubmissionService,
}

def build_submission_service(
    comp: str | None,
    *,
    user_svc,
    submission_repo,
    task_repo,
    user_repo,
    team_repo=None,
    speed_repo=None,
    file_parser=None,
):
    cls = SubmissionServiceFactory.get(comp, NullSubmissionService)
    return cls(
        user_svc=user_svc,
        submission_repo=submission_repo,
        task_repo=task_repo,
        user_repo=user_repo,
        file_parser=file_parser,
        team_repo=team_repo,
        speed_repo=speed_repo,
    )
