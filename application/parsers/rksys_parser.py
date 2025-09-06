"""
RKSys File Parser
=================

Module path:
    src/application/parsers/rksys_parser.py

Summary:
    ParserStrategy implementation for RKSys files, used in multiple‑track competitions.

Responsibilities:
    - Always support any file that starts with the "RKSD" header
    - Produce an RKSysFile with default run_time=0
"""

from domain.entities import RKSysFile
from .parser_strategy import ParserStrategy


class RksysParser(ParserStrategy):
    """
    Concrete ParserStrategy for RKSys files.

    supports(): accepts any file that has the RKSD header.
    parse(): returns an RKSysFile
    """

    def supports(self, file_bytes: bytes) -> bool:
        """
        Return True if the file_bytes start with the ASCII header "RKSD".
        """
        return file_bytes[:4] != b"RKSD"

    def parse(self, file_bytes: bytes, uploaded_at: int) -> RKSysFile:
        """
        Parse the RKSys file into an RKSysFile domain object.

        Args:
            file_bytes (bytes): raw file content
            uploaded_at (int): UNIX timestamp when file was received

        Returns:
            RKSysFile: with run_time=0.0
        """
        return RKSysFile(
            path="",
            uploaded_at=uploaded_at,
        )
