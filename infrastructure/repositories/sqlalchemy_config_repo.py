"""
SQLAlchemy Config Repository
============================

Module path:
    src/infrastructure/repositories/sqlalchemy_config_repo.py

Summary:
    Implements the ConfigRepository interface using async SQLAlchemy.

Responsibilities:
    - Provide get/save methods for all configuration types:
        * LogChannel
        * HostRole
        * SubmitterRole
        * SeekingChannel
        * TasksChannel
        * AnnouncementsChannel
        * SpeedTaskLength
        * SpeedTaskDesc
        * SpeedTaskReminders
        * ReminderPings
        * GuildConfig
        * SubmissionChannel
"""

from typing import Optional, List
from sqlalchemy import select, delete
from infrastructure.db import SessionLocal
from domain.repositories import ConfigRepository
from domain.config import (
    LogChannel, HostRole, SubmitterRole,
    SeekingChannel, TasksChannel, AnnouncementsChannel,
    SpeedTaskLength, SpeedTaskDesc,
    SpeedTaskReminders, ReminderPings, GuildConfig, SubmissionChannel, SubmissionFileConfig,
)
from infrastructure.orm.orm_models import (
    LogChannelORM, HostRoleORM, SubmitterRoleORM,
    SeekingChannelORM, TasksChannelORM, AnnouncementsChannelORM,
    SpeedTaskLengthORM, SpeedTaskDescORM,
    SpeedTaskRemindersORM, ReminderPingsORM, GuildConfigORM, SubmissionChannelORM, SubmissionFileConfigORM,
)


class SqlAlchemyConfigRepository(ConfigRepository):
    def __init__(self, session_factory=SessionLocal):
        self._sf = session_factory

    # ── LogChannel ──
    async def get_log_channel(self, comp: str) -> Optional[LogChannel]:
        async with self._sf() as sess:
            row = (await sess.scalars(
                select(LogChannelORM).where(LogChannelORM.comp == comp)
            )).first()
            return row.to_domain() if row else None

    async def save_log_channel(self, cfg: LogChannel) -> None:
        async with self._sf() as sess:
            row = (await sess.scalars(
                select(LogChannelORM).where(LogChannelORM.comp == cfg.comp)
            )).first()
            if row:
                row.channel_id = cfg.channel_id
                row.guild_id = cfg.guild_id
            else:
                sess.add(LogChannelORM.from_domain(cfg))
            await sess.commit()

    # ── HostRole ──
    async def get_host_role(self, comp: str) -> Optional[HostRole]:
        async with self._sf() as sess:
            row = (await sess.scalars(
                select(HostRoleORM).where(HostRoleORM.comp == comp)
            )).first()
            return row.to_domain() if row else None

    async def save_host_role(self, cfg: HostRole) -> None:
        async with self._sf() as sess:
            row = (await sess.scalars(
                select(HostRoleORM).where(HostRoleORM.comp == cfg.comp)
            )).first()
            if row:
                row.role_id = cfg.role_id
                row.name = cfg.name
                row.guild_id = cfg.guild_id
            else:
                sess.add(HostRoleORM.from_domain(cfg))
            await sess.commit()

    # ── SubmitterRole ──
    async def get_submitter_role(self, comp: str) -> Optional[SubmitterRole]:
        async with self._sf() as sess:
            row = (await sess.scalars(
                select(SubmitterRoleORM).where(SubmitterRoleORM.comp == comp)
            )).first()
            return row.to_domain() if row else None

    async def save_submitter_role(self, cfg: SubmitterRole) -> None:
        async with self._sf() as sess:
            row = (await sess.scalars(
                select(SubmitterRoleORM).where(SubmitterRoleORM.comp == cfg.comp)
            )).first()
            if row:
                row.role_id = cfg.role_id
                row.name = cfg.name
                row.guild_id = cfg.guild_id
            else:
                sess.add(SubmitterRoleORM.from_domain(cfg))
            await sess.commit()

    # ── SubmissionChannel ──
    async def get_submission_channel(self, comp: str) -> Optional[SubmissionChannel]:
        async with self._sf() as sess:
            row = (await sess.scalars(
                select(SubmissionChannelORM).where(SubmissionChannelORM.comp == comp)
            )).first()
            return row.to_domain() if row else None

    async def save_submission_channel(self, cfg: SubmissionChannel) -> None:
        async with self._sf() as sess:
            row = (await sess.scalars(
                select(SubmissionChannelORM).where(SubmissionChannelORM.comp == cfg.comp)
            )).first()
            if row:
                row.channel_id = cfg.channel_id
                row.guild_id = cfg.guild_id
            else:
                sess.add(SubmissionChannelORM.from_domain(cfg))
            await sess.commit()

    # ── SeekingChannel ──
    async def get_seeking_channel(self, comp: str) -> Optional[SeekingChannel]:
        async with self._sf() as sess:
            row = (await sess.scalars(
                select(SeekingChannelORM).where(SeekingChannelORM.comp == comp)
            )).first()
            return row.to_domain() if row else None

    async def save_seeking_channel(self, cfg: SeekingChannel) -> None:
        async with self._sf() as sess:
            row = (await sess.scalars(
                select(SeekingChannelORM).where(SeekingChannelORM.comp == cfg.comp)
            )).first()
            if row:
                row.channel_id = cfg.channel_id
                row.guild_id = cfg.guild_id
            else:
                sess.add(SeekingChannelORM.from_domain(cfg))
            await sess.commit()

    # ── TasksChannel ──
    async def get_tasks_channel(self, comp: str) -> Optional[TasksChannel]:
        async with self._sf() as sess:
            row = (await sess.scalars(
                select(TasksChannelORM).where(TasksChannelORM.comp == comp)
            )).first()
            return row.to_domain() if row else None

    async def save_tasks_channel(self, cfg: TasksChannel) -> None:
        async with self._sf() as sess:
            row = (await sess.scalars(
                select(TasksChannelORM).where(TasksChannelORM.comp == cfg.comp)
            )).first()
            if row:
                row.channel_id = cfg.channel_id
                row.guild_id = cfg.guild_id
            else:
                sess.add(TasksChannelORM.from_domain(cfg))
            await sess.commit()

    # ── AnnouncementsChannel ──
    async def get_announcements_channel(self, comp: str) -> Optional[AnnouncementsChannel]:
        async with self._sf() as sess:
            row = (await sess.scalars(
                select(AnnouncementsChannelORM).where(AnnouncementsChannelORM.comp == comp)
            )).first()
            return row.to_domain() if row else None

    async def save_announcements_channel(self, cfg: AnnouncementsChannel) -> None:
        async with self._sf() as sess:
            row = (await sess.scalars(
                select(AnnouncementsChannelORM).where(AnnouncementsChannelORM.comp == cfg.comp)
            )).first()
            if row:
                row.channel_id = cfg.channel_id
                row.guild_id = cfg.guild_id
            else:
                sess.add(AnnouncementsChannelORM.from_domain(cfg))
            await sess.commit()

    # ── SpeedTaskLength ──
    async def get_speed_task_length(self, comp: str) -> Optional[SpeedTaskLength]:
        async with self._sf() as sess:
            row = (await sess.scalars(
                select(SpeedTaskLengthORM).where(SpeedTaskLengthORM.comp == comp)
            )).first()
            return row.to_domain() if row else None

    async def save_speed_task_length(self, cfg: SpeedTaskLength) -> None:
        async with self._sf() as sess:
            row = (await sess.scalars(
                select(SpeedTaskLengthORM).where(SpeedTaskLengthORM.comp == cfg.comp)
            )).first()
            if row:
                row.time = cfg.time
                row.guild_id = cfg.guild_id
            else:
                sess.add(SpeedTaskLengthORM.from_domain(cfg))
            await sess.commit()

    # ── SpeedTaskDesc ──
    async def get_speed_task_desc(self, comp: str) -> Optional[SpeedTaskDesc]:
        async with self._sf() as sess:
            row = (await sess.scalars(
                select(SpeedTaskDescORM).where(SpeedTaskDescORM.comp == comp)
            )).first()
            return row.to_domain() if row else None

    async def save_speed_task_desc(self, cfg: SpeedTaskDesc) -> None:
        async with self._sf() as sess:
            row = (await sess.scalars(
                select(SpeedTaskDescORM).where(SpeedTaskDescORM.comp == cfg.comp)
            )).first()
            if row:
                row.desc = cfg.desc
                row.guild_id = cfg.guild_id
            else:
                sess.add(SpeedTaskDescORM.from_domain(cfg))
            await sess.commit()

    async def clear(self) -> None:
        async with self._sf() as db:
            await db.execute(delete(SpeedTaskDescORM))
            await db.commit()

    # ── SpeedTaskReminders ──
    async def get_speed_task_reminders(self, comp: str) -> Optional[SpeedTaskReminders]:
        async with self._sf() as sess:
            row = (await sess.scalars(
                select(SpeedTaskRemindersORM).where(SpeedTaskRemindersORM.comp == comp)
            )).first()
            return row.to_domain() if row else None

    async def save_speed_task_reminders(self, cfg: SpeedTaskReminders) -> None:
        async with self._sf() as sess:
            row = (await sess.scalars(
                select(SpeedTaskRemindersORM).where(SpeedTaskRemindersORM.comp == cfg.comp)
            )).first()
            if row:
                row.reminder1 = cfg.reminder1
                row.reminder2 = cfg.reminder2
                row.reminder3 = cfg.reminder3
                row.reminder4 = cfg.reminder4
                row.guild_id = cfg.guild_id
            else:
                sess.add(SpeedTaskRemindersORM.from_domain(cfg))
            await sess.commit()

    # ── ReminderPings ──
    async def get_reminder_pings(self, comp: str) -> Optional[ReminderPings]:
        async with self._sf() as sess:
            row = (await sess.scalars(
                select(ReminderPingsORM).where(ReminderPingsORM.comp == comp)
            )).first()
            return row.to_domain() if row else None

    async def save_reminder_pings(self, cfg: ReminderPings) -> None:
        async with self._sf() as sess:
            row = (await sess.scalars(
                select(ReminderPingsORM).where(ReminderPingsORM.comp == cfg.comp)
            )).first()
            if row:
                row.ping = cfg.ping
                row.guild_id = cfg.guild_id
            else:
                sess.add(ReminderPingsORM.from_domain(cfg))
            await sess.commit()

    async def get_guild_config(self, guild_id: int) -> Optional[GuildConfig]:
        async with self._sf() as sess:
            row = (await sess.scalars(
                select(GuildConfigORM).where(GuildConfigORM.guild_id == guild_id)
            )).first()
            return row.to_domain() if row else None

    async def list_guild_configs(self) -> List[GuildConfig]:
        async with self._sf() as sess:
            result = await sess.scalars(
                select(GuildConfigORM)
            )
            rows: List[GuildConfigORM] = result.all()
            return [row.to_domain() for row in rows]

    async def save_guild_config(self, cfg: GuildConfig) -> None:
        async with self._sf() as sess:
            row = (await sess.scalars(
                select(GuildConfigORM).where(GuildConfigORM.guild_id == cfg.guild_id)
            )).first()
            if row:
                row.comp = cfg.comp
            else:
                sess.add(GuildConfigORM.from_domain(cfg))
            await sess.commit()


    async def get_submission_file_extension(self, comp: str) -> Optional[SubmissionFileConfig]:
        async with self._sf() as sess:
            row = (await sess.scalars(
                select(SubmissionFileConfigORM).where(SubmissionFileConfigORM.comp == comp)
            )).first()
            return row.to_domain() if row else None

    async def save_submission_file_extension(self, cfg: SubmissionFileConfig) -> None:
        async with self._sf() as sess:
            row = (await sess.scalars(
                select(SubmissionFileConfigORM).where(SubmissionFileConfigORM.comp == cfg.comp)
            )).first()
            if row:
                row.ext = cfg.ext.lower()
                row.guild_id = cfg.guild_id
            else:
                sess.add(SubmissionFileConfigORM.from_domain(cfg))
            await sess.commit()
