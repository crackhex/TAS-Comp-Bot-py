"""
File Parser
===========

Module path:
    src/application/parsers/file_parser.py

Summary:
    Delegates parsing to exactly one ParserStrategy, which can be swapped at
    runtime (e.g., via the `/set-file` host command).  If no strategy is
    provided on construction the parser falls back to NullParser, ensuring
    that submissions are rejected until a host picks a file type.
"""

from __future__ import annotations

from typing import Optional

from domain.entities import SubmissionFile
from .parser_strategy import ParserStrategy
from .null_parser     import NullParser


class FileParser:
    """
    Wrapper around a single ``ParserStrategy`` instance.

    The strategy can be replaced at runtime with set_strategy.
    """

    # ──────────────────────────── Init / Config ─────────────────────────── #

    def __init__(self, strategy: Optional[ParserStrategy] = None) -> None:
        """
        Args:
            strategy: Concrete parser to start with.  If None, the parser
                      is the null parser.
        """
        self._strategy: ParserStrategy = strategy or NullParser()

    def set_strategy(self, strategy: ParserStrategy) -> None:
        """Replace the current parsing strategy"""
        self._strategy = strategy

    # ────────────────────────────── Parsing ────────────────────────────── #

    def parse(self, file_bytes: bytes, uploaded_at_epoch: int) -> SubmissionFile:
        """
        Parse file_bytes using the current strategy.

        Raises
        ------
        RuntimeError
            If the current strategy does not support the given file format.
        """
        if not self._strategy.supports(file_bytes):
            raise RuntimeError(
                f"{self._strategy.__class__.__name__} does not support this file type. "
                "An administrator may need to run `/set-file`."
            )
        return self._strategy.parse(file_bytes, uploaded_at_epoch)

    @property
    def strategy(self) -> ParserStrategy:
        """Read-only access to the currently configured strategy."""
        return self._strategy
