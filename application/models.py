"""
Pydantic Models for Application & Command Layer
=====================================

Module path:
    src/application/models.py

Summary:
    Defines DTOs (Data Transfer Object) and validation rules for application commands and services.

Responsibilities:
    - TaskConfig: parameters for the `/start-task` command, with automatic
      filling of the `year` field when omitted.
"""

from datetime import datetime, timezone
from pydantic import BaseModel, field_validator
from typing import Optional


class TaskConfig(BaseModel):
    """
    Model for the `/start-task` command.

    Args:
        number (int): the competition number.
        year (Optional[int]): the competition year; if not provided,
            automatically set to the current UTC year.
        team_size (int): maximum number of members per team.
        speed_task (bool): whether this is a speed-task.
        deadline (int): UNIX epoch timestamp of the deadline.
    """

    number: int
    year: Optional[int] = None
    team_size: int
    speed_task: bool
    deadline: int

    @field_validator("year", mode="before")
    def default_year(cls, v):
        """
        Auto-complete the `year` field when it's missing or None (usually when doing /start-task).
        """
        return v or datetime.now(timezone.utc).year
