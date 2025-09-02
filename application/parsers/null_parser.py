"""
Null / Fallback Parser
======================

Always returns *False* from ``supports`` and raises a clear exception from
``parse``.  This lets the bot start with “no parser selected” while still
satisfying the ParserStrategy protocol.
"""

from domain.entities import SubmissionFile
from .parser_strategy import ParserStrategy


class NullParser(ParserStrategy):
    """ParserStrategy that never matches any file type."""

    # ──────────────────────────────────────────────── #
    # Protocol implementation                         #
    # ──────────────────────────────────────────────── #

    def supports(self, file_bytes: bytes) -> bool:
        """Return ``False`` for every byte-sequence."""
        return False

    def parse(self, file_bytes: bytes, uploaded_at_epoch: int):
        """Always raises – the caller picked an unsupported file type."""
        raise RuntimeError(
            "No submission-file type has been configured for this competition. "
            "An administrator must run `/set-file` first."
        )
