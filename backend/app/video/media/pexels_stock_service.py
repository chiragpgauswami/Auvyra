import os
import shutil
import hashlib
import httpx
from datetime import datetime, timezone
from typing import List, Optional, Set
from urllib.parse import urlencode
from loguru import logger
from backend.app.video.models import MediaItem, VideoAspect
from backend.app.video.storyboard import VisualScene, VisualStoryboard

class PexelsStockService:
    """Production-grade Pexels stock video search, candidate ranking, caching, and multi-clip assignment."""

    def __init__(self, api_keys: Optional[str] = None, cache_dir: str = "media/cache/pexels"):
        raw_keys = api_keys or os.getenv("PEXELS_API_KEY", "")
        self.api_keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
        self.key_idx = 0
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_api_key(self) -> str:
        if not self.api_keys:
            raise ValueError("PEXELS_API_KEY is not configured in environment or settings")
        key = self.api_keys[self.key_idx]
        self.key_idx = (self.key_idx + 1) % len(self.api_keys)
        return key

    async def search_candidates(
        self,
        query: str,
        aspect_ratio: VideoAspect = VideoAspect.portrait,
        min_duration: float = 2.0,
        per_page: int = 15
    ) -> List[MediaItem]:
        """Search Pexels for candidate videos matching query, with orientation-first fallback."""
        if not self.api_keys:
            logger.warning("No Pexels API key available for stock video search")
            return []

        orientation = "portrait" if aspect_ratio == VideoAspect.portrait else ("landscape" if aspect_ratio == VideoAspect.landscape else "square")

        candidates = await self._query_pexels_api(query, orientation=orientation, min_duration=min_duration, per_page=per_page)
        
        # If portrait search yielded 0 results, fall back to searching without orientation filter
        if not candidates and aspect_ratio == VideoAspect.portrait:
            logger.info(f"Zero portrait videos for '{query}', falling back to general orientation search")
            candidates = await self._query_pexels_api(query, orientation=None, min_duration=min_duration, per_page=per_page)

        return candidates

    async def _query_pexels_api(
        self,
        query: str,
        orientation: Optional[str],
        min_duration: float,
        per_page: int
    ) -> List[MediaItem]:
        headers = {
            "Authorization": self._get_api_key(),
            "User-Agent": "Auvyra-Autonomous-Engine/2.0"
        }
        params = {"query": query, "per_page": per_page}
        if orientation:
            params["orientation"] = orientation

        url = f"https://api.pexels.com/v1/videos/search?{urlencode(params)}"
        items: List[MediaItem] = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    logger.error(f"Pexels search returned HTTP {resp.status_code}: {resp.text[:200]}")
                    return []

                data = resp.json()
                videos = data.get("videos", [])

                for v in videos:
                    duration = float(v.get("duration", 0))
                    if duration < min_duration:
                        continue

                    video_files = v.get("video_files", [])
                    # Rank video files by resolution quality
                    ranked_file = self._select_best_video_file(video_files, orientation)
                    if ranked_file:
                        user_info = v.get("user") or {}
                        items.append(MediaItem(
                            provider="pexels",
                            url=ranked_file["link"],
                            download_url=ranked_file["link"],
                            duration=duration,
                            width=ranked_file["width"],
                            height=ranked_file["height"],
                            search_term=query,
                            crop_mode="cover" if orientation != "portrait" else "fit",
                            pexels_id=v.get("id"),
                            photographer=user_info.get("name", ""),
                            photographer_url=user_info.get("url", ""),
                            video_url=v.get("url", ""),
                            selected_at=datetime.now(timezone.utc).isoformat()
                        ))

            except Exception as e:
                logger.error(f"Error querying Pexels API for '{query}': {e}")

        return items

    def _select_best_video_file(self, video_files: list, desired_orientation: Optional[str]) -> Optional[dict]:
        """Selects HD/Full-HD video file prioritizing 1080p, then 720p, then 4k."""
        valid_files = [f for f in video_files if f.get("link") and f.get("width") and f.get("height")]
        if not valid_files:
            return None

        def score_file(f: dict) -> int:
            w = int(f.get("width", 0))
            h = int(f.get("height", 0))
            score = 0
            # Preferred height for portrait is 1920 (1080x1920)
            if desired_orientation == "portrait":
                if h == 1920 and w == 1080: score += 100
                elif h >= 1280 and w >= 720: score += 80
                elif h > w: score += 50
                elif w >= 1920: score += 30
            else:
                if w == 1920 and h == 1080: score += 100
                elif w >= 1280 and h >= 720: score += 80
                elif w > h: score += 50

            # Penalize excessively massive 4k files for memory/time efficiency
            if w > 2160 or h > 3840:
                score -= 20
            return score

        valid_files.sort(key=score_file, reverse=True)
        return valid_files[0]

    async def download_video(self, item: MediaItem, dest_dir: str) -> str:
        """Downloads video using SHA-256 caching. Avoids duplicate network transfers."""
        url_hash = hashlib.sha256(item.url.encode("utf-8")).hexdigest()
        cache_filename = f"pexels_{url_hash}.mp4"
        cache_path = os.path.join(self.cache_dir, cache_filename)

        target_dest = os.path.join(dest_dir, f"scene_{item.scene_index or 0}_{cache_filename}")
        if os.path.exists(cache_path) and os.path.getsize(cache_path) > 50000:
            shutil.copyfile(cache_path, target_dest)
        else:
            # Download if not in cache
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                try:
                    async with client.stream("GET", item.url) as resp:
                        resp.raise_for_status()
                        temp_cache_path = f"{cache_path}.tmp"
                        with open(temp_cache_path, "wb") as f:
                            async for chunk in resp.aiter_bytes(chunk_size=65536):
                                f.write(chunk)
                        os.replace(temp_cache_path, cache_path)

                    shutil.copyfile(cache_path, target_dest)
                except Exception as e:
                    logger.error(f"Failed to download video from {item.url}: {e}")
                    return ""

        item.local_path = target_dest
        item.file_size = os.path.getsize(target_dest)

        # Compute deterministic sha256 of downloaded media
        h = hashlib.sha256()
        with open(target_dest, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        item.sha256 = h.hexdigest()
        return target_dest


    async def fetch_media_for_storyboard(
        self,
        storyboard: VisualStoryboard,
        dest_dir: str,
        aspect_ratio: VideoAspect = VideoAspect.portrait
    ) -> List[MediaItem]:
        """Resolves and downloads stock footage for every single scene in the storyboard."""
        os.makedirs(dest_dir, exist_ok=True)
        assigned_media: List[MediaItem] = []
        used_urls: Set[str] = set()

        for scene in storyboard.scenes:
            selected_item: Optional[MediaItem] = None

            # Try each search query for this scene
            for query in scene.search_queries:
                candidates = await self.search_candidates(
                    query=query,
                    aspect_ratio=aspect_ratio,
                    min_duration=scene.duration
                )

                # Pick first unused candidate
                for cand in candidates:
                    if cand.url not in used_urls:
                        selected_item = cand
                        break

                if selected_item:
                    break

            # Fallback to storyboard topic if queries yielded no unique video
            if not selected_item:
                fallback_query = storyboard.title or "cinematic vertical"
                candidates = await self.search_candidates(
                    query=fallback_query,
                    aspect_ratio=aspect_ratio,
                    min_duration=scene.duration
                )
                for cand in candidates:
                    if cand.url not in used_urls:
                        selected_item = cand
                        break
                if not selected_item and candidates:
                    # Reuse a candidate if library exhausted
                    selected_item = candidates[0]

            if selected_item:
                selected_item.scene_index = scene.scene_index
                selected_item.scene_id = getattr(scene, "scene_id", None) or f"scene_{scene.scene_index}"
                used_urls.add(selected_item.url)
                local_path = await self.download_video(selected_item, dest_dir)
                if local_path:
                    assigned_media.append(selected_item)
                else:
                    logger.warning(f"Failed download for scene {scene.scene_index}")

            else:
                logger.warning(f"No stock video candidate found for scene {scene.scene_index}")

        logger.info(f"Storyboard media assignment: {len(assigned_media)} / {len(storyboard.scenes)} scenes filled with stock video")
        return assigned_media
