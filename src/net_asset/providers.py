from __future__ import annotations


from abc import ABC, abstractmethod


from dataclasses import dataclass, field


from typing import List, Optional


@dataclass
class AssetResult:

    id: str

    title: str

    media_type: str  # "video" | "image" | "audio"

    provider: str  # "pexels" | "pixabay" | "freesound"

    preview_url: str  # low-res thumbnail for quick display

    download_url: str  # direct file URL to download

    page_url: str  # original page for attribution link

    author: str

    attribution: str  # required attribution text

    license: str  # e.g. "Pexels License", "Pixabay License", "CC BY"

    duration: Optional[float] = None  # seconds, video/audio only

    width: Optional[int] = None  # pixels, image/video only

    height: Optional[int] = None

    tags: List[str] = field(default_factory=list)

    description: str = ""


class BaseProvider(ABC):

    name: str = ""

    @abstractmethod
    def search(
        self,
        query: str,
        media_type: str,
        per_page: int = 10,
        **kwargs,
    ) -> List[AssetResult]:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Return True when the required API key is configured."""

        ...
