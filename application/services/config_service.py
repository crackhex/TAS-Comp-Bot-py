"""
Configuration Service
=====================

Module path:
    src/application/services/config_service.py

Summary:
    Provides high-level application operations for reading and updating
    guild and competition configuration through the underlying repository.

Responsibilities:
    - get_log_channel / set_log_channel
    - get_host_role / set_host_role
    - get_submitter_role / set_submitter_role
    - get_submission_channel / set_submission_channel
    - get_seeking_channel / set_seeking_channel
    - get_tasks_channel / set_tasks_channel
    - get_announcements_channel / set_announcements_channel
    - get_speed_task_length / set_speed_task_length
    - get_speed_task_desc / set_speed_task_desc
    - get_speed_task_reminders / set_speed_task_reminders
    - get_reminder_pings / set_reminder_pings
    - get_guild_config / set_guild_config
    - etc
"""

from typing import Optional
from domain.config import (
    LogChannel, HostRole, SubmitterRole,
    SeekingChannel, TasksChannel, AnnouncementsChannel,
    SpeedTaskLength, SpeedTaskDesc,
    SpeedTaskReminders, ReminderPings, GuildConfig, SubmissionChannel, SubmissionFileConfig, ExtraSettingConfig,
)
from domain.repositories import ConfigRepository


class ConfigService:
    def __init__(self, config_repo: ConfigRepository):
        self._repo = config_repo

    # ── LogChannel ──
    async def get_log_channel(self, comp: str) -> Optional[LogChannel]:
        return await self._repo.get_log_channel(comp)

    async def set_log_channel(self, comp: str, channel_id: int, guild_id: int) -> None:
        cfg = LogChannel(comp=comp, channel_id=channel_id, guild_id=guild_id)
        await self._repo.save_log_channel(cfg)

    # ── HostRole ──
    async def get_host_role(self, comp: str) -> Optional[HostRole]:
        return await self._repo.get_host_role(comp)

    async def set_host_role(self, comp: str, role_id: int, name: str, guild_id: int) -> None:
        cfg = HostRole(comp=comp, role_id=role_id, name=name, guild_id=guild_id)
        await self._repo.save_host_role(cfg)

    # ── SubmitterRole ──
    async def get_submitter_role(self, comp: str) -> Optional[SubmitterRole]:
        return await self._repo.get_submitter_role(comp)

    async def set_submitter_role(self, comp: str, role_id: int, name: str, guild_id: int) -> None:
        cfg = SubmitterRole(comp=comp, role_id=role_id, name=name, guild_id=guild_id)
        await self._repo.save_submitter_role(cfg)

    # ── SubmissionChannel ──
    async def get_submission_channel(self, comp: str) -> Optional[SubmissionChannel]:
        return await self._repo.get_submission_channel(comp)

    async def set_submission_channel(self, comp: str, channel_id: int, guild_id: int) -> None:
        cfg = SubmissionChannel(comp=comp, channel_id=channel_id, guild_id=guild_id)
        await self._repo.save_submission_channel(cfg)

    # ── SeekingChannel ──
    async def get_seeking_channel(self, comp: str) -> Optional[SeekingChannel]:
        return await self._repo.get_seeking_channel(comp)

    async def set_seeking_channel(self, comp: str, channel_id: int, guild_id: int) -> None:
        cfg = SeekingChannel(comp=comp, channel_id=channel_id, guild_id=guild_id)
        await self._repo.save_seeking_channel(cfg)

    # ── TasksChannel ──
    async def get_tasks_channel(self, comp: str) -> Optional[TasksChannel]:
        return await self._repo.get_tasks_channel(comp)

    async def set_tasks_channel(self, comp: str, channel_id: int, guild_id: int) -> None:
        cfg = TasksChannel(comp=comp, channel_id=channel_id, guild_id=guild_id)
        await self._repo.save_tasks_channel(cfg)

    # ── AnnouncementsChannel ──
    async def get_announcements_channel(self, comp: str) -> Optional[AnnouncementsChannel]:
        return await self._repo.get_announcements_channel(comp)

    async def set_announcements_channel(self, comp: str, channel_id: int, guild_id: int) -> None:
        cfg = AnnouncementsChannel(comp=comp, channel_id=channel_id, guild_id=guild_id)
        await self._repo.save_announcements_channel(cfg)

    # ── SpeedTaskLength ──
    async def get_speed_task_length(self, comp: str) -> Optional[SpeedTaskLength]:
        return await self._repo.get_speed_task_length(comp)

    async def set_speed_task_length(self, comp: str, time: float, guild_id: int) -> None:
        cfg = SpeedTaskLength(comp=comp, time=time, guild_id=guild_id)
        await self._repo.save_speed_task_length(cfg)

    # ── SpeedTaskDesc ──
    async def get_speed_task_desc(self, comp: str) -> Optional[SpeedTaskDesc]:
        return await self._repo.get_speed_task_desc(comp)

    async def set_speed_task_desc(self, comp: str, desc: str, guild_id: int) -> None:
        cfg = SpeedTaskDesc(comp=comp, desc=desc, guild_id=guild_id)
        await self._repo.save_speed_task_desc(cfg)

    async def clear_speed_task_desc(self) -> None:
        await self._repo.clear()

    # ── SpeedTaskReminders ──
    async def get_speed_task_reminders(self, comp: str) -> Optional[SpeedTaskReminders]:
        return await self._repo.get_speed_task_reminders(comp)

    async def set_speed_task_reminders(
        self,
        comp: str,
        reminder1: Optional[int],
        reminder2: Optional[int],
        reminder3: Optional[int],
        reminder4: Optional[int],
        guild_id: int,
    ) -> None:
        cfg = SpeedTaskReminders(
            comp=comp,
            reminder1=reminder1,
            reminder2=reminder2,
            reminder3=reminder3,
            reminder4=reminder4,
            guild_id=guild_id,
        )
        await self._repo.save_speed_task_reminders(cfg)

    # ── ReminderPings ──
    async def get_reminder_pings(self, comp: str) -> Optional[ReminderPings]:
        return await self._repo.get_reminder_pings(comp)

    async def set_reminder_pings(self, comp: str, ping: int, guild_id: int) -> None:
        cfg = ReminderPings(comp=comp, ping=ping, guild_id=guild_id)
        await self._repo.save_reminder_pings(cfg)

    # ── GuildConfig ──
    async def get_guild_config(self, guild_id: int) -> Optional[GuildConfig]:
        return await self._repo.get_guild_config(guild_id)

    async def list_guild_configs(self) -> list[GuildConfig]:
        return await self._repo.list_guild_configs()

    async def set_guild_config(self, guild_id: int, comp: str) -> None:
        gc = GuildConfig(guild_id=guild_id, comp=comp)
        await self._repo.save_guild_config(gc)

    # ── FileExtension ──
    async def get_submission_file_extension(self, comp: str) -> Optional[SubmissionFileConfig]:
        return await self._repo.get_submission_file_extension(comp)

    async def set_submission_file_extension(self, comp: str, ext: str, guild_id: int) -> None:
        cfg = SubmissionFileConfig(comp=comp, ext=ext.lower(), guild_id=guild_id)
        await self._repo.save_submission_file_extension(cfg)

    # ── ExtraSetting ──
    async def get_extra_setting(self, comp: str) -> Optional[ExtraSettingConfig]:
        return await self._repo.get_extra_setting(comp)

    async def set_extra_setting(self, comp: str, enabled: bool, lower_bound: int, upper_bound: int, guild_id: int) -> None:
        cfg = ExtraSettingConfig(comp=comp, enabled=enabled, lower_bound=lower_bound, upper_bound=upper_bound,
                                 guild_id=guild_id)
        await self._repo.save_extra_setting(cfg)
