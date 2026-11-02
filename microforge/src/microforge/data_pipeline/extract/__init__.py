"""Extracteurs par source."""

from microforge.data_pipeline.extract.db_jlcparts import JlcpartsExtractor
from microforge.data_pipeline.extract.file_arduino_index import ArduinoIndexExtractor
from microforge.data_pipeline.extract.file_fritzing import FritzingExtractor
from microforge.data_pipeline.extract.rest_digikey import DigiKeyExtractor
from microforge.data_pipeline.extract.rest_fx import FrankfurterExtractor
from microforge.data_pipeline.extract.rest_github import GitHubLibrariesExtractor
from microforge.data_pipeline.extract.rest_mouser import MouserExtractor
from microforge.data_pipeline.extract.scrape_shop import ShopScraper

EXTRACTORS = {
    "digikey": DigiKeyExtractor,
    "mouser": MouserExtractor,
    "github": GitHubLibrariesExtractor,
    "fx": FrankfurterExtractor,
    "arduino_index": ArduinoIndexExtractor,
    "fritzing": FritzingExtractor,
    "shop": ShopScraper,
    "jlcparts": JlcpartsExtractor,
}

__all__ = ["EXTRACTORS"]
