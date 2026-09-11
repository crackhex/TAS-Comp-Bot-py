"""
RKG File Parser Strategy
=========================

Module path:
    src/application/parsers/rkg_parser_strategy.py

Summary:
    ParserStrategy implementation for the RKG file format, used in non‑multiple‑track competitions.

Responsibilities:
    - Handle CTGP compression flag and trim the bytearray accordingly
    - Extract lap times, character ID, and vehicle ID from the RKG data
    - Compute the run time (in seconds) for the first lap
"""

import struct
from typing import List
from domain.entities import RKGFile
from .parser_strategy import ParserStrategy
from crccheck.crc import Crc32IsoHdlc

def _decode_time(b1: int, b2: int, b3: int) -> int:
    """
    Decode MKW's packed 3-byte time representation into whole milliseconds.

    The same 7/7/10 bit layout is used for the header's finishing time and
    for every lap time.

    Returns:
        int: time in whole milliseconds
    """
    minutes = b1 >> 1
    seconds = ((b1 & 0x1) << 6) | (b2 >> 2)
    millis  = ((b2 & 0x3) << 8) | b3
    return (minutes * 60 + seconds) * 1000 + millis


def get_ghost_time(rkg: bytearray) -> float:
    """
    Extract the ghost's finishing time from the RKG header.

    Stored at offsets 0x04-0x06, always inside the fixed 0x88-byte header,
    so CTGP compression never affects it. This is the *total* run time, as
    opposed to ``get_lap_times`` which returns each lap separately.

    Returns:
        float: total run time in seconds (e.g. 62.678)
    """
    return _decode_time(rkg[0x04], rkg[0x05], rkg[0x06]) / 1000


def get_lap_times(rkg: bytearray) -> List[str]:
    """
    Extract lap time strings from an RKG bytearray.

    Handles CTGP compression: if the 0x08 flag is set in byte 12,
    reads the compressed length at offset 0x88 and trims the array.

    Each lap is encoded in 3 bytes:
      - high 7 bits of byte contain minutes (m)
      - next 7 bits combine seconds (s)
      - low 10 bits combine milliseconds (ms)

    Returns:
        List[str]: lap times formatted as "M:SS.mmm"
    """
    # CTGP compression flag present?
    if (rkg[12] & 0x08) == 0x08:
        # Read original uncompressed length from bytes 0x88–0x8B
        length = struct.unpack(">I", rkg[0x88:0x8C])[0] + 0x90
        rkg = rkg[:length]

    nr_laps = min(rkg[0x10], 5)
    lap_times: List[str] = []
    for i in range(nr_laps):
        # Byte layout: 3 bytes per lap starting at offset 0x11
        b1 = rkg[0x11 + 3*i]
        b2 = rkg[0x12 + 3*i]
        b3 = rkg[0x13 + 3*i]

        total_ms = _decode_time(b1, b2, b3)
        m, rem   = divmod(total_ms, 60_000)
        s, ms    = divmod(rem, 1000)

        lap_times.append(f"{m}:{s:02}.{ms:03}")
    return lap_times


def get_character(rkg: bytearray) -> int:
    """
    Extract the character ID from an RKG bytearray.

    Handles CTGP compression similarly to get_lap_times.

    Returns:
        int: character identifier (0–31)
    """
    if (rkg[12] & 0x08) == 0x08:
        length = struct.unpack(">I", rkg[0x88:0x8C])[0] + 0x90
        rkg = rkg[:length]
    # Character bits: combine bits from bytes 0x08 and 0x09
    return ((rkg[0x8] & 0x3) << 4) | (rkg[0x9] >> 4)


def get_vehicle(rkg: bytearray) -> int:
    """
    Extract the vehicle ID from an RKG bytearray.

    Handles CTGP compression similarly to get_lap_times.

    Returns:
        int: vehicle identifier
    """
    if (rkg[12] & 0x08) == 0x08:
        length = struct.unpack(">I", rkg[0x88:0x8C])[0] + 0x90
        rkg = rkg[:length]
    # Vehicle bits stored at byte offset 0x08 (upper 6 bits)
    return rkg[0x8] >> 2


def readable_to_float(time_str: str) -> float:
    """
    Convert a time string "M:SS.mmm" into total seconds as float.

    Args:
        time_str (str): formatted time, e.g. "1:23.456"

    Returns:
        float: total seconds (e.g. 83.456)
    """
    m, rest = time_str.split(":")
    s, ms   = rest.split(".")
    return int(m) * 60 + int(s) + int(ms) / 1000


class RkgParserStrategy(ParserStrategy):
    """
    Concrete ParserStrategy for RKG files.

    supports(): checks for the "RKGD" magic header and does a CRC check.
    parse(): extracts lap times, character, vehicle, and run time.
    """

    def supports(self, file_bytes: bytes) -> bool:
        """
        Return True if the file_bytes start with the ASCII header "RKGD".
        """

        our_crc = Crc32IsoHdlc.calc(file_bytes[0:-4])
        rkg_crc = int.from_bytes(file_bytes[-4:])

        return (file_bytes[:4] == b"RKGD") and (rkg_crc == our_crc)

    def parse(self, file_bytes: bytes, uploaded_at: int) -> RKGFile:
        """
        Parse the RKG file bytes into an RKGFile domain object.

        Args:
            file_bytes (bytes): raw file content
            uploaded_at (int): UNIX timestamp when file was received

        Returns:
            RKGFile: populated with lap_times, character, vehicle, run_time, ghost_time
        """
        rkg = bytearray(file_bytes)
        laps = get_lap_times(rkg)

        # Use first lap as run_time, or zero if no laps
        run_time = readable_to_float(laps[0]) if laps else 0.0
        char_id  = get_character(rkg)
        veh_id   = get_vehicle(rkg)
        ghost_time = get_ghost_time(rkg)

        return RKGFile(
            path="",
            uploaded_at=uploaded_at,
            lap_times=laps,
            character=char_id,
            vehicle=veh_id,
            run_time=run_time,
            ghost_time=ghost_time,
        )
