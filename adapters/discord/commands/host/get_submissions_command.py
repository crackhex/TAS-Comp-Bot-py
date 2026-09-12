"""
Get Submissions Command
=======================

Module path:
    src/adapters/discord/commands/host/get_submissions_command.py

Summary:
    Host-only command that lists submissions for the active task
    or the most recent task if it is past deadline. Discord's 2000
    characters limit is taken into account.

Responsibilities:
    - Resolve the active task (fallback to the last task if it's past deadline).
    - Fetch all submissions for that task via SubmissionService.
    - Split output into multiple messages under Discord size limits.
    - Provide a zip file with all ghosts.
"""

import asyncio
import io
import re
import zipfile
import zlib
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Dict, List, NamedTuple, Optional, Set, Tuple
from urllib.parse import urlparse

import aiohttp
import discord
from discord.ext import commands
from discord.http import Route

from application.services.task_manager       import TaskManager
from application.parsers.rkg_parser_strategy import get_ghost_time
from adapters.discord.checks                 import host_only
from adapters.discord.utils.time_format      import fmt_time, fmt_filename_time

MSG_LIMIT = 2_000
BUFFER    = 50

# How many submission files to download from the CDN at once.
MAX_CONCURRENT_DOWNLOADS = 5
# Per-request timeout when downloading a submission file.
DOWNLOAD_TIMEOUT = aiohttp.ClientTimeout(total=30)
# Fallback attachment size limit when the guild one is unavailable (bytes).
DEFAULT_FILESIZE_LIMIT = 10 * 1024 * 1024
# Headroom kept under the attachment limit for zip overhead (bytes).
ZIP_OVERHEAD_MARGIN = 256 * 1024
# Estimated zip bookkeeping bytes per archive entry (headers, central dir).
ZIP_ENTRY_OVERHEAD = 256
# Longest participant string allowed inside a filename.
MAX_PARTICIPANTS_LEN = 80
# How many failed downloads to name in the closing message.
MAX_REPORTED_FAILURES = 10

# Characters that are unsafe in a filename on Windows/macOS/Linux.
# ``\w`` under the unicode flag keeps accents and CJK, so display names
# survive mostly intact.
_UNSAFE_CHARS = re.compile(r"[^\w\-.& ]", re.UNICODE)
# Reserved device names on Windows; a file called ``CON.rkg`` cannot be
# extracted there.
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


class ArchiveEntry(NamedTuple):
    """One downloaded file, ready to be written into an archive."""
    name: str
    payload: bytes
    uploaded_at: int
    zip_size: int  # estimated deflated size inside the archive, in bytes


def _ghost_time_from(payload: bytes) -> Optional[str]:
    """
    Read the ghost time out of a downloaded payload, when it is an RKG.

    Submissions reloaded from the database carry a plain SubmissionFile, so
    the ghost time is not available there; the raw bytes are the only source.

    Args:
        payload (bytes): raw file content.

    Returns:
        str | None: formatted ghost time, or None for .dat, .zip or malformed
        files.
    """
    if len(payload) < 0x07 or payload[:4] != b"RKGD":
        return None
    try:
        return fmt_filename_time(get_ghost_time(bytearray(payload)))
    except Exception:
        return None


def _safe_name(name: str, fallback: str = "user") -> str:
    """
    Turn an arbitrary Discord display name into a safe filename component.

    Args:
        name (str): Raw display name, possibly containing slashes, emoji, etc.
        fallback (str): Value to use when nothing usable remains.

    Returns:
        str: Sanitized, length-capped name.
    """
    cleaned = _UNSAFE_CHARS.sub("_", name or "")
    # Windows rejects trailing dots and spaces.
    cleaned = cleaned.strip(" .")
    cleaned = cleaned[:60]
    if not cleaned or cleaned.upper() in _WINDOWS_RESERVED:
        return fallback
    return cleaned


def _file_participants(sub) -> str:
    """
    Participant names for use in a filename.

    Unlike ``_who_for``, the team's own name is deliberately left out.
    Each member is sanitized individually.

    Args:
        sub: Submission entity.

    Returns:
        str: e.g. ``DashQC & Police`` for a team, ``DashQC`` for a solo run.
    """
    if sub.team:
        joined = " & ".join(_safe_name(m.display_name) for m in sub.team.members)
    else:
        joined = _safe_name(sub.submitted_by.display_name)

    if len(joined) > MAX_PARTICIPANTS_LEN:
        joined = joined[:MAX_PARTICIPANTS_LEN].rstrip(" .&")
    return joined or "team"


def _unique_name(base: str, ext: str, used: Set[str]) -> str:
    """
    Return ``base.ext``, suffixed with ``(2)``, ``(3)``... on collision.

    Comparison is case-insensitive because NTFS and APFS are: ``Dash.rkg``
    and ``dash.rkg`` would overwrite each other on extraction.

    Args:
        base (str): filename without extension.
        ext (str): extension without a leading dot.
        used (set): names already taken; mutated in place.

    Returns:
        str: a filename not yet present in ``used``.
    """
    name = f"{base}.{ext}"
    n = 2
    while name.lower() in used:
        name = f"{base} ({n}).{ext}"
        n += 1
    used.add(name.lower())
    return name


def _entry_ext(url: str, default_ext: str) -> str:
    """
    Derive a file extension from a CDN URL, ignoring query parameters.

    Discord attachment URLs look like ``.../file.rkg?ex=...&is=...``, so the
    suffix has to be taken from the parsed path rather than the raw string.
    Falls back to the competition's configured extension when the URL has no
    usable suffix.

    Args:
        url (str): Stored submission URL.
        default_ext (str): Extension configured for the competition.

    Returns:
        str: Extension without a leading dot.
    """
    suffix = PurePosixPath(urlparse(url).path).suffix.lstrip(".").lower()
    return suffix or default_ext


def _who_for(sub) -> str:
    """
    Build the participant label used in the listing and in error messages.

    Args:
        sub: Submission entity.

    Returns:
        str: Team name/members joined, or the solo submitter's display name.
    """
    if sub.team:
        members = " & ".join(m.display_name for m in sub.team.members)
        if sub.team.name and sub.team.name.strip():
            return f"{sub.team.name} ({members})"
        return members
    return sub.submitted_by.display_name


async def _refresh_cdn_urls(bot, urls: List[str]) -> Dict[str, str]:
    """
    Ask Discord for freshly signed CDN URLs.

    Stored attachment URLs carry a signature (``ex``/``is``/``hm``
    query parameters) that makes them expire after 24h. This calls
    ``POST /attachments/refresh-urls`` with the bot token and returns an
    ``original -> refreshed`` mapping. URLs that could not be refreshed
    are simply absent from the mapping, so callers fall back to the
    stored URL.

    Args:
        bot: The bot instance (for its authenticated HTTP client).
        urls (list): Stored attachment URLs, exactly as persisted.

    Returns:
        dict: stored URL -> freshly signed URL.
    """
    refreshed: Dict[str, str] = {}
    for i in range(0, len(urls), 50):
        chunk = urls[i:i + 50]
        try:
            data = await bot.http.request(
                Route("POST", "/attachments/refresh-urls"),
                json={"attachment_urls": chunk},
            )
        except (discord.HTTPException, aiohttp.ClientError, asyncio.TimeoutError):
            continue  # network/API hiccup: stored URLs remain the fallback
        for item in data.get("refreshed_urls", []):
            if item.get("refreshed"):
                refreshed[item["original"]] = item["refreshed"]
    return refreshed


async def _download_one(
        session: aiohttp.ClientSession,
        sem: asyncio.Semaphore,
        sub,
        url: str,
) -> Tuple[object, Optional[bytes], Optional[str]]:
    """
    Download a single submission file.

    Args:
        session (aiohttp.ClientSession): Shared HTTP session.
        sem (asyncio.Semaphore): Concurrency limiter.
        sub: Submission entity (kept for naming and error reporting).
        url (str): URL to fetch - a refreshed CDN URL when available,
            otherwise the stored one.

    Returns:
        tuple: ``(sub, payload, error)`` - exactly one of payload/error is set.
    """
    async with sem:
        try:
            async with session.get(url) as resp:
                resp.raise_for_status()
                return sub, await resp.read(), None
        except Exception as exc:  # network, 404, expired CDN link…
            return sub, None, f"{type(exc).__name__}: {exc}"


def _prepare_entries(
        task,
        results,
        default_ext: str,
) -> Tuple[List[ArchiveEntry], List[str]]:
    """
    Turn download results into named archive entries.

    Filenames follow ``Task N - participant - 1m02s678.ext``, the ghost
    time being omitted for formats that do not carry one. Each entry also
    gets an estimated deflated size, so partitioning can pack archives close to the
    attachment limit regardless of how compressible the payloads are.

    Compresses every payload once, so run it in a worker thread.

    Args:
        task: Task entity (used for the filename prefix).
        results (list): ``(sub, payload, error)`` triples from _download_one.
        default_ext (str): Extension configured for the competition.

    Returns:
        tuple: ``(entries, failures)`` — failures are human-readable lines.
    """
    entries: List[ArchiveEntry] = []
    failures: List[str] = []
    used: Set[str] = set()

    for idx, (sub, payload, error) in enumerate(results, 1):
        if error is not None:
            failures.append(f"{idx}. {_who_for(sub)} — {error}")
            continue

        base = f"Task {task.number} - {_file_participants(sub)}"
        ghost = _ghost_time_from(payload)
        if ghost:
            base = f"{base} - {ghost}"

        name = _unique_name(base, _entry_ext(sub.file.path, default_ext), used)
        zip_size = (
            len(zlib.compress(payload, 6))
            + ZIP_ENTRY_OVERHEAD
            + 2 * len(name)
        )
        entries.append(
            ArchiveEntry(name, payload, sub.file.uploaded_at, zip_size)
        )

    return entries, failures


def _build_archive(entries: List[ArchiveEntry]) -> io.BytesIO:
    """
    Zip a batch of already-downloaded files in memory.

    Runs in a worker thread (see caller) so compression never blocks the
    event loop.

    Args:
        entries (list): the files to archive.

    Returns:
        io.BytesIO: Rewound buffer holding the archive.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for entry in entries:
            stamp = datetime.fromtimestamp(entry.uploaded_at, tz=timezone.utc)
            info = zipfile.ZipInfo(entry.name, date_time=stamp.timetuple()[:6])
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, entry.payload)
    buffer.seek(0)
    return buffer


def _partition(
        entries: List[ArchiveEntry],
        limit: int,
) -> List[List[ArchiveEntry]]:
    """
    Split entries into batches that each fit under the attachment limit.

    Sizes are the estimated deflated sizes from ``_prepare_entries``, so
    highly compressible payloads pack into a single archive instead of
    being split on their raw byte counts.


    Args:
        entries (list): the files to archive.
        limit (int): Maximum archive size in bytes.

    Returns:
        list: List of batches, each a list of entries.
    """
    batches: List[List[ArchiveEntry]] = []
    current: List[ArchiveEntry] = []
    running = 0
    for entry in entries:
        size = entry.zip_size
        if current and running + size > limit:
            batches.append(current)
            current, running = [], 0
        current.append(entry)
        running += size
    if current:
        batches.append(current)
    return batches


class GetSubmissionsCommand(commands.Cog):
    """
    Cog providing the `/get-submissions` host command.

    Attributes:
        task_mgr (TaskManager): Application service for task lifecycle and lookup.
    """

    def __init__(
        self,
        task_manager: TaskManager,
):
        self.task_mgr = task_manager

    @commands.hybrid_command(
        name="get-submissions",
        description="[Host] Retrieves all submissions for the current task",
        usage="$/get-submissions",
        help=("Retrieves all submission for the latest task. This shows, for each submission, the user (and their team "
              "if applicable), the time at which the file was submitted, and the time of the run itself. "
              "\n\nNote that unless the submission has been manually "
              "edited using /edit-submissions, the fetched timed may be unknown or wrong. This can happen if the "
              "competition is backwards, or is on multiple tracks.\n\n"

            "Parameters:\n"
                "None"
        ),
    )
    @host_only()
    async def get_submissions(self, ctx: commands.Context):
        """
        List all submissions for the active task or, if none is active,
        for the most recent task.

        Steps:
            1) Resolve active task, else last task; abort if none exist.
            2) Fetch submissions via service (already filtered by task).
            3) Sort by upload submission ID to preserve order of submissions
            4) Build formatted lines for solo/team entries.
            5) Chunk lines into messages under ~1950 chars.
            6) Send messages with a header on the first chunk.
            7) Download every submitted file and attach them as .zip archives.

        Args:
            ctx (commands.Context): Invocation context.

        Returns:
            None
        """
        # 1) Load active task, else last task
        task = await self.task_mgr.get_active_task()
        if not task:
            task = await self.task_mgr.get_last_task()
        if not task:
            return await ctx.send("There is no competition to retrieve submissions from.")

        # 2) Retrieve submissions for this task via submission service
        try:
            subs = await ctx.bot.submission_service.get_submissions()
        except Exception as exc:
            return await ctx.send(f"Error when retrieving results: {exc}")

        # 3) If there are no submissions
        if not subs:
            return await ctx.send(
                f"No one submitted to **Task {task.number}, {task.year}** :(")

        # 4) Sort by first submission ID
        subs.sort(key=lambda s: s.id)

        # 5) Build listing lines
        lines: List[str] = []
        for idx, sub in enumerate(subs, 1):
            who = _who_for(sub)
            run_t = fmt_time(sub.time)
            ts    = f"<t:{sub.file.uploaded_at}:f>"
            lines.append(
                f"{idx}. {who} : {sub.file.path} – {ts} | "
                f"Fetched time: ||{run_t}||"
            )

        # 6) Chunk output to respect message length limits
        parts: List[str] = []
        current = ""
        for line in lines:
            # +1 accounts for the newline
            if len(current) + len(line) + 1 > MSG_LIMIT - BUFFER:
                parts.append(current)
                current = ""
            current += line + "\n"
        if current:
            parts.append(current)

        # 7) Send output
        header = (
            f"__**Task {task.number} submissions**__:\n"
            f"-# (Total submissions: {len(lines)})\n\n"
        )
        for i, part in enumerate(parts):
            await ctx.reply(
                header + part if i == 0 else part,
                allowed_mentions=discord.AllowedMentions.none(),
                suppress_embeds=True,
            )
            # Small delay to avoid rate limits
            await asyncio.sleep(1)

        await self._send_archives(ctx, task, subs)

        return None

    # noinspection PyMethodMayBeStatic
    async def _send_archives(self, ctx: commands.Context, task, subs) -> None:
        """
        Download every submission file and post them as zip attachment(s).

        Stored CDN URLs are refreshed through Discord's API first, since
        their signatures expire ~24h after issuance and many submissions
        are downloaded well past that.

        Args:
            ctx (commands.Context): Invocation context.
            task: Task entity (used for naming).
            subs (list): Submissions, already sorted by id.

        Returns:
            None
        """
        comp = (await ctx.bot.config_service.get_guild_config(ctx.guild.id)).comp
        default_ext = (
            await ctx.bot.config_service.get_submission_file_extension(comp)
        ).ext.lower().lstrip(".")

        progress = await ctx.send(
            f"Downloading {len(subs)} submission file(s)…"
        )

        url_map = await _refresh_cdn_urls(
            ctx.bot, [sub.file.path for sub in subs]
        )

        sem = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
        async with aiohttp.ClientSession(timeout=DOWNLOAD_TIMEOUT) as session:
            results = await asyncio.gather(
                *(_download_one(
                    session, sem, sub,
                    url_map.get(sub.file.path, sub.file.path),
                ) for sub in subs)
            )

        entries, failures = await asyncio.to_thread(
            _prepare_entries, task, results, default_ext
        )

        if not entries:
            await progress.edit(
                content="Could not download any submission file.\n"
                        + "\n".join(failures[:MAX_REPORTED_FAILURES])
            )
            return

        limit = getattr(ctx.guild, "filesize_limit", None) or DEFAULT_FILESIZE_LIMIT
        batches = _partition(entries, max(limit - ZIP_OVERHEAD_MARGIN, 1))

        for part_no, batch in enumerate(batches, 1):
            buffer = await asyncio.to_thread(_build_archive, batch)
            suffix = "" if len(batches) == 1 else f" - part {part_no}"
            filename = f"Task {task.number} Submissions{suffix}.zip"
            await ctx.send(file=discord.File(buffer, filename=filename))
            await asyncio.sleep(1)

        summary = f"Archived {len(entries)} file(s)."
        if failures:
            summary += (
                    "\nFailed to download:\n"
                    + "\n".join(failures[:MAX_REPORTED_FAILURES])
            )
        await progress.edit(content=summary)


async def setup(bot: commands.Bot) -> None:
    """
    Register the GetSubmissionsCommand cog.

    Args:
        bot (commands.Bot): The bot instance.
    """
    await bot.add_cog(
        GetSubmissionsCommand(
            task_manager = bot.task_manager,
        )
    )