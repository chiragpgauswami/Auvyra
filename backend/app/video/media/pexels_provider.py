import os
import httpx
from typing import List
from urllib.parse import urlencode
from loguru import logger
from .base import MediaProvider
from ..models import MediaItem, VideoAspect

class PexelsProvider(MediaProvider):
    def __init__(self, api_keys: str = None):
        self.api_keys = [k.strip() for k in (api_keys or os.getenv("PEXELS_API_KEY", "")).split(",") if k.strip()]
        self.key_idx = 0
        
    def _get_key(self):
        if not self.api_keys:
            raise ValueError("PEXELS_API_KEY not set")
        key = self.api_keys[self.key_idx]
        self.key_idx = (self.key_idx + 1) % len(self.api_keys)
        return key

    async def search(self, query: str, aspect_ratio: VideoAspect = VideoAspect.portrait, min_duration: int = 3) -> List[MediaItem]:
        video_width, video_height = aspect_ratio.to_resolution()
        orientation = aspect_ratio.name
        
        headers = {
            "Authorization": self._get_key(),
            "User-Agent": "Mozilla/5.0"
        }
        params = {"query": query, "per_page": 20, "orientation": orientation}
        query_url = f"https://api.pexels.com/v1/videos/search?{urlencode(params)}"
        
        items = []
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(query_url, headers=headers, timeout=30)
                response.raise_for_status()
                data = response.json()
                
                for v in data.get("videos", []):
                    duration = v.get("duration", 0)
                    if duration < min_duration:
                        continue
                        
                    for vf in v.get("video_files", []):
                        w, h = int(vf.get("width", 0)), int(vf.get("height", 0))
                        
                        # Check orientation
                        is_match = False
                        if aspect_ratio == VideoAspect.portrait and h > w: is_match = True
                        elif aspect_ratio == VideoAspect.landscape and w > h: is_match = True
                        elif aspect_ratio == VideoAspect.square and w == h: is_match = True
                        
                        if is_match and w >= min(video_width, 480):
                            items.append(MediaItem(
                                provider="pexels",
                                url=vf.get("link"),
                                duration=duration,
                                width=w,
                                height=h,
                                search_term=query
                            ))
                            break
            except Exception as e:
                logger.error(f"Pexels search failed: {e}")
                
        return items
        
    async def download(self, item: MediaItem, dest_dir: str) -> str:
        filename = f"{item.provider}_{hash(item.url)}.mp4"
        dest_path = os.path.join(dest_dir, filename)
        
        if os.path.exists(dest_path):
            return dest_path
            
        async with httpx.AsyncClient() as client:
            try:
                async with client.stream("GET", item.url, follow_redirects=True) as response:
                    response.raise_for_status()
                    with open(dest_path, "wb") as f:
                        async for chunk in response.aiter_bytes():
                            f.write(chunk)
                item.local_path = dest_path
                return dest_path
            except Exception as e:
                logger.error(f"Failed to download Pexels video {item.url}: {e}")
                return ""
