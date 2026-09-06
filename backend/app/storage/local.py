import os
import shutil
import aiofiles
from pathlib import Path
from typing import Optional
from loguru import logger
from backend.app.storage.base import StorageProvider
from backend.app.config import get_settings

class LocalStorageProvider(StorageProvider):
    def __init__(self, root_dir: Optional[str] = None):
        settings = get_settings()
        dir_name = root_dir if root_dir is not None else settings.MEDIA_ROOT
        self.root_dir = Path(dir_name).resolve()
        self.ensure_dirs()
        
    def ensure_dirs(self):
        dirs = ["videos", "audio", "images", "thumbnails", "temp"]
        for d in dirs:
            (self.root_dir / d).mkdir(parents=True, exist_ok=True)
            
    def _validate_safe_path(self, key: str) -> Path:
        """Prevent path traversal attacks (e.g. ../../etc/passwd)."""
        clean_key = key.lstrip("/\\")
        dest_path = (self.root_dir / clean_key).resolve()
        if not str(dest_path).startswith(str(self.root_dir)):
            raise ValueError(f"Path traversal detected for storage key: {key}")
        return dest_path

    async def save(self, source_path: str, dest_key: str) -> str:
        dest_path = self._validate_safe_path(dest_key)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Async file streaming
        async with aiofiles.open(source_path, 'rb') as src, aiofiles.open(dest_path, 'wb') as dst:
            while True:
                chunk = await src.read(65536)
                if not chunk:
                    break
                await dst.write(chunk)
                
        return dest_key
        
    async def get(self, key: str) -> str:
        dest_path = self._validate_safe_path(key)
        return str(dest_path)
        
    async def delete(self, key: str) -> bool:
        dest_path = self._validate_safe_path(key)
        if dest_path.exists():
            dest_path.unlink()
            return True
        return False
        
    async def exists(self, key: str) -> bool:
        dest_path = self._validate_safe_path(key)
        return dest_path.exists()
