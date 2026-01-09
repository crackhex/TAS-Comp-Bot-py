"""
Configuration Data Classes
==========================

Module path:
    src/domain/config.py

Summary:
    Domain value objects representing guild and competition configuration settings.

Responsibilities:
    - LogChannel: configuration for the logging channel
    - HostRole: configuration for the host role
    - SubmitterRole: configuration for the submitter role
    - SubmissionChannel: configuration for the submissions channel
    - SeekingChannel: configuration for the channel where participants seek teammates
    - TasksChannel: configuration for the channel where tasks are posted
    - AnnouncementsChannel: configuration for the announcements channel
    - SpeedTaskLength: configured duration (in hours) for speed-tasks
    - SpeedTaskDesc: description text for speed-tasks
    - SpeedTaskReminders: reminder schedule (in minutes) for speed-tasks
    - ReminderPings: ping settings for reminders (@everyone or not)
    - GuildConfig: mapping of a guild to its active competition key
    - etc
"""

from dataclasses import dataclass


@dataclass
class LogChannel:
    comp: str
    channel_id: int
    guild_id: int


@dataclass
class HostRole:
    comp: str
    role_id: int
    name: str
    guild_id: int


@dataclass
class SubmitterRole:
    comp: str
    role_id: int
    name: str
    guild_id: int


@dataclass
class SubmissionChannel:
    comp: str
    channel_id: int
    guild_id: int


@dataclass
class SeekingChannel:
    comp: str
    channel_id: int
    guild_id: int


@dataclass
class TasksChannel:
    comp: str
    channel_id: int
    guild_id: int


@dataclass
class AnnouncementsChannel:
    comp: str
    channel_id: int
    guild_id: int


@dataclass
class SpeedTaskLength:
    comp: str
    time: float  # In hours
    guild_id: int


@dataclass
class SpeedTaskDesc:
    comp: str
    desc: str
    guild_id: int


@dataclass
class SpeedTaskReminders:
    comp: str
    reminder1: int
    reminder2: int
    reminder3: int
    reminder4: int
    guild_id: int


@dataclass
class ReminderPings:
    comp: str
    ping: int
    guild_id: int



@dataclass
class GuildConfig:
    guild_id: int
    comp: str

@dataclass
class SubmissionFileConfig:
    comp: str
    ext: str
    guild_id: int

@dataclass
class FunnySettingOneConfig:
    comp: str
    enabled: bool
    guild_id: int


