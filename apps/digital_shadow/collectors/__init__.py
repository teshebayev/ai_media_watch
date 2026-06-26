"""Коллекторы Digital Shadow: clearweb (httpx), darknet (мок для демо / Tor), paste-сайты."""

from .base import Collector, RawItem
from .darknet_mock import DarknetMockCollector
from .demo_clusters import DemoClusterCollector
from .file_collector import FileCollector
from .http_page import HttpPageCollector
from .paste_sites import PasteSiteCollector
from .rss import RssCollector

__all__ = [
    "Collector", "RawItem", "DarknetMockCollector", "DemoClusterCollector",
    "FileCollector", "HttpPageCollector", "RssCollector", "PasteSiteCollector",
]
