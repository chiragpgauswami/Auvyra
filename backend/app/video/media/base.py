from abc import ABC, abstractmethod
from typing import List
from ..models import MediaItem, VideoAspect

class MediaProvider(ABC):
    @abstractmethod
    async def search(self, query: str, aspect_ratio: VideoAspect = VideoAspect.portrait, min_duration: int = 3) -> List[MediaItem]:
        """Search for stock media matching query and aspect ratio."""
        pass
    
    @abstractmethod
    async def download(self, item: MediaItem, dest_dir: str) -> str:
        """Download media item to dest_dir. Returns local file path."""
        pass
    
    async def search_and_download(self, queries: List[str], dest_dir: str, 
                                   aspect_ratio: VideoAspect = VideoAspect.portrait, 
                                   target_duration: float = 60) -> List[str]:
        """Search multiple queries and download until target_duration is met."""
        downloaded_paths = []
        total_duration = 0.0
        
        for query in queries:
            if total_duration >= target_duration:
                break
                
            items = await self.search(query, aspect_ratio)
            for item in items:
                if total_duration >= target_duration:
                    break
                
                path = await self.download(item, dest_dir)
                if path:
                    downloaded_paths.append(path)
                    total_duration += item.duration
                    
        return downloaded_paths
