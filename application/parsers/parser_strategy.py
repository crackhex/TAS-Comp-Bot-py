"""
Parser Strategy Interface
=========================

Module path:
    src/application/parsers/parser_strategy.py

Summary:
    Defines the interface that all file parsing strategies must implement.

Responsibilities:
    - supports: determine if the strategy can parse given bytes
    - parse: perform the parsing and return a SubmissionFile
"""

from typing import Protocol
from domain.entities import SubmissionFile


class ParserStrategy(Protocol):
    """
    Protocol for file parsing strategies.
    """

    def supports(self, file_bytes: bytes) -> bool:
        """
        Determine whether this strategy can handle the given bytes.

        Args:
            file_bytes (bytes): content of the file to parse.

        Returns:
            bool: True if this strategy supports the format.
        """
        ...

    def parse(self, file_bytes: bytes, uploaded_at_epoch: int) -> SubmissionFile:
        """
        Parse the provided bytes into a domain SubmissionFile object.

        Args:
            file_bytes (bytes): raw content of the submission file.
            uploaded_at_epoch (int): UNIX timestamp of the upload.

        Returns:
            SubmissionFile: parsed file with extracted metadata.
        """
        ...
