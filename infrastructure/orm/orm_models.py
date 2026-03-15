"""
SQLAlchemy ORM Models
=====================

Module path:
    src/infrastructure/orm/orm_models.py

Summary:
    Declarative SQLAlchemy models for every persisted domain entity and
    configuration object used by the bot.

Responsibilities:
    - Provide a table mapping (ORM) for:
        * Core entities: Task, SpeedTaskSession, Submission, User, Team
        * Configuration: LogChannel, HostRole, SubmitterRole, SeekingChannel,
          TasksChannel, AnnouncementsChannel, SpeedTaskLength, SpeedTaskDesc,
          SpeedTaskReminders, ReminderPings, GuildConfig, SubmissionChannel
    - Offer `from_domain()` helpers to convert a domain object → ORM instance.
    - Offer `to_domain()` helpers to convert an ORM instance → domain object.
"""

from typing import Optional

from sqlalchemy import Column, Integer, String, Float, Boolean
from infrastructure.db import Base
from domain.entities import Task, User, Submission, Team, SpeedTaskSession, SubmissionFile
from domain.config import (
    LogChannel, HostRole, SubmitterRole,
    SeekingChannel, TasksChannel, AnnouncementsChannel,
    SpeedTaskLength, SpeedTaskDesc,
    SpeedTaskReminders, ReminderPings, GuildConfig, SubmissionChannel, SubmissionFileConfig, ExtraSettingConfig,
)

# ────────────────────────────────────────────────────────────
# TaskORM
# ────────────────────────────────────────────────────────────
class TaskORM(Base):
    """SQLAlchemy representation of a competition task."""

    __tablename__ = "tasks"

    id              = Column("id",             Integer, primary_key=True)
    number          = Column("task",           Integer, nullable=False)
    year            = Column("year",           Integer, nullable=False)
    is_active       = Column("is_active",      Boolean, default=False)
    team_size       = Column("team_size",      Integer, nullable=False)
    speed_task      = Column("speed_task",     Boolean, default=False)
    deadline        = Column("deadline",       Integer, nullable=False)  # UNIX
    is_released     = Column("is_released",    Boolean, default=False)

    # ---------- mapping helpers ----------
    @classmethod
    def from_domain(cls, task: Task) -> "TaskORM":
        """Create an ORM row from a Task domain object."""
        return cls(
            id=task.id,
            number=task.number,
            year=task.year,
            is_active=task.is_active,
            team_size=task.team_size,
            speed_task=task.speed_task,
            deadline=task.deadline,
            is_released=task.is_released,
        )

    def to_domain(self) -> Task:
        """Convert this ORM row back to a Task domain object."""
        t = Task(
            number=self.number,
            year=self.year,
            team_size=self.team_size,
            speed_task=self.speed_task,
            deadline_epoch=self.deadline,
            is_active=self.is_active,
            is_released=self.is_released,
        )
        t.id = self.id
        return t


# ────────────────────────────────────────────────────────────
# SpeedTaskSessionORM
# ────────────────────────────────────────────────────────────
class SpeedTaskSessionORM(Base):
    """Stores one personal speed-task session per user."""
    __tablename__ = "speedtask"

    user_id  = Column("user_id",  Integer, primary_key=True)
    end_time = Column("end_time", Integer, nullable=False)
    active   = Column("active",   Boolean, default=True)

    @classmethod
    def from_domain(cls, s: SpeedTaskSession) -> "SpeedTaskSessionORM":
        """Create ORM row from SpeedTaskSession domain object."""
        return cls(
            user_id   = s.user.discord_id,
            end_time  = s.personal_deadline,
            active    = s.active,
        )

    def to_domain(self, user: User, task: Task) -> SpeedTaskSession:
        """
        Rebuild a SpeedTaskSession from this ORM row.

        Args:
            user (User): hydrated User entity.
            task (Task): hydrated Task entity.

        Returns:
            SpeedTaskSession: the reconstructed domain object.
        """
        return SpeedTaskSession(
            user              = user,
            task              = task,
            personal_deadline = self.end_time,
            active            = self.active,
        )


# ────────────────────────────────────────────────────────────
# SubmissionORM
# ────────────────────────────────────────────────────────────
class SubmissionORM(Base):
    """SQLAlchemy row for a solo or team submission."""
    __tablename__ = "submissions"

    # ─── Column declarations ───
    id:          int            = Column("index",       Integer, primary_key=True, autoincrement=True)
    user_id:     int            = Column("user_id",     Integer, nullable=False)
    task_id:     int            = Column("task",        Integer, nullable=False)
    team_id:     Optional[int]  = Column("team_id",     Integer, nullable=True)
    url:         str            = Column("url",         String,  nullable=False)
    time:        float          = Column("time",        Float,   default=0.0)
    uploaded_at: int            = Column("uploaded_at", Integer, nullable=False, default=0)
    dq:          bool           = Column("dq",          Boolean, default=False)
    dq_reason:   Optional[str]  = Column("dq_reason",   String,  nullable=True)
    character:   Optional[str]  = Column("character",   String,  nullable=True)
    vehicle:     Optional[str]  = Column("vehicle",     String,  nullable=True)

    # ---------- mapping helpers ----------
    @classmethod
    def from_domain(cls, sub: Submission) -> "SubmissionORM":
        """Create ORM row from Submission domain object."""
        return cls(
            id          = sub.id,
            user_id     = sub.submitted_by.discord_id,
            task_id     = sub.task.id,
            team_id     = sub.team.id if sub.team else None,
            url         = sub.url,
            time        = sub.time,
            uploaded_at = sub.file.uploaded_at,
            dq          = sub.dq,
            dq_reason   = sub.dq_reason,
            character   = sub.character,
            vehicle     = sub.vehicle,
        )

    def to_domain(
        self,
        user: User,
        task: Task,
        file: SubmissionFile,
        team: Team | None = None,
    ) -> Submission:
        """
        Convert ORM row back to a Submission domain object.

        Args:
            user (User): User who submitted.
            task (Task): Task reference.
            file (SubmissionFile): the stored file metadata.
            team (Team | None): associated team, if any.

        Returns:
            Submission: the domain entity.
        """
        sub = Submission(
            submitted_by=user,
            task=task,
            file=file,
            team=team,
            url=self.url,
        )
        sub.id        = self.id
        sub.time      = self.time
        sub.dq        = self.dq
        sub.dq_reason = self.dq_reason
        sub.character = self.character
        sub.vehicle   = self.vehicle
        return sub


# ────────────────────────────────────────────────────────────
# UserORM
# ────────────────────────────────────────────────────────────
class UserORM(Base):
    """Information about a Discord user."""
    __tablename__ = "userbase"

    index        = Column(Integer, primary_key=True, autoincrement=True)
    user_id      = Column("user_id",  Integer, nullable=False)   # Discord ID
    user         = Column("user",     String)                    # Discord handle
    display_name = Column("display_name", String)

    @classmethod
    def from_domain(cls, u: User) -> "UserORM":
        """Create ORM row from User domain object."""
        return cls(
            index        = u.id,
            user_id      = u.discord_id,
            user         = u.handle,
            display_name = u.display_name,
        )

    def to_domain(self) -> User:
        """Convert ORM row back to a User domain object."""
        return User(
            id           = self.index,
            discord_id   = self.user_id,
            handle       = self.user,
            display_name = self.display_name,
        )


# ────────────────────────────────────────────────────────────
# TeamORM
# ────────────────────────────────────────────────────────────
class TeamORM(Base):
    """Stores a team of up to 4 Discord users."""
    __tablename__ = "teams"

    id        = Column("index",     Integer, primary_key=True, autoincrement=True)
    team_name = Column("team_name", String, nullable=True)
    leader_id = Column("leader",    Integer, nullable=False)
    user2_id  = Column("user2",     Integer, nullable=True)
    user3_id  = Column("user3",     Integer, nullable=True)
    user4_id  = Column("user4",     Integer, nullable=True)

    # ---------- mapping helpers ----------
    @classmethod
    def from_domain(cls, team: Team) -> "TeamORM":
        """Create ORM row from Team domain object."""
        return cls(
            id        = team.id,
            team_name = team.name,
            leader_id = team.leader.discord_id,
            user2_id  = team.members[1].discord_id if len(team.members) > 1 else None,
            user3_id  = team.members[2].discord_id if len(team.members) > 2 else None,
            user4_id  = team.members[3].discord_id if len(team.members) > 3 else None,
        )

    def to_domain(self) -> Team:
        """
        Convert ORM row back to a Team domain object.

        Note: only IDs are reconstructed; handles / names can be enriched later.
        """
        from domain.entities import User  # local import to avoid circularity

        leader = User(id=None, discord_id=self.leader_id,
                      handle=str(self.leader_id), display_name="")
        members = [leader]
        for attr in ("user2_id", "user3_id", "user4_id"):
            uid = getattr(self, attr)
            if uid is not None:
                members.append(
                    User(id=None, discord_id=uid,
                         handle=str(uid), display_name="")
                )

        team = Team(name=self.team_name, leader=leader, members=members)
        team.id = self.id
        return team


# ────────────────────────────────────────────────────────────
# Config ORMs (one-row-per-comp)
# ────────────────────────────────────────────────────────────
class LogChannelORM(Base):
    """Channel where the bot logs DM messages and internal errors."""
    __tablename__ = "log_channel"

    index      = Column("index",      Integer, primary_key=True, autoincrement=True)
    comp       = Column("comp",       String,  nullable=False, unique=True)
    channel_id = Column("channel_id", Integer, nullable=False)
    guild_id   = Column("guild_id",   Integer, nullable=False)

    @classmethod
    def from_domain(cls, cfg: LogChannel) -> "LogChannelORM":
        return cls(comp=cfg.comp, channel_id=cfg.channel_id, guild_id=cfg.guild_id)

    def to_domain(self) -> LogChannel:
        return LogChannel(comp=self.comp, channel_id=self.channel_id, guild_id=self.guild_id)


class HostRoleORM(Base):
    """Role allowed to host and manage a competition."""
    __tablename__ = "host_role"

    index    = Column("index",    Integer, primary_key=True, autoincrement=True)
    comp     = Column("comp",     String,  nullable=False, unique=True)
    role_id  = Column("role_id",  Integer, nullable=False)
    name     = Column("name",     String,  nullable=False)
    guild_id = Column("guild_id", Integer, nullable=False)

    @classmethod
    def from_domain(cls, cfg: HostRole) -> "HostRoleORM":
        return cls(comp=cfg.comp, role_id=cfg.role_id, name=cfg.name, guild_id=cfg.guild_id)

    def to_domain(self) -> HostRole:
        return HostRole(comp=self.comp, role_id=self.role_id, name=self.name, guild_id=self.guild_id)


class SubmitterRoleORM(Base):
    """Role automatically granted after a participant submits."""
    __tablename__ = "submitter_role"

    index    = Column("index",    Integer, primary_key=True, autoincrement=True)
    comp     = Column("comp",     String,  nullable=False, unique=True)
    role_id  = Column("role_id",  Integer, nullable=False)
    name     = Column("name",     String,  nullable=False)
    guild_id = Column("guild_id", Integer, nullable=False)

    @classmethod
    def from_domain(cls, cfg: SubmitterRole) -> "SubmitterRoleORM":
        return cls(comp=cfg.comp, role_id=cfg.role_id, name=cfg.name, guild_id=cfg.guild_id)

    def to_domain(self) -> SubmitterRole:
        return SubmitterRole(comp=self.comp, role_id=self.role_id, name=self.name, guild_id=self.guild_id)


class SubmissionChannelORM(Base):
    """Channel where the submission list is posted."""
    __tablename__ = "submission_channel"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    comp       = Column("comp",       String,  nullable=False, index=True)
    channel_id = Column("channel_id", Integer, nullable=False)
    guild_id   = Column("guild_id",   Integer, nullable=False)

    # ---------- mapping helpers ----------
    @classmethod
    def from_domain(cls, sc: SubmissionChannel) -> "SubmissionChannelORM":
        return cls(comp=sc.comp, channel_id=sc.channel_id, guild_id=sc.guild_id)

    def to_domain(self) -> SubmissionChannel:
        return SubmissionChannel(comp=self.comp, channel_id=self.channel_id, guild_id=self.guild_id)


class SeekingChannelORM(Base):
    """Channel where participants look for teammates."""
    __tablename__ = "seeking_channel"

    index      = Column("index",      Integer, primary_key=True, autoincrement=True)
    comp       = Column("comp",       String,  nullable=False, unique=True)
    channel_id = Column("channel_id", Integer, nullable=False)
    guild_id   = Column("guild_id",   Integer, nullable=False)

    @classmethod
    def from_domain(cls, cfg: SeekingChannel) -> "SeekingChannelORM":
        return cls(comp=cfg.comp, channel_id=cfg.channel_id, guild_id=cfg.guild_id)

    def to_domain(self) -> SeekingChannel:
        return SeekingChannel(comp=self.comp, channel_id=self.channel_id, guild_id=self.guild_id)


class TasksChannelORM(Base):
    """Channel where task descriptions are posted."""
    __tablename__ = "tasks_channel"

    index      = Column("index",      Integer, primary_key=True, autoincrement=True)
    comp       = Column("comp",       String,  nullable=False, unique=True)
    channel_id = Column("channel_id", Integer, nullable=False)
    guild_id   = Column("guild_id",   Integer, nullable=False)

    @classmethod
    def from_domain(cls, cfg: TasksChannel) -> "TasksChannelORM":
        return cls(comp=cfg.comp, channel_id=cfg.channel_id, guild_id=cfg.guild_id)

    def to_domain(self) -> TasksChannel:
        return TasksChannel(comp=self.comp, channel_id=self.channel_id, guild_id=self.guild_id)


class AnnouncementsChannelORM(Base):
    """Channel where global announcements are made."""
    __tablename__ = "announcements_channel"

    index      = Column("index",      Integer, primary_key=True, autoincrement=True)
    comp       = Column("comp",       String,  nullable=False, unique=True)
    channel_id = Column("channel_id", Integer, nullable=False)
    guild_id   = Column("guild_id",   Integer, nullable=False)

    @classmethod
    def from_domain(cls, cfg: AnnouncementsChannel) -> "AnnouncementsChannelORM":
        return cls(comp=cfg.comp, channel_id=cfg.channel_id, guild_id=cfg.guild_id)

    def to_domain(self) -> AnnouncementsChannel:
        return AnnouncementsChannel(comp=self.comp, channel_id=self.channel_id, guild_id=self.guild_id)


class SpeedTaskLengthORM(Base):
    """Configured length (in hours) of a speed-task."""
    __tablename__ = "speedtasklength"

    index    = Column("index", Integer, primary_key=True, autoincrement=True)
    comp     = Column("comp",  String,  nullable=False, unique=True)
    time     = Column("time",  Float,   nullable=False)
    guild_id = Column("guild_id", Integer, nullable=False)

    @classmethod
    def from_domain(cls, cfg: SpeedTaskLength) -> "SpeedTaskLengthORM":
        return cls(comp=cfg.comp, time=cfg.time, guild_id=cfg.guild_id)

    def to_domain(self) -> SpeedTaskLength:
        return SpeedTaskLength(comp=self.comp, time=self.time, guild_id=self.guild_id)


class SpeedTaskDescORM(Base):
    """Description text of a speed-task."""
    __tablename__ = "speedtaskdesc"

    index    = Column("index", Integer, primary_key=True, autoincrement=True)
    comp     = Column("comp",  String,  nullable=False, unique=True)
    desc     = Column("desc",  String,  nullable=False)
    guild_id = Column("guild_id", Integer, nullable=False)

    @classmethod
    def from_domain(cls, cfg: SpeedTaskDesc) -> "SpeedTaskDescORM":
        return cls(comp=cfg.comp, desc=cfg.desc, guild_id=cfg.guild_id)

    def to_domain(self) -> SpeedTaskDesc:
        return SpeedTaskDesc(comp=self.comp, desc=self.desc, guild_id=self.guild_id)


class SpeedTaskRemindersORM(Base):
    """List of reminder times (in minutes). Up to 4"""
    __tablename__ = "speedtaskreminders"

    index      = Column("index",      Integer, primary_key=True, autoincrement=True)
    comp       = Column("comp",       String,  nullable=False, unique=True)
    reminder1  = Column("reminder1",  Integer, nullable=True)
    reminder2  = Column("reminder2",  Integer, nullable=True)
    reminder3  = Column("reminder3",  Integer, nullable=True)
    reminder4  = Column("reminder4",  Integer, nullable=True)
    guild_id   = Column("guild_id",   Integer, nullable=False)

    @classmethod
    def from_domain(cls, cfg: SpeedTaskReminders) -> "SpeedTaskRemindersORM":
        return cls(
            comp      = cfg.comp,
            reminder1 = cfg.reminder1,
            reminder2 = cfg.reminder2,
            reminder3 = cfg.reminder3,
            reminder4 = cfg.reminder4,
            guild_id  = cfg.guild_id,
        )

    def to_domain(self) -> SpeedTaskReminders:
        return SpeedTaskReminders(
            comp      = self.comp,
            reminder1 = self.reminder1,
            reminder2 = self.reminder2,
            reminder3 = self.reminder3,
            reminder4 = self.reminder4,
            guild_id  = self.guild_id,
        )


class ReminderPingsORM(Base):
    """Whether @everyone ping is enabled for reminders."""
    __tablename__ = "reminderpings"

    index    = Column("index", Integer, primary_key=True, autoincrement=True)
    comp     = Column("comp",  String,  nullable=False, unique=True)
    ping     = Column("ping",  Integer, nullable=False)
    guild_id = Column("guild_id", Integer, nullable=False)

    @classmethod
    def from_domain(cls, cfg: ReminderPings) -> "ReminderPingsORM":
        return cls(comp=cfg.comp, ping=cfg.ping, guild_id=cfg.guild_id)

    def to_domain(self) -> ReminderPings:
        return ReminderPings(comp=self.comp, ping=self.ping, guild_id=self.guild_id)


class GuildConfigORM(Base):
    """Mapping from Guild ID to active competition key (`comp`)."""
    __tablename__ = "guild_config"

    guild_id = Column("guild_id", Integer, primary_key=True)
    comp     = Column("comp",     String,  nullable=False)

    @classmethod
    def from_domain(cls, gc: GuildConfig) -> "GuildConfigORM":
        return cls(guild_id=gc.guild_id, comp=gc.comp)

    def to_domain(self) -> GuildConfig:
        return GuildConfig(guild_id=self.guild_id, comp=self.comp)


class SubmissionFileConfigORM(Base):
    __tablename__ = "submission_file_config"

    id       = Column(Integer, primary_key=True, autoincrement=True)
    comp     = Column("comp",     String,  nullable=False, unique=True)
    ext      = Column("ext",      String,  nullable=False)
    guild_id = Column("guild_id", Integer, nullable=False)

    @classmethod
    def from_domain(cls, cfg: SubmissionFileConfig) -> "SubmissionFileConfigORM":
        return cls(comp=cfg.comp, ext=cfg.ext.lower(), guild_id=cfg.guild_id)

    def to_domain(self) -> SubmissionFileConfig:
        return SubmissionFileConfig(comp=self.comp, ext=self.ext, guild_id=self.guild_id)

class ExtraSettingORM(Base):
    __tablename__ = "extra_setting"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    comp        = Column("comp",     String,  nullable=False, unique=True)
    enabled     = Column("enabled",  Boolean,  nullable=False)
    lower_bound = Column("lower_bound", Integer, nullable=False)
    upper_bound = Column("upper_bound", Integer, nullable=False)
    guild_id    = Column("guild_id", Integer, nullable=False)

    @classmethod
    def from_domain(cls, cfg: ExtraSettingConfig) -> "ExtraSettingORM":
        return cls(comp=cfg.comp, enabled=cfg.enabled, lower_bound = cfg.lower_bound, upper_bound = cfg.upper_bound,
                   guild_id=cfg.guild_id)

    def to_domain(self) -> ExtraSettingConfig:
        return ExtraSettingConfig(comp=self.comp, enabled=self.enabled, lower_bound=self.lower_bound,
                                  upper_bound=self.upper_bound, guild_id=self.guild_id)


