"""
Time Formatting Utilities
=========================

Module path:
    src/adapters/discord/utils/time_format.py

Summary:
    Single source of truth for rendering run times in Discord output and
    filenames. Every duration in the bot is a float in seconds; every
    formatter here rounds to whole milliseconds *before* splitting,
    because float arithmetic stores 48.687 as 48.68699999…, which
    truncation would render as .686.
"""

from typing import Tuple

# Placeholder shown when a time is missing or not yet fetched.
UNKNOWN_TIME = "??:??.???"


def _split_ms(seconds: float) -> Tuple[int, int, int]:
    """
    Split a duration in seconds into ``(minutes, seconds, milliseconds)``.

    Args:
        seconds (float): duration in seconds.

    Returns:
        tuple: minutes, seconds, milliseconds - all whole numbers.
    """
    total_ms = round(seconds * 1000)
    m, rem = divmod(total_ms, 60_000)
    s, ms  = divmod(rem, 1000)
    return m, s, ms


def fmt_time(seconds: float | None) -> str:
    """
    Format a run time as ``M:SS.mmm`` for Discord display.

    Args:
        seconds (float | None): Time in seconds, may be None.

    Returns:
        str: Human-readable time; ``??:??.???`` if missing or non-positive.
    """
    if not seconds or seconds <= 0:
        return UNKNOWN_TIME
    m, s, ms = _split_ms(seconds)
    return f"{m}:{s:02}.{ms:03}"


def fmt_filename_time(seconds: float) -> str:
    """
    Format a run time as ``1m02s678`` for use inside a filename.

    Colons are illegal on Windows, hence the letter separators.

    Args:
        seconds (float): Time in seconds. Caller guarantees it is present.

    Returns:
        str: Filename-safe time string.
    """
    m, s, ms = _split_ms(seconds)
    return f"{m}m{s:02}s{ms:03}"