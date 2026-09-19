import os
import subprocess
import shutil
import hashlib
from typing import List
from loguru import logger
from .base import MediaProvider
from ..models import MediaItem, VideoAspect
from ..validation import validate_media_asset

# High-contrast, dynamic modern motion palettes
VISUAL_THEMES = [
    # Theme 0: Deep Tech (Midnight, Indigo, Royal Blue, Electric Cyan)
    {"c0": "0x0f172a", "c1": "0x1e1b4b", "c2": "0x2563eb", "c3": "0x06b6d4", "type": "radial", "speed": "0.025"},
    # Theme 1: Cyber Sunset (Plum, Deep Violet, Neon Rose, Amber)
    {"c0": "0x18181b", "c1": "0x4c1d95", "c2": "0xbe185d", "c3": "0xf59e0b", "type": "spiral", "speed": "0.030"},
    # Theme 2: Emerald Frontier (Dark Forest, Emerald, Bright Teal, Mint)
    {"c0": "0x022c22", "c1": "0x065f46", "c2": "0x0d9488", "c3": "0x34d399", "type": "radial", "speed": "0.020"},
    # Theme 3: Electric Nebula (Midnight Navy, Cyber Magenta, Vivid Blue, Electric Purple)
    {"c0": "0x020617", "c1": "0x581c87", "c2": "0x3b82f6", "c3": "0xc026d3", "type": "linear", "speed": "0.035"},
]

class LocalMediaProvider(MediaProvider):
    def __init__(self, search_dir: str = "media/videos"):
        self.search_dir = search_dir
        os.makedirs(self.search_dir, exist_ok=True)
        
    def _create_dynamic_motion_clip(self, output_path: str, width: int, height: int, theme_idx: int = 0, duration: int = 5) -> str:
        """Create a vibrant procedural motion background clip using FFmpeg's gradients filter."""
        ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
        theme = VISUAL_THEMES[theme_idx % len(VISUAL_THEMES)]
        
        filter_str = (
            f"gradients=s={width}x{height}:r=30:"
            f"c0={theme['c0']}:c1={theme['c1']}:c2={theme['c2']}:c3={theme['c3']}:"
            f"nb_colors=4:type={theme['type']}:speed={theme['speed']}"
        )
        
        cmd = [
            ffmpeg_bin, "-y",
            "-f", "lavfi",
            "-i", filter_str,
            "-t", str(duration),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            output_path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0 or not os.path.exists(output_path):
            raise RuntimeError(f"FFmpeg failed to generate motion scene: {res.stderr}")
            
        return output_path

    async def search(self, query: str, aspect_ratio: VideoAspect = VideoAspect.portrait, min_duration: int = 3) -> List[MediaItem]:
        items = []
        width, height = aspect_ratio.to_resolution()
        
        # 1. Look for existing valid video clips in search directory
        if os.path.exists(self.search_dir):
            for f in sorted(os.listdir(self.search_dir)):
                if f.endswith((".mp4", ".mov", ".avi")) and not f.startswith("sample_"):
                    path = os.path.join(self.search_dir, f)
                    is_valid, _ = validate_media_asset(path)
                    if is_valid:
                        items.append(MediaItem(
                            provider="local",
                            url=path,
                            local_path=path,
                            duration=5.0,
                            width=width,
                            height=height,
                            search_term=query
                        ))
                    
        # 2. If no valid existing files, generate distinct dynamic motion clips per query
        if not items:
            # Deterministically hash query to pick visual theme
            query_hash = int(hashlib.md5(query.encode()).hexdigest(), 16)
            theme_idx = query_hash % len(VISUAL_THEMES)
            
            clip_name = f"motion_{aspect_ratio.name}_theme{theme_idx}.mp4"
            clip_path = os.path.join(self.search_dir, clip_name)
            
            # Recreate clip if not existing or invalid
            is_valid, _ = validate_media_asset(clip_path) if os.path.exists(clip_path) else (False, "")
            if not is_valid:
                try:
                    self._create_dynamic_motion_clip(clip_path, width, height, theme_idx=theme_idx, duration=5)
                except Exception as e:
                    logger.warning(f"Could not generate dynamic motion clip: {e}")
                    
            if os.path.exists(clip_path):
                items.append(MediaItem(
                    provider="local",
                    url=clip_path,
                    local_path=clip_path,
                    duration=5.0,
                    width=width,
                    height=height,
                    search_term=query
                ))
                
        return items
        
    async def download(self, item: MediaItem, dest_dir: str) -> str:
        return item.local_path
