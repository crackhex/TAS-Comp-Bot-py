"""
Registry
===========

Module path:
    src/application/parsers/registry.py

Summary:
    Maps file extension to parsing strategies and provides helper methods
"""

from typing import Dict, Type, Optional

from application.parsers.parser_strategy import ParserStrategy
from application.parsers.rkg_parser_strategy import RkgParserStrategy
from application.parsers.rksys_parser_strategy import RksysParserStrategy
from application.parsers.zip_parser_strategy import ZipParserStrategy

EXTENSION_STRATEGIES: Dict[str, Type[ParserStrategy]] = {
    "rkg":   RkgParserStrategy,
    "dat":   RksysParserStrategy,
    "zip":   ZipParserStrategy,
}

def get_strategy_cls(ext: str) -> Optional[Type[ParserStrategy]]:
    return EXTENSION_STRATEGIES.get(ext.lower())

def new_strategy(ext: str) -> Optional[ParserStrategy]:
    cls = get_strategy_cls(ext)
    return cls() if cls else None

def candidates_excluding(current: ParserStrategy) -> list[ParserStrategy]:
    """Helper for fallback loop in parse_file()."""
    current_cls = type(current)
    return [cls() for cls in EXTENSION_STRATEGIES.values() if cls is not current_cls]