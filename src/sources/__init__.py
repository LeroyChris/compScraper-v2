"""Scraper registry."""

from __future__ import annotations

from src.sources.base import BaseScraper
from src.sources.generic import SITES, GenericSiteScraper
from src.sources.infolomba import InfolombaScraper
from src.sources.infolombait import InfolombaitScraper
from src.sources.informasilomba import InformasilombaScraper
from src.sources.luarkampus import LuarkampusScraper
from src.sources.puspresnas import PuspresnasScraper


def build_sources() -> list[BaseScraper]:
    """All active providers, in priority order."""
    sources: list[BaseScraper] = [
        InfolombaScraper(),
        LuarkampusScraper(),
        PuspresnasScraper(),
        InfolombaitScraper(),
        InformasilombaScraper(),
    ]
    sources.extend(GenericSiteScraper(cfg) for cfg in SITES)
    return sources


__all__ = [
    "build_sources",
    "BaseScraper",
    "InfolombaScraper",
    "InfolombaitScraper",
    "InformasilombaScraper",
    "LuarkampusScraper",
    "PuspresnasScraper",
    "GenericSiteScraper",
]
