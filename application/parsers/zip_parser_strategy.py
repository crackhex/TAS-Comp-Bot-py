"""
Zip File Parser Strategy
=============================

Module path:
    src/application/parsers/zip_parser_strategy.py

Summary:
    ParserStrategy implementation for Zip files, used for special types of tasks that require more than a type of file.

Responsibilities:
    - Check if the file bytes are indeed a zip by verifying its magic headers
    - Produce a ZipFile object with default run_time=0
"""

from domain.entities import ZipFile
from io import BytesIO
import zipfile
from .parser_strategy import ParserStrategy


class ZipParserStrategy(ParserStrategy):
    """
    Concrete ParserStrategy for .zip files.

    supports(): accepts any zip
    parse(): returns a ZipFile
    """

    def supports(self, file_bytes: bytes) -> bool:
        """
        Under the hood, this checks for the magic headers
        """
        try:
            return zipfile.is_zipfile(BytesIO(file_bytes))
        except Exception:
            return False

    def parse(self, file_bytes: bytes, uploaded_at: int) -> ZipFile:
        """
        Parse the Zip file into a ZipFile domain object.

        Args:
            file_bytes (bytes): raw file content
            uploaded_at (int): UNIX timestamp when file was received

        Returns:
            ZipFile: with run_time=0.0
        """
        return ZipFile(
            path="",
            uploaded_at=uploaded_at,
        )
